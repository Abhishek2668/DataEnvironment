from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Iterable, Sequence

import httpx
from tenacity import RetryError, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from forex.config import get_settings
from forex.logging_config import get_logger
from forex.utils.time import utc_now
from forex.utils.types import OrderRequest, Price

OANDA_API = "https://api-fxpractice.oanda.com/v3"
OANDA_STREAM = "https://stream-fxpractice.oanda.com/v3"

logger = get_logger(__name__)


class OandaError(Exception):
    pass


def _headers() -> dict[str, str]:
    settings = get_settings()
    token = settings.oanda_api_token.get_secret_value() if settings.oanda_api_token else None
    if not token:
        msg = "OANDA_API_TOKEN is required"
        raise OandaError(msg)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=20.0), headers=_headers())


class OandaBroker:
    name = "oanda"

    def __init__(self) -> None:
        self.settings = get_settings(reload=True)
        if not self.settings.oanda_account_id:
            msg = "OANDA_ACCOUNT_ID is required"
            raise OandaError(msg)
        if not (self.settings.oanda_api_token and self.settings.oanda_api_token.get_secret_value()):
            msg = "OANDA_API_TOKEN is required"
            raise OandaError(msg)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(), retry=retry_if_exception_type(httpx.HTTPError))
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        async with _client() as client:
            response = await client.request(method, f"{OANDA_API}{path}", **kwargs)
            if response.status_code == 429:
                raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
            response.raise_for_status()
            return response.json()

    async def get_account(self) -> dict:
        data = await self._request("GET", f"/accounts/{self.settings.oanda_account_id}")
        return data.get("account", {})

    async def get_instruments(self) -> Sequence[dict]:
        data = await self._request("GET", f"/accounts/{self.settings.oanda_account_id}/instruments")
        return data.get("instruments", [])

    async def get_prices(self, instruments: Iterable[str]) -> Sequence[Price]:
        params = {"instruments": ",".join(instruments)}
        data = await self._request("GET", "/pricing", params=params, headers={"AccountID": self.settings.oanda_account_id})
        prices: list[Price] = []
        for item in data.get("prices", []):
            prices.append(
                Price(
                    instrument=item["instrument"],
                    bid=float(item["bids"][0]["price"]),
                    ask=float(item["asks"][0]["price"]),
                    time=datetime.fromisoformat(item["time"].replace("Z", "+00:00")),
                )
            )
        return prices

    async def price_stream(self, instruments: Iterable[str]) -> AsyncIterator[Price]:
        params = {"instruments": ",".join(instruments), "snapshot": "false"}
        async with httpx.AsyncClient(timeout=None, headers=_headers()) as client:
            async with client.stream(
                "GET",
                f"{OANDA_STREAM}/accounts/{self.settings.oanda_account_id}/pricing/stream",
                params=params,
            ) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        payload = httpx.Response(200, text=line).json()
                    except ValueError:
                        continue
                    if payload.get("type") != "PRICE":
                        continue
                    yield Price(
                        instrument=payload["instrument"],
                        bid=float(payload["bids"][0]["price"]),
                        ask=float(payload["asks"][0]["price"]),
                        time=datetime.fromisoformat(payload["time"].replace("Z", "+00:00")),
                    )

    async def place_order(self, order: OrderRequest) -> dict:
        body = {
            "order": {
                "units": str(order.units if order.side == "buy" else -order.units),
                "instrument": order.instrument,
                "type": "MARKET",
                "timeInForce": order.time_in_force,
            }
        }
        if order.take_profit:
            body["order"]["takeProfitOnFill"] = {"price": f"{order.take_profit:.5f}"}
        if order.stop_loss:
            body["order"]["stopLossOnFill"] = {"price": f"{order.stop_loss:.5f}"}
        return await self._request(
            "POST",
            f"/accounts/{self.settings.oanda_account_id}/orders",
            json=body,
        )

    async def cancel_order(self, order_id: str) -> None:
        await self._request(
            "PUT",
            f"/accounts/{self.settings.oanda_account_id}/orders/{order_id}/cancel",
        )

    async def get_open_positions(self) -> Sequence[dict]:
        data = await self._request("GET", f"/accounts/{self.settings.oanda_account_id}/openPositions")
        return data.get("positions", [])

    async def get_orders(self) -> Sequence[dict]:
        data = await self._request("GET", f"/accounts/{self.settings.oanda_account_id}/orders")
        return data.get("orders", [])

    async def get_candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None = None,
        end: datetime | None = None,
        count: int | None = None,
    ) -> Sequence[dict]:
        params: dict[str, Any] = {"granularity": granularity}
        if start:
            params["from"] = start.isoformat()
        if end:
            params["to"] = end.isoformat()
        if count:
            params["count"] = count
        data = await self._request("GET", f"/instruments/{instrument}/candles", params=params)
        return data.get("candles", [])


__all__ = ["OandaBroker", "OandaError"]
