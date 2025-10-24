"""Trading engine orchestration and state machine."""
from __future__ import annotations

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque

from .broker import Broker, PaperBroker
from .data import CandleStore, FeatureCalculator, generate_synthetic_candles
from .event_bus import EventBus
from .metrics import Counter, Gauge, register
from .models import (
    Candle,
    EngineStageStatus,
    EngineStatus,
    EventEnvelope,
    FeatureSnapshot,
    OrderIntent,
    Position,
    Signal,
    SignalDirection,
)
from .news import NewsService
from .risk import RiskManager
from .rl_agent import RLSignalService
from .settings import Settings

STAGES = ["data", "features", "rl", "risk", "order", "broker", "position", "pnl", "news"]

METRIC_TRADE_COUNT = register(Counter("trades_total", "Total trades executed", ["mode"]))
METRIC_REJECT_COUNT = register(Counter("trade_rejections_total", "Rejected trades", ["reason"]))
METRIC_HEARTBEAT = register(Gauge("engine_heartbeat", "Engine heartbeat timestamp"))
METRIC_EQUITY = register(Gauge("equity", "Account equity"))


@dataclass(slots=True)
class EngineContext:
    instrument: str
    timeframe: str
    mode: str


class TradingEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        broker: Broker | None = None,
        candle_store: CandleStore,
        event_bus: EventBus,
        news_service: NewsService,
    ) -> None:
        self.settings = settings
        self.broker = broker or PaperBroker()
        self.candle_store = candle_store
        self.event_bus = event_bus
        self.news_service = news_service
        self.risk = RiskManager(settings)
        self.rl_service = RLSignalService(settings)
        self.feature_calc = FeatureCalculator(self.candle_store.window)
        self.stages: dict[str, EngineStageStatus] = {
            stage: EngineStageStatus(stage=stage) for stage in STAGES
        }
        self.run_id: str | None = None
        self.context: EngineContext | None = None
        self.last_signal: Signal | None = None
        self.last_features: FeatureSnapshot | None = None
        self._runner_task: asyncio.Task | None = None
        self._news_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._events: Deque[EventEnvelope] = deque(maxlen=200)
        self._idle_reason = "Engine not started"
        self._forced_signal: Signal | None = None

    async def start(self, *, instrument: str, timeframe: str, mode: str) -> str:
        if self._runner_task and not self._runner_task.done():
            raise RuntimeError("Engine already running")
        self.run_id = uuid.uuid4().hex
        self.context = EngineContext(instrument=instrument, timeframe=timeframe, mode=mode)
        self._stop_event.clear()
        self._runner_task = asyncio.create_task(self._run_loop())
        self._news_task = asyncio.create_task(self._news_loop())
        return self.run_id

    async def stop(self) -> None:
        self._stop_event.set()
        if self._runner_task:
            await self._runner_task
        if self._news_task:
            await self._news_task
        self._runner_task = None
        self._news_task = None
        self._idle_reason = "Engine stopped"

    async def force_signal(self, signal: Signal) -> None:
        self._forced_signal = signal
        await self._publish_event(
            EventEnvelope(
                trace_id=uuid.uuid4().hex,
                stage="rl",
                ts=datetime.utcnow(),
                decision="forced_signal",
                reason_codes=signal.reason_codes,
                payload={"direction": signal.direction.value, "confidence": signal.confidence},
            )
        )

    async def _run_loop(self) -> None:
        assert self.context is not None
        interval = timedelta(minutes=1)
        start = datetime.utcnow() - timedelta(minutes=500)
        synthetic_stream = generate_synthetic_candles(
            instrument=self.context.instrument,
            start=start,
            steps=10_000,
            base_price=1.35,
            interval=interval,
        )
        for candle in synthetic_stream:
            if self._stop_event.is_set():
                break
            await self._process_candle(candle)
            await asyncio.sleep(float(self.settings.HEARTBEAT_INTERVAL_SECONDS))
        self._idle_reason = "Stream completed"

    async def _news_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                news_items = await self.news_service.fetch_news()
            except Exception as exc:  # pragma: no cover - network errors
                await self._transition("news", "error", reason="fetch_failed")
                await self._publish_event(
                    EventEnvelope(
                        trace_id=uuid.uuid4().hex,
                        stage="news",
                        ts=datetime.utcnow(),
                        decision="error",
                        reason_codes=["news_fetch_failed"],
                        payload={"error": str(exc)},
                    )
                )
            else:
                if news_items:
                    await self._transition("news", "ok")
                    latest = news_items[0]
                    await self._publish_event(
                        EventEnvelope(
                            trace_id=uuid.uuid4().hex,
                            stage="news",
                            ts=datetime.utcnow(),
                            decision="fetched",
                            reason_codes=[],
                            payload={"title": latest.title, "sentiment": latest.sentiment},
                        )
                    )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=300)
            except asyncio.TimeoutError:
                continue

    async def _process_candle(self, candle: Candle) -> None:
        now = datetime.utcnow()
        METRIC_HEARTBEAT.set(now.timestamp())
        await self._transition("data", "ok", reason="tick")
        self.candle_store.add(candle)
        self.risk.update_equity((await self.broker.account_summary()).equity)
        features = self.feature_calc.compute()
        if not features:
            self._idle_reason = "Awaiting feature warmup"
            await self._transition("features", "blocked", reason="insufficient_history")
            return
        self.last_features = features
        await self._transition("features", "ok")
        signal = await self._signal_decision(features)
        self.last_signal = signal
        if signal.direction == SignalDirection.FLAT or signal.confidence < float(self.settings.MIN_SIGNAL_CONF):
            reason = "low_confidence" if signal.direction != SignalDirection.FLAT else "flat_signal"
            self._idle_reason = "No actionable signal"
            METRIC_REJECT_COUNT.labels(reason=reason).inc()
            await self._transition("rl", "blocked", reason=reason)
            await self._evaluate_positions(candle, signal)
            return
        await self._transition("rl", "ok")
        account = await self.broker.account_summary()
        if self.risk.max_drawdown_breached(account.equity):
            await self._transition("risk", "blocked", reason="drawdown_stop")
            self._idle_reason = "Risk throttle active"
            METRIC_REJECT_COUNT.labels(reason="drawdown_stop").inc()
            await self._evaluate_positions(candle, signal)
            return
        plan = self.risk.position_plan(
            equity=account.equity,
            price=candle.close,
            atr=features.atr,
            direction=signal.direction,
        )
        if not plan:
            await self._transition("risk", "blocked", reason="position_sizing")
            self._idle_reason = "Risk filters blocked trade"
            METRIC_REJECT_COUNT.labels(reason="position_sizing").inc()
            await self._evaluate_positions(candle, signal)
            return
        await self._transition("risk", "ok")
        order = self.risk.build_order_intent(
            plan=plan,
            instrument=candle.instrument,
            price=candle.close,
            direction=signal.direction,
            reason_codes=signal.reason_codes,
        )
        await self._transition("order", "ok")
        position = await self.broker.place_order(order)
        await self._transition("broker", "ok")
        await self._publish_event(
            EventEnvelope(
                trace_id=uuid.uuid4().hex,
                stage="order",
                ts=datetime.utcnow(),
                decision="executed",
                reason_codes=order.reason_codes,
                payload={
                    "price": order.price,
                    "units": order.units,
                    "side": order.side.value,
                },
            )
        )
        METRIC_TRADE_COUNT.labels(mode=self.context.mode if self.context else "paper").inc()
        await self._publish_event(
            EventEnvelope(
                trace_id=uuid.uuid4().hex,
                stage="position",
                ts=datetime.utcnow(),
                decision="opened",
                reason_codes=[],
                payload={"position_id": position.id, "risk": order.risk_fraction},
            )
        )
        self._idle_reason = "Monitoring open positions"
        await self._evaluate_positions(candle, signal)

    async def _signal_decision(self, features: FeatureSnapshot) -> Signal:
        if self._forced_signal:
            signal = self._forced_signal
            self._forced_signal = None
            return signal
        if not self.settings.USE_RL_SIGNALS:
            return Signal(direction=SignalDirection.FLAT, confidence=0.0, features=features)
        signal = self.rl_service.predict(features)
        return signal

    async def _evaluate_positions(self, candle: Candle, signal: Signal) -> None:
        await self.broker.refresh_mark_to_market(candle.instrument, candle.close)
        await self._transition("pnl", "ok")
        positions = await self.broker.list_open_positions()
        METRIC_EQUITY.set((await self.broker.account_summary()).equity)
        for position in positions:
            exit_reason = None
            if position.stop_loss and (
                (position.side == SignalDirection.LONG and candle.low <= position.stop_loss)
                or (position.side == SignalDirection.SHORT and candle.high >= position.stop_loss)
            ):
                exit_reason = "stop_loss"
            elif position.take_profit and (
                (position.side == SignalDirection.LONG and candle.high >= position.take_profit)
                or (position.side == SignalDirection.SHORT and candle.low <= position.take_profit)
            ):
                exit_reason = "take_profit"
            elif signal.direction != position.side and signal.confidence - float(self.settings.MIN_SIGNAL_CONF) >= 0.3:
                exit_reason = "signal_flip"
            if exit_reason:
                closed = await self.broker.close_position(position.id, exit_reason)
                await self._publish_event(
                    EventEnvelope(
                        trace_id=uuid.uuid4().hex,
                        stage="position",
                        ts=datetime.utcnow(),
                        decision="closed",
                        reason_codes=[exit_reason],
                        payload={"position_id": closed.id, "pnl": closed.realized_pnl},
                    )
                )
        if positions:
            self._idle_reason = "Monitoring open positions"
        else:
            self._idle_reason = "No open positions"

    async def status(self) -> EngineStatus:
        account = await self.broker.account_summary()
        heartbeat = datetime.utcnow()
        latest_event = self._events[-1].model_dump() if self._events else None
        return EngineStatus(
            run_id=self.run_id,
            mode=self.context.mode if self.context else "paper",
            broker=self.settings.BROKER,
            instrument=self.context.instrument if self.context else None,
            heartbeat_ts=heartbeat,
            stages=list(self.stages.values()),
            latest_event=latest_event,
            idle_reason=self._idle_reason,
        )

    async def _transition(self, stage: str, status: str, reason: str | None = None) -> None:
        entry = self.stages[stage]
        entry.status = status  # type: ignore[assignment]
        entry.reason = reason
        entry.last_event_ts = datetime.utcnow()
        await self.event_bus.publish(
            "events",
            {
                "stage": stage,
                "status": status,
                "reason": reason,
                "ts": entry.last_event_ts.isoformat(),
            },
        )

    async def _publish_event(self, event: EventEnvelope) -> None:
        self._events.append(event)
        await self.event_bus.publish("events", event.model_dump())


__all__ = ["TradingEngine"]
