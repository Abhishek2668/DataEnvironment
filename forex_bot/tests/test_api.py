import asyncio
from typing import Any

import pendulum
import pytest
import pytest_asyncio
from httpx import AsyncClient

from forex.api import create_app
from forex.config import Settings
from forex.data.candles_store import CandleStore
from forex.realtime.bus import EventBus
from forex.realtime.live import LiveRunConfig


class DummyBroker:
    name = "paper"

    async def get_instruments(self) -> list[dict[str, Any]]:
        return [{"name": "EUR_USD"}]

    async def get_account(self) -> dict[str, Any]:
        return {"balance": 100000.0, "equity": 100000.0}

    async def get_orders(self) -> list[dict[str, Any]]:
        return []

    async def get_open_positions(self) -> list[dict[str, Any]]:
        return []

    async def place_order(self, order: Any) -> dict[str, Any]:  # pragma: no cover - not used in smoke tests
        return {"order": order}

    async def cancel_order(self, order_id: str) -> None:  # pragma: no cover - not used in smoke tests
        return None

    async def price_stream(self, instruments):  # pragma: no cover - streaming not used in smoke tests
        while True:
            await asyncio.sleep(0.01)
            yield pendulum.now("UTC")


class DummyRunner:
    def __init__(self) -> None:
        self.started: LiveRunConfig | None = None
        self.stopped = False

    async def start(self, config: LiveRunConfig) -> str:
        self.started = config
        return "run-1"

    async def stop(self) -> None:
        self.stopped = True


@pytest_asyncio.fixture()
async def api_client():
    settings = Settings(broker="paper", dash_token="test-token", api_host="127.0.0.1", api_port=8000)
    store = CandleStore("sqlite:///:memory:")
    runner = DummyRunner()
    app = create_app(settings=settings, broker=DummyBroker(), candle_store=store, event_bus=EventBus(), live_runner=runner)
    async with AsyncClient(app=app, base_url="http://test") as client:
        client.runner = runner  # type: ignore[attr-defined]
        yield client


@pytest.mark.asyncio()
async def test_health_returns_ok(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio()
async def test_run_live_requires_token(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/run-live", json={"strategy": "sma", "instrument": "EUR_USD", "granularity": "M5", "risk": 0.5})
    assert response.status_code == 401


@pytest.mark.asyncio()
async def test_run_live_starts_runner(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/run-live",
        json={
            "strategy": "sma",
            "instrument": "EUR_USD",
            "granularity": "M5",
            "risk": 0.5,
            "sl": 10,
            "spread_pips": 0.8,
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "started"
    runner: DummyRunner = api_client.runner  # type: ignore[attr-defined]
    assert runner.started is not None
    assert runner.started.instrument == "EUR_USD"


@pytest.mark.asyncio()
async def test_stop_live_calls_runner(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/stop-live", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    runner: DummyRunner = api_client.runner  # type: ignore[attr-defined]
    assert runner.stopped is True
