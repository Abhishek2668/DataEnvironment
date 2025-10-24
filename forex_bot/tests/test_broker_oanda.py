import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from forex.broker.oanda import OandaBroker, OandaError
from forex.config import Settings


class DummySettings(Settings):
    model_config = Settings.model_config


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("BROKER", "oanda")
    monkeypatch.setenv("OANDA_ENV", "practice")
    monkeypatch.setenv("OANDA_API_TOKEN", "token")
    monkeypatch.setenv("OANDA_ACCOUNT_ID", "acct")
    return Settings()


@pytest.mark.asyncio
async def test_get_account(settings, monkeypatch):
    broker = OandaBroker()
    response = {"account": {"balance": "100000"}}
    with patch("forex.broker.oanda._client") as mock_client:
        async_mock = AsyncMock()
        async_mock.__aenter__.return_value = async_mock
        async_mock.request.return_value = httpx.Response(
            200, json=response, request=httpx.Request("GET", "http://test")
        )
        mock_client.return_value = async_mock
        data = await broker.get_account()
    assert data["balance"] == "100000"


def test_missing_token(monkeypatch):
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)
    with pytest.raises(OandaError):
        OandaBroker()
