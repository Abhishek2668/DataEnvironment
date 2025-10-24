from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient

from forex_app.routes import create_app
from forex_app.settings import Settings


@pytest.mark.asyncio
async def test_api_lifecycle(tmp_path) -> None:
    settings = Settings(
        DB_PATH=tmp_path / "trading.db",
        DATA_DIR=tmp_path / "data",
        HEARTBEAT_INTERVAL_SECONDS=0.01,
    )
    app = create_app(settings)
    app.state.news_service.fetch_news = lambda: asyncio.sleep(0, result=[])  # type: ignore[assignment]

    async with AsyncClient(app=app, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        payload = health.json()
        assert payload["status"] == "ok"

        start_resp = await client.post("/api/session/start", json={"instrument": "EUR_USD", "tf": "M5"})
        assert start_resp.status_code == 200
        run_id = start_resp.json()["run_id"]
        assert run_id

        await asyncio.sleep(0.05)

        status_resp = await client.get("/api/status")
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload["run_id"] == run_id

        stop_resp = await client.post("/api/session/stop")
        assert stop_resp.status_code == 200

        metrics_resp = await client.get("/api/metrics")
        assert metrics_resp.status_code == 200

        settings_resp = await client.post("/api/settings", json={"TRADE_ALLOCATION_PCT": 0.03})
        assert settings_resp.status_code == 200

        backtest_resp = await client.post(
            "/api/backtest/run",
            json={
                "symbol": "EUR_USD",
                "start": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
        )
        assert backtest_resp.status_code == 200
        backtest_payload = backtest_resp.json()
        assert "equity_curve" in backtest_payload
        assert "stats" in backtest_payload

        news_resp = await client.get("/api/news")
        assert news_resp.status_code == 200
