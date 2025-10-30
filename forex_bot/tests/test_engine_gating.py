from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.asyncio
async def test_engine_blocks_low_confidence_signal(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "trading.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("LOOP_INTERVAL_SECONDS", "0.01")

    modules = [
        "forex_bot.utils.settings",
        "forex_bot.data.candles",
        "forex_bot.engine.core",
    ]
    for name in modules:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)

    from forex_bot.engine.core import EngineContext, TradingEngine
    from forex_bot.utils.settings import get_settings

    settings = get_settings()
    TradingEngine._instance = None  # type: ignore[attr-defined]
    engine = TradingEngine.get_instance(settings)
    engine.context = EngineContext(instrument="EUR_USD", timeframe="M5", mode="paper")
    engine.current_run = await engine.store.create_run("EUR_USD", "M5", "paper")

    await engine._warm_history()  # type: ignore[attr-defined]

    engine.strategy.generate = lambda candles: {"direction": "long", "confidence": 0.05, "reason": "test"}  # type: ignore[assignment]

    await engine._tick()  # type: ignore[attr-defined]

    orders = await engine.store.list_orders(engine.current_run.id)
    assert orders == []
