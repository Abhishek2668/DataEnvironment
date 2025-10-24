"""Trading engine orchestration."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
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
            try:
                raw_signal = self.strategy.generate(
                    candles, threshold=self.settings.signal_confidence_threshold
                )
            except TypeError:
                raw_signal = self.strategy.generate(candles)
        self._forced_signal = None
        signal = self._coerce_signal(raw_signal)
        self._last_signal = signal

        executed_order: Dict[str, Any] | None = None
        if signal and signal.confidence >= self.settings.signal_confidence_threshold:
            logger.info(
                "[ENGINE] Executing %s trade on %s",
                signal.direction,
                instrument,
            )
            executed_order = await self.broker.execute_trade(
                instrument,
                signal.direction,
                run_id=self.current_run.id if self.current_run else "",
                price=latest.close,
                confidence=signal.confidence,
            )
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
                },
            )
        else:
            logger.info("[ENGINE] No valid trade signal this loop.")

        if self.current_run:
            closed = await self.broker.update_positions(
                self.current_run.id,
                instrument=instrument,
                price=latest.close,
            )
            if closed:
                logger.info("Closed %s positions", len(closed))

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
        self._forced_signal = Signal(direction=direction, confidence=confidence, reason="manual")

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
        return Signal(direction=direction, confidence=confidence_value, reason=reason)


__all__ = ["TradingEngine"]
