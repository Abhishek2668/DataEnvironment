"""Trading engine orchestration."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


from forex_bot.broker import PaperBroker
from forex_bot.broker.oanda import OandaBroker
from forex_bot.data.candles import CandleStore
from forex_bot.data.models import Candle, Run
from forex_bot.strategies.murphy_candles import MurphyStrategy, Signal
from forex_bot.utils.event_bus import EventBus
from forex_bot.utils.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EngineContext:
    instrument: str
    timeframe: str
    mode: str


class TradingEngine:
    """Coordinates candle ingestion, strategy evaluation, and order execution."""

    _instance: "TradingEngine" | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bus = EventBus()
        self.store = CandleStore(settings)
        self.broker = self._create_broker()
        self.strategy = MurphyStrategy()
        self.running = False
        self.context: EngineContext | None = None
        self.current_run: Run | None = None
        self._stop_event = asyncio.Event()
        self._forced_signal: Optional[Signal] = None
        self._last_candle: Candle | None = None
        self._last_signal: Signal | None = None
        self._open_trades: int = 0
        self._unrealized_pnl: float = 0.0
        self._news_windows: list[tuple[datetime, datetime]] = []
        self._open_position_risk: Dict[str, float] = {}
        self._position_metadata: Dict[str, Dict[str, Any]] = {}
        self._state_snapshot: Dict[str, Any] = {
            "running": False,
            "status": "stopped",
            "run_id": None,
            "instrument": None,
            "timeframe": None,
            "last_signal_direction": None,
            "last_signal_confidence": None,
            "open_trades": 0,
            "unrealized_pnl": 0.0,
            "last_candle_at": None,
        }

    @classmethod
    def get_instance(cls, settings: Settings | None = None) -> "TradingEngine":
        if cls._instance is None:
            if settings is None:
                raise RuntimeError("Settings required for first initialisation")
            cls._instance = cls(settings)
        return cls._instance

    def _create_broker(self):
        if self.settings.broker.lower() == "oanda":
            return OandaBroker(self.settings, self.store, self.bus)
        return PaperBroker(self.settings, self.store, self.bus)

    async def start(
        self, instrument: str | None = None, timeframe: str | None = None, mode: str | None = None
    ) -> None:
        if self.running:
            logger.info("Trading engine already running")
            return
        instrument = instrument or self.settings.default_instrument or "EUR_USD"
        timeframe = timeframe or self.settings.default_timeframe or "M5"
        mode = mode or self.settings.broker
        self.context = EngineContext(instrument=instrument, timeframe=timeframe, mode=mode)
        self.current_run = await self.store.create_run(instrument, timeframe, mode)
        self.running = True
        self._stop_event.clear()
        self._forced_signal = None
        self._last_signal = None
        self._open_trades = 0
        self._unrealized_pnl = 0.0
        self._news_windows.clear()
        self._open_position_risk.clear()
        self._position_metadata.clear()
        await self.bus.publish(
            "engine.state",
            {
                "event": "started",
                "run_id": self.current_run.id,
                "instrument": instrument,
                "timeframe": timeframe,
                "running": True,
            },
        )
        logger.info("Trading engine started run %s", self.current_run.id)
        self._state_snapshot.update(
            {
                "running": True,
                "status": "running",
                "run_id": self.current_run.id,
                "instrument": instrument,
                "timeframe": timeframe,
                "last_signal_direction": None,
                "last_signal_confidence": None,
                "open_trades": 0,
                "unrealized_pnl": 0.0,
                "last_candle_at": None,
                "activity": "idle",
            }
        )
        await self._warm_history()
        try:
            while not self._stop_event.is_set():
                await self._tick()
                await asyncio.sleep(self.settings.loop_interval_seconds)
        finally:
            await self.store.complete_run(self.current_run.id)
            self.running = False
            await self.bus.publish(
                "engine.state",
                {
                    "event": "stopped",
                    "run_id": self.current_run.id,
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "running": False,
                },
            )
            logger.info("Trading engine stopped run %s", self.current_run.id)
            self._state_snapshot.update({"running": False, "status": "stopped"})

    async def _tick(self) -> None:
        assert self.context is not None
        instrument = self.context.instrument
        timeframe = self.context.timeframe
        logger.info("[ENGINE] Fetching %s (%s) candles...", instrument, timeframe)
        candles = await self.store.get_latest(instrument, timeframe, 200)
        logger.info("[ENGINE] Got %s candles", len(candles))
        if not candles:
            logger.warning("[ENGINE] No candles available for %s (%s); skipping loop", instrument, timeframe)
            await self.bus.publish(
                "engine.tick",
                {
                    "run_id": self.current_run.id if self.current_run else None,
                    "instrument": instrument,
                    "timeframe": timeframe,
                    "status": "no_data",
                },
            )
            return

        latest = candles[-1]
        self._last_candle = latest
        await self.bus.publish(
            "candle.new",
            {
                "run_id": self.current_run.id if self.current_run else None,
                "instrument": latest.instrument,
                "close": latest.close,
                "timestamp": latest.timestamp.isoformat(),
            },
        )

        if self._forced_signal:
            raw_signal: Signal | Dict[str, Any] | None = self._forced_signal
        else:
            strategy_context = await self._build_strategy_context(instrument, latest.timestamp)
            try:
                raw_signal = self.strategy.generate(
                    candles,
                    threshold=self.settings.signal_confidence_threshold,
                    context=strategy_context,
                )
            except TypeError:
                raw_signal = self.strategy.generate(candles)
        self._forced_signal = None
        signal = self._coerce_signal(raw_signal)
        self._last_signal = signal

        executed_order: Dict[str, Any] | None = None
        if signal and signal.confidence >= self.settings.signal_confidence_threshold:
            can_trade, position_size, risk_pct = await self.manage_risk(signal, latest)
            if not can_trade:
                logger.info("[ENGINE] Risk controls rejected trade signal")
                signal = None
                self._last_signal = None
            else:
                logger.info(
                    "[ENGINE] Executing %s trade on %s (units=%s)",
                    signal.direction,
                    instrument,
                    position_size,
                )
                original_units = self.settings.trade_units
                self.settings.trade_units = max(position_size, 1)
                try:
                    executed_order = await self.broker.execute_trade(
                        instrument,
                        signal.direction,
                        run_id=self.current_run.id if self.current_run else "",
                        price=latest.close,
                        confidence=signal.confidence,
                    )
                finally:
                    self.settings.trade_units = original_units
                if executed_order:
                    position_id = executed_order.get("position_id")
                    if position_id:
                        self._open_position_risk[position_id] = risk_pct
                        trade_log = self._compose_trade_log(
                            signal,
                            result="open",
                            additional={
                                "order_id": executed_order.get("order_id"),
                                "position_id": position_id,
                                "instrument": instrument,
                                "timeframe": timeframe,
                                "position_size": position_size,
                                "entry_price": latest.close,
                            },
                        )
                        self._position_metadata[position_id] = trade_log
                        logger.info("[ENGINE] Trade metrics: %s", trade_log)
                    await self.bus.publish(
                        "trade.executed",
                        {
                            "run_id": self.current_run.id if self.current_run else None,
                            "instrument": instrument,
                            "timeframe": timeframe,
                            "direction": signal.direction,
                            "confidence": signal.confidence,
                            "price": latest.close,
                            "order": executed_order,
                            "stop_loss": signal.stop_loss,
                            "take_profit": signal.take_profit,
                            "regime": signal.regime,
                            "confidence_breakdown": signal.confidence_breakdown,
                            "rr_ratio": signal.rr_ratio,
                            "position_size": position_size,
                        },
                    )
        if not executed_order:
            logger.info("[ENGINE] No valid trade signal this loop.")

        if self.current_run:
            closed = await self.broker.update_positions(
                self.current_run.id,
                instrument=instrument,
                price=latest.close,
            )
            if closed:
                logger.info("Closed %s positions", len(closed))
                for payload in closed:
                    position_id = payload.get("position_id")
                    if position_id and position_id in self._open_position_risk:
                        self._open_position_risk.pop(position_id, None)
                    if position_id and position_id in self._position_metadata:
                        trade_log = dict(self._position_metadata.pop(position_id))
                        pnl = payload.get("pnl", 0.0)
                        trade_log.update(
                            {
                                "result": "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven",
                                "pnl": pnl,
                                "exit_price": payload.get("exit_price"),
                                "closed_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
                            }
                        )
                        logger.info("[ENGINE] Trade outcome: %s", trade_log)

        activity = "trade" if executed_order else "idle"
        await self._refresh_metrics(latest, activity)
        status_payload = {
            "run_id": self.current_run.id if self.current_run else None,
            "instrument": instrument,
            "timeframe": timeframe,
            "activity": activity,
            "last_signal_direction": signal.direction if signal else None,
            "last_signal_confidence": signal.confidence if signal else None,
            "open_trades": self._open_trades,
            "unrealized_pnl": self._unrealized_pnl,
            "last_candle_timestamp": latest.timestamp.isoformat(),
            "running": self.running,
        }
        await self.bus.publish("engine.tick", status_payload)

    async def stop(self) -> None:
        if not self.running:
            return
        self._stop_event.set()

    def force_signal(self, direction: str, confidence: float) -> None:
        entry = self._last_candle.close if self._last_candle else None
        if entry is None:
            self._forced_signal = Signal(direction=direction, confidence=confidence, reason="manual")
            return
        buffer = 0.001
        stop_loss = entry - buffer if direction == "long" else entry + buffer
        take_profit = entry + buffer * 3 if direction == "long" else entry - buffer * 3
        self._forced_signal = Signal(
            direction=direction,
            confidence=confidence,
            reason="manual",
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime="manual",
            timestamp=datetime.utcnow().replace(tzinfo=timezone.utc),
        )

    async def _warm_history(self) -> None:
        if not self.context:
            return
        instrument = self.context.instrument
        timeframe = self.context.timeframe
        candles = await self.store.get_latest(instrument, timeframe, 200)
        if candles:
            self._last_candle = candles[-1]
            return
        logger.info("No cached candles for %s (%s); generating synthetic warmup", instrument, timeframe)
        start_time = datetime.utcnow() - timedelta(seconds=self.settings.candle_interval_seconds * 200)
        price = self._last_candle.close if self._last_candle else 1.1
        synthetic: list[Candle] = []
        for step in range(200):
            timestamp = start_time + timedelta(seconds=self.settings.candle_interval_seconds * step)
            candle = self._generate_synthetic_candle(timestamp, price, instrument, timeframe)
            price = candle.close
            synthetic.append(candle)
        for candle in synthetic:
            await self.store.record_candle(candle)
        self._last_candle = synthetic[-1]

    async def status(self) -> Dict[str, Any]:
        snapshot = dict(self._state_snapshot)
        snapshot.update({"running": self.running})
        if snapshot.get("status") != "error":
            snapshot["status"] = "running" if self.running else "stopped"
        return snapshot

    def last_price(self) -> float | None:
        return self._last_candle.close if self._last_candle else None

    async def _refresh_metrics(self, latest: Candle, activity: str) -> None:
        if not self.current_run:
            return
        open_positions = await self.broker.list_open_positions(self.current_run.id)
        self._open_trades = len(open_positions)
        self._unrealized_pnl = await self.broker.unrealized_pnl(
            self.current_run.id,
            instrument=latest.instrument,
            price=latest.close,
        )
        self._state_snapshot.update(
            {
                "run_id": self.current_run.id,
                "instrument": latest.instrument,
                "timeframe": self.context.timeframe if self.context else None,
                "last_signal_direction": self._last_signal.direction if self._last_signal else None,
                "last_signal_confidence": self._last_signal.confidence if self._last_signal else None,
                "open_trades": self._open_trades,
                "unrealized_pnl": self._unrealized_pnl,
                "last_candle_at": latest.timestamp.isoformat(),
                "activity": activity,
                "status": "running" if self.running else "stopped",
            }
        )

    def _generate_synthetic_candle(
        self, timestamp: datetime, price: float, instrument: str, timeframe: str
    ) -> Candle:
        change = random.gauss(0, 0.0004)
        open_price = price
        close_price = max(0.0001, price * (1 + change))
        high = max(open_price, close_price) * (1 + abs(change) * 0.5)
        low = min(open_price, close_price) * (1 - abs(change) * 0.5)
        volume = abs(random.gauss(1000, 200))
        return Candle(
            instrument=instrument,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=volume,
        )

    def _coerce_signal(self, value: Signal | Dict[str, Any] | None) -> Signal | None:
        if value is None:
            return None
        if isinstance(value, Signal):
            return value
        direction = value.get("direction") if isinstance(value, dict) else None
        confidence = value.get("confidence", 0.0) if isinstance(value, dict) else 0.0
        reason = value.get("reason", "external") if isinstance(value, dict) else "external"
        if direction not in {"long", "short"}:
            return None
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0
        entry_price = value.get("entry_price") if isinstance(value, dict) else None
        stop_loss = value.get("stop_loss") if isinstance(value, dict) else None
        take_profit = value.get("take_profit") if isinstance(value, dict) else None
        regime = value.get("regime") if isinstance(value, dict) else None
        confidence_breakdown = value.get("confidence_breakdown") if isinstance(value, dict) else None
        rr_ratio = value.get("rr_ratio") if isinstance(value, dict) else None
        timestamp_value = value.get("timestamp") if isinstance(value, dict) else None
        indicators = value.get("indicators") if isinstance(value, dict) else None
        position_size = value.get("position_size") if isinstance(value, dict) else None
        return Signal(
            direction=direction,
            confidence=confidence_value,
            reason=reason,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime,
            confidence_breakdown=confidence_breakdown,
            rr_ratio=rr_ratio,
            timestamp=timestamp_value,
            indicators=indicators,
            position_size=position_size,
        )

    async def _build_strategy_context(
        self, instrument: str, timestamp: datetime
    ) -> Dict[str, Any]:
        news_blocked = self._is_news_blocked(timestamp)
        h1_task = asyncio.create_task(self.store.get_latest(instrument, "H1", 200))
        h4_task = asyncio.create_task(self.store.get_latest(instrument, "H4", 200))
        h1_candles, h4_candles = await asyncio.gather(h1_task, h4_task)
        return {
            "news_blocked": news_blocked,
            "higher_timeframes": {
                "H1": h1_candles,
                "H4": h4_candles,
            },
        }

    def _is_news_blocked(self, timestamp: datetime) -> bool:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        windows: list[tuple[datetime, datetime]] = []
        blocked = False
        for start, end in self._news_windows:
            if end < timestamp:
                continue
            windows.append((start, end))
            if start <= timestamp <= end:
                blocked = True
        self._news_windows = windows
        return blocked

    def register_news_event(self, event_time: datetime, window: timedelta | None = None) -> None:
        window = window or timedelta(minutes=30)
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        start = event_time - window
        end = event_time + window
        self._news_windows.append((start, end))

    async def manage_risk(self, signal: Signal, latest: Candle) -> tuple[bool, int, float]:
        if signal.stop_loss is None or signal.entry_price is None:
            logger.warning("[ENGINE] Signal missing stop-loss or entry; cannot manage risk")
            return False, 0, 0.0
        summary = await self.broker.account_summary()
        equity = float(summary.get("balance", 0.0))
        if equity <= 0:
            logger.warning("[ENGINE] Unable to determine account equity; skipping trade")
            return False, 0, 0.0
        pip_size = self._pip_size(latest.instrument)
        stop_distance = abs(signal.entry_price - signal.stop_loss)
        stop_distance_pips = stop_distance / pip_size if pip_size else 0.0
        if stop_distance_pips <= 0:
            logger.warning("[ENGINE] Invalid stop distance; skipping trade")
            return False, 0, 0.0
        risk_pct = 0.01
        total_exposure = sum(self._open_position_risk.values())
        if total_exposure + risk_pct > 0.03:
            logger.info("[ENGINE] Exposure cap reached (%.2f); skipping trade", total_exposure)
            return False, 0, risk_pct
        position_size = int((equity * risk_pct) / stop_distance_pips)
        if position_size <= 0:
            logger.info("[ENGINE] Computed position size is zero; skipping trade")
            return False, 0, risk_pct
        signal.position_size = position_size
        return True, position_size, risk_pct

    def _pip_size(self, instrument: str) -> float:
        if instrument.upper().endswith("JPY"):
            return 0.01
        return 0.0001

    def _compose_trade_log(
        self,
        signal: Signal,
        *,
        result: str,
        additional: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload = {
            "timestamp": (signal.timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)).isoformat(),
            "regime": signal.regime,
            "confidence": signal.confidence,
            "confidence_breakdown": signal.confidence_breakdown,
            "rr_ratio": signal.rr_ratio,
            "direction": signal.direction,
            "reason": signal.reason,
            "result": result,
        }
        if signal.indicators:
            payload["indicators"] = signal.indicators
        if additional:
            payload.update(additional)
        return payload


__all__ = ["TradingEngine"]
