from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from forex.data.run_store import RunStore
from forex.execution.executor import ExecutionConfig, Executor
from forex.realtime.bus import EventBus
from forex.strategy.base import Strategy, StrategyContext
from forex.utils.time import utc_now


class LiveRunnerError(RuntimeError):
    """Raised when the live runner encounters an invalid state."""


@dataclass(slots=True)
class LiveRunConfig:
    strategy: str
    instrument: str
    granularity: str
    risk_pct: float
    stop_distance_pips: float
    max_positions: int
    spread_pips: float
    params: Dict[str, Any]
    take_profit_pips: float | None = None


class LiveRunner:
    def __init__(
        self,
        *,
        broker,
        strategy_factory: Callable[[str, Dict[str, Any]], Strategy],
        event_bus: EventBus,
        run_store: RunStore,
    ) -> None:
        self._broker = broker
        self._strategy_factory = strategy_factory
        self._bus = event_bus
        self._run_store = run_store
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._current_config: LiveRunConfig | None = None
        self._current_run_id: str | None = None

    @property
    def run_id(self) -> Optional[str]:
        return self._current_run_id

    @property
    def is_running(self) -> bool:
        task = self._task
        return bool(task and not task.done())

    async def start(self, config: LiveRunConfig) -> str:
        async with self._lock:
            if self.is_running:
                raise LiveRunnerError("Live session already running")
            strategy = self._strategy_factory(config.strategy, config.params)
            execution_config = ExecutionConfig(
                instrument=config.instrument,
                risk_pct=config.risk_pct,
                stop_distance_pips=config.stop_distance_pips,
                max_positions=config.max_positions,
            )
            context = StrategyContext(
                instrument=config.instrument,
                granularity=config.granularity,
                risk_pct=config.risk_pct,
                max_positions=config.max_positions,
            )
            run_id = uuid4().hex
            self._current_config = config
            self._current_run_id = run_id
            executor = Executor(
                broker=self._broker,
                strategy=strategy,
                config=execution_config,
                event_bus=self._bus,
            )
            self._run_store.start_run(
                run_id,
                run_type="live",
                strategy=config.strategy,
                instrument=config.instrument,
                granularity=config.granularity,
                config={
                    "risk_pct": config.risk_pct,
                    "max_positions": config.max_positions,
                    "stop_distance_pips": config.stop_distance_pips,
                    "spread_pips": config.spread_pips,
                    "take_profit_pips": config.take_profit_pips,
                    "params": config.params,
                },
            )
            await self._bus.publish(
                "logs",
                {
                    "event": "live_start",
                    "run_id": run_id,
                    "instrument": config.instrument,
                    "strategy": config.strategy,
                    "timestamp": utc_now().isoformat(),
                },
            )
            self._task = asyncio.create_task(
                self._run_loop(run_id=run_id, strategy=strategy, executor=executor, context=context)
            )
            self._task.add_done_callback(self._on_task_done)
            return run_id

    async def stop(self) -> None:
        task: asyncio.Task[None] | None
        async with self._lock:
            task = self._task
        if not task:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        with contextlib.suppress(Exception):
            task.result()
        self._task = None
        self._current_config = None
        self._current_run_id = None

    async def _run_loop(
        self,
        *,
        run_id: str,
        strategy: Strategy,
        executor: Executor,
        context: StrategyContext,
    ) -> None:
        strategy.on_startup(context)
        instrument = context.instrument
        topic = f"prices:{instrument.upper()}"
        try:
            async for price in self._broker.price_stream([instrument]):
                price_payload = {
                    "run_id": run_id,
                    "instrument": price.instrument,
                    "bid": price.bid,
                    "ask": price.ask,
                    "mid": price.mid,
                    "time": price.time.isoformat(),
                }
                await self._bus.publish("prices", price_payload)
                await self._bus.publish(topic, price_payload)
                strategy.on_price_tick(price)
                await executor.run_bar(price)
        except asyncio.CancelledError:
            await self._bus.publish(
                "logs",
                {
                    "event": "live_stopped",
                    "run_id": run_id,
                    "timestamp": utc_now().isoformat(),
                },
            )
            self._run_store.finish_run(run_id, status="stopped")
            raise
        except Exception as exc:  # pragma: no cover - defensive
            await self._bus.publish(
                "logs",
                {
                    "event": "live_error",
                    "run_id": run_id,
                    "detail": str(exc),
                    "timestamp": utc_now().isoformat(),
                },
            )
            self._run_store.finish_run(run_id, status="error")
            raise
        else:
            await self._bus.publish(
                "logs",
                {
                    "event": "live_complete",
                    "run_id": run_id,
                    "timestamp": utc_now().isoformat(),
                },
            )
            self._run_store.finish_run(run_id, status="completed")
        finally:
            strategy.on_stop()


__all__ = ["LiveRunner", "LiveRunnerError", "LiveRunConfig"]

