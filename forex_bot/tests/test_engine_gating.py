from __future__ import annotations

from datetime import datetime, timedelta
from types import MethodType

import pytest

from forex_app.broker import PaperBroker
from forex_app.data import CandleStore, generate_synthetic_candles
from forex_app.engine import TradingEngine
from forex_app.event_bus import EventBus
from forex_app.models import Signal, SignalDirection
from forex_app.news import NewsService
from forex_app.settings import Settings


@pytest.mark.asyncio
async def test_engine_blocks_low_confidence_signal(tmp_path) -> None:
    settings = Settings(DB_PATH=tmp_path / "trading.db", DATA_DIR=tmp_path / "data")
    candle_store = CandleStore(settings.DB_PATH)
    event_bus = EventBus()
    news_service = NewsService(settings)
    engine = TradingEngine(
        settings=settings,
        broker=PaperBroker(),
        candle_store=candle_store,
        event_bus=event_bus,
        news_service=news_service,
    )

    start = datetime.utcnow() - timedelta(minutes=200)
    candles = list(
        generate_synthetic_candles(
            instrument="EUR_USD",
            start=start,
            steps=30,
            base_price=1.1,
            interval=timedelta(minutes=1),
        )
    )
    for candle in candles[:-1]:
        candle_store.add(candle)
    low_conf_signal = Signal(direction=SignalDirection.LONG, confidence=0.2, reason_codes=["low_conf"], features=None)

    engine._forced_signal = low_conf_signal

    await engine._process_candle(candles[-1])

    assert engine.stages["rl"].status == "blocked"
    assert engine._idle_reason in {"No actionable signal", "No open positions"}
