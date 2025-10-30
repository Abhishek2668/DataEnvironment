from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.asyncio
async def test_paper_broker_closes_positions(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "trading.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("LOOP_INTERVAL_SECONDS", "0.01")
    monkeypatch.setenv("TAKE_PROFIT_PCT", "0.0001")
    monkeypatch.setenv("STOP_LOSS_PCT", "0.05")

    modules = [
        "forex_bot.utils.settings",
        "forex_bot.data.candles",
        "forex_bot.engine.core",
    ]
    for name in modules:
        if name in sys.modules:
            module = importlib.reload(sys.modules[name])
        else:
            module = importlib.import_module(name)
        if name == "forex_bot.engine.core":
            module.TradingEngine._instance = None  # type: ignore[attr-defined]

    from forex_bot.engine.core import EngineContext, TradingEngine
    from forex_bot.utils.settings import get_settings

    settings = get_settings()
    engine = TradingEngine.get_instance(settings)
    engine.context = EngineContext(instrument="EUR_USD", timeframe="M5", mode="paper")
    engine.current_run = await engine.store.create_run("EUR_USD", "M5", "paper")
    await engine._warm_history()  # type: ignore[attr-defined]

    await engine.broker.place_order(
        run_id=engine.current_run.id,
        instrument="EUR_USD",
        direction="long",
        price=1.0,
        confidence=1.0,
    )

    closed = await engine.broker.update_positions(
        engine.current_run.id,
        instrument="EUR_USD",
        price=1.0 * (1 + settings.take_profit_pct * 2),
    )

    assert closed, "Position should close on take profit"
