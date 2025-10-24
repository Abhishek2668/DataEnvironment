from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from typing import Literal

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
    loop_interval: float = 15.0
    daily_target_pct: float | None = None
    daily_loss_limit_pct: float | None = None


@dataclass(slots=True)
class LiveSessionState:
    status: Literal["running", "stopped", "error"] = "stopped"
    run_id: str | None = None
    instrument: str | None = None
    strategy: str | None = None
    granularity: str | None = None
    equity: float | None = None
    start_equity: float | None = None
    daily_return_pct: float | None = None
    open_positions: int = 0
    trades_today: int = 0
    target_hit: bool = False
    loss_limit_hit: bool = False
    timestamp: datetime | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "instrument": self.instrument,
            "strategy": self.strategy,
            "granularity": self.granularity,
            "equity": self.equity,
            "start_equity": self.start_equity,
            "daily_return_pct": self.daily_return_pct,
            "open_positions": self.open_positions,
            "trades_today": self.trades_today,
            "target_hit": self.target_hit,
            "loss_limit_hit": self.loss_limit_hit,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "message": self.message,
        }


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
        self._metrics_task: asyncio.Task[None] | None = None
        self._current_config: LiveRunConfig | None = None
        self._current_run_id: str | None = None
        self._state = LiveSessionState()
        self._state_lock = asyncio.Lock()

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
            run_id = utc_now().format("YYYYMMDDHHmmss")
            self._current_config = config
            self._current_run_id = run_id
            await self._initialise_state(run_id=run_id, config=config)
            executor = Executor(
                broker=self._broker,
                strategy=strategy,
                config=execution_config,
                event_bus=self._bus,
                on_trade=self._record_trade,
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
            await self._bus.publish("events", {"type": "session_started", **self._state.as_dict()})
            await self._refresh_metrics(run_id, emit_event=True)
            self._task = asyncio.create_task(
                self._run_loop(run_id=run_id, strategy=strategy, executor=executor, context=context)
            )
            self._task.add_done_callback(self._on_task_done)
            self._metrics_task = asyncio.create_task(self._metrics_loop(run_id))
            return run_id

    async def stop(self) -> None:
        task: asyncio.Task[None] | None
        metrics_task: asyncio.Task[None] | None
        async with self._lock:
            task = self._task
            metrics_task = self._metrics_task
        if not task:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        if metrics_task:
            metrics_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await metrics_task

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        with contextlib.suppress(Exception):
            task.result()
        self._task = None
        self._current_config = None
        self._current_run_id = None
        metrics_task = self._metrics_task
        self._metrics_task = None
        if metrics_task:
            metrics_task.cancel()

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
            await self._finalise_session(run_id, status="stopped")
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
            await self._finalise_session(run_id, status="error", message=str(exc))
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
            await self._finalise_session(run_id, status="stopped")
        finally:
            strategy.on_stop()


    async def _initialise_state(self, *, run_id: str, config: LiveRunConfig) -> None:
        account = await self._broker.get_account()
        equity = self._extract_equity(account)
        positions = await self._broker.get_open_positions()
        timestamp = utc_now()
        async with self._state_lock:
            self._state = LiveSessionState(
                status="running",
                run_id=run_id,
                instrument=config.instrument,
                strategy=config.strategy,
                granularity=config.granularity,
                equity=equity,
                start_equity=equity if equity else None,
                daily_return_pct=0.0 if equity else None,
                open_positions=len(positions),
                trades_today=0,
                target_hit=False,
                loss_limit_hit=False,
                timestamp=timestamp,
                message=None,
            )

    async def _metrics_loop(self, run_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(max((self._current_config.loop_interval if self._current_config else 15.0), 1.0))
                if self._current_run_id != run_id:
                    break
                await self._refresh_metrics(run_id)
        except asyncio.CancelledError:
            pass

    async def _refresh_metrics(self, run_id: str, *, emit_event: bool = True) -> None:
        account = await self._broker.get_account()
        positions = await self._broker.get_open_positions()
        equity = self._extract_equity(account)
        timestamp = utc_now()
        hit_target = False
        hit_loss = False
        async with self._state_lock:
            if self._state.run_id != run_id:
                return
            state = self._state
            if state.start_equity is None and equity is not None:
                state.start_equity = equity
            state.equity = equity
            if state.start_equity and state.start_equity > 0 and equity is not None:
                state.daily_return_pct = ((equity - state.start_equity) / state.start_equity) * 100
            elif equity is None:
                state.daily_return_pct = None
            state.open_positions = len(positions)
            state.timestamp = timestamp
            config = self._current_config
            if config and state.daily_return_pct is not None:
                if (
                    config.daily_target_pct is not None
                    and state.daily_return_pct >= config.daily_target_pct
                    and not state.target_hit
                ):
                    state.target_hit = True
                    hit_target = True
                if (
                    config.daily_loss_limit_pct is not None
                    and state.daily_return_pct <= -config.daily_loss_limit_pct
                    and not state.loss_limit_hit
                ):
                    state.loss_limit_hit = True
                    hit_loss = True
            payload = state.as_dict()
        if emit_event:
            await self._bus.publish("events", {"type": "equity_update", **payload})
            if hit_target:
                await self._bus.publish("events", {"type": "target_hit", **payload})
            if hit_loss:
                await self._bus.publish("events", {"type": "loss_limit_hit", **payload})

    async def _record_trade(self, trade: dict[str, Any]) -> dict[str, Any] | None:
        async with self._state_lock:
            if self._state.status != "running":
                return None
            self._state.trades_today += 1
        run_id = self._current_run_id
        if not run_id:
            return None
        await self._refresh_metrics(run_id, emit_event=False)
        async with self._state_lock:
            self._state.timestamp = utc_now()
            payload = self._state.as_dict()
        return payload

    async def _finalise_session(self, run_id: str, *, status: Literal["stopped", "error"], message: str | None = None) -> None:
        timestamp = utc_now()
        async with self._state_lock:
            if self._state.run_id != run_id:
                return
            self._state.status = status
            self._state.message = message
            self._state.timestamp = timestamp
        payload = self._state.as_dict()
        event_type = "session_stopped" if status == "stopped" else "error"
        await self._bus.publish("events", {"type": event_type, **payload})

    async def get_state(self) -> dict[str, Any]:
        async with self._state_lock:
            return self._state.as_dict()

    @staticmethod
    def _extract_equity(account: dict[str, Any]) -> float | None:
        for key in ("equity", "balance", "NAV", "nav"):
            value = account.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None


__all__ = ["LiveRunner", "LiveRunnerError", "LiveRunConfig", "LiveSessionState"]

