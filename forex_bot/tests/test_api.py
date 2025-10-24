from __future__ import annotations

import asyncio
import importlib
import sys

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_lifecycle(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "trading.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("LOOP_INTERVAL_SECONDS", "0.01")

    from forex_bot.utils import settings as settings_module

    settings_module.get_settings.cache_clear()  # type: ignore[attr-defined]

    modules_to_reload = [
        "forex_bot.utils.settings",
        "forex_bot.data.candles",
        "forex_bot.engine.core",
        "forex_bot.engine.live_runner",
        "forex_bot.api.session",
        "forex_bot.api.trade",
        "forex_bot.api.status",
        "forex_bot.api.events",
        "forex_bot.main",
    ]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)
        if module_name == "forex_bot.engine.core":
            module.TradingEngine._instance = None  # type: ignore[attr-defined]

    from forex_bot.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        start_resp = await client.post("/api/session/start", json={"instrument": "EUR_USD", "timeframe": "M5"})
        assert start_resp.status_code == 200
        run_id = start_resp.json()["run_id"]

        await asyncio.sleep(0.05)

        status_resp = await client.get("/api/status")
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["run_id"] == run_id

        await asyncio.sleep(0.2)
        force_resp = await client.post("/api/trade/signal/force", json={"direction": "long", "confidence": 1.0})
        assert force_resp.status_code == 200

        stop_resp = await client.post("/api/session/stop")
        assert stop_resp.status_code == 200
