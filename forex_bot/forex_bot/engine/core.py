"""Trading engine orchestration."""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from forex_bot.broker.paper import PaperBroker
from forex_bot.data.candles import CandleStore
from forex_bot.data.models import Candle, Run
from forex_bot.strategies.murphy_candles import MurphyStrategy
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
        self.broker = PaperBroker(settings, self.store, self.bus)
        self.strategy = MurphyStrategy()
        self.running = False
        self.context: EngineContext | None = None
        self.current_run: Run | None = None
        self._stop_event = asyncio.Event()
        self._forced_signal: Optional[Dict[str, Any]] = None
        self._last_candle: Candle | None = None

    @classmethod
    def get_instance(cls, settings: Settings | None = None) -> "TradingEngine":
        if cls._instance is None:
            if settings is None:
                raise RuntimeError("Settings required for first initialisation")
            cls._instance = cls(settings)
        return cls._instance

    async def start(self, instrument: str = "EUR_USD", timeframe: str = "M5", mode: str | None = None) -> None:
        if self.running:
            logger.info("Trading engine already running")
            return
        mode = mode or self.settings.broker
        self.context = EngineContext(instrument=instrument, timeframe=timeframe, mode=mode)
        self.current_run = await self.store.create_run(instrument, timeframe, mode)
        self.running = True
        self._stop_event.clear()
        await self.bus.publish(
            "engine.state",
            {"event": "started", "run_id": self.current_run.id, "instrument": instrument, "timeframe": timeframe},
        )
        logger.info("Trading engine started run %s", self.current_run.id)
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
                {"event": "stopped", "run_id": self.current_run.id, "instrument": instrument, "timeframe": timeframe},
            )
            logger.info("Trading engine stopped run %s", self.current_run.id)

    async def _warm_history(self) -> None:
        assert self.context is not None
        candles = await self.store.get_latest(self.context.instrument, self.context.timeframe, 200)
        if candles:
            self._last_candle = candles[-1]
            return
        logger.info("Seeding candle history for %s", self.context.instrument)
        now = datetime.utcnow() - timedelta(minutes=200)
        price = 1.1
        for _ in range(200):
            candle = self._generate_candle(timestamp=now, price=price)
            price = candle.close
            await self.store.record_candle(candle)
            now += timedelta(seconds=self.settings.candle_interval_seconds)
        candles = await self.store.get_latest(self.context.instrument, self.context.timeframe, 1)
        self._last_candle = candles[-1] if candles else None

    async def _tick(self) -> None:
        assert self.context is not None
        timestamp = datetime.utcnow()
        candle = self._generate_candle(timestamp=timestamp)
        self._last_candle = candle
        await self.store.record_candle(candle)
        await self.bus.publish(
            "candle.new",
            {
                "run_id": self.current_run.id if self.current_run else None,
                "instrument": candle.instrument,
                "close": candle.close,
                "timestamp": candle.timestamp.isoformat(),
            },
        )
        candles = await self.store.get_latest(self.context.instrument, self.context.timeframe, 200)
        signal = self._forced_signal or self.strategy.generate(candles)
        self._forced_signal = None
        if signal and signal["confidence"] >= self.settings.signal_confidence_threshold:
            await self._execute_signal(signal, candle)
        else:
            await self.bus.publish(
                "engine.tick",
                {
                    "run_id": self.current_run.id if self.current_run else None,
                    "instrument": candle.instrument,
                    "status": "idle",
                },
            )
        closed = await self.broker.update_positions(
            self.current_run.id,
            instrument=self.context.instrument,
            price=candle.close,
        )
        if closed:
            logger.info("Closed %s positions", len(closed))

    async def _execute_signal(self, signal: Dict[str, Any], candle: Candle) -> None:
        assert self.current_run is not None
        payload = await self.broker.place_order(
            run_id=self.current_run.id,
            instrument=self.context.instrument,
            direction=signal["direction"],
            price=candle.close,
            confidence=signal["confidence"],
        )
        trade_payload = {
            "run_id": self.current_run.id,
            "instrument": self.context.instrument,
            "signal": signal,
            "order": payload,
        }
        await self.bus.publish("trade.executed", trade_payload)
        logger.info("Executed trade %s", trade_payload)

    def _generate_candle(self, timestamp: datetime, price: float | None = None) -> Candle:
        assert self.context is not None
        if price is None and self._last_candle is not None:
            price = self._last_candle.close
        price = price or 1.1
        change = random.gauss(0, 0.0005)
        open_price = price
        close = max(0.0001, price * (1 + change))
        high = max(open_price, close) * (1 + abs(change) * 0.5)
        low = min(open_price, close) * (1 - abs(change) * 0.5)
        volume = abs(random.gauss(1500, 250))
        return Candle(
            instrument=self.context.instrument,
            timeframe=self.context.timeframe,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

    async def stop(self) -> None:
        if not self.running:
            return
        self._stop_event.set()

    def force_signal(self, direction: str, confidence: float) -> None:
        self._forced_signal = {"direction": direction, "confidence": confidence, "reason": "manual"}

    async def status(self) -> Dict[str, Any]:
        run = self.current_run
        return {
            "running": self.running,
            "run_id": run.id if run else None,
            "instrument": self.context.instrument if self.context else None,
            "timeframe": self.context.timeframe if self.context else None,
        }

    def last_price(self) -> float | None:
        return self._last_candle.close if self._last_candle else None


__all__ = ["TradingEngine"]
