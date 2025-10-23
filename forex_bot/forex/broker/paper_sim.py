from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import AsyncIterator, Deque, Iterable, Sequence

from forex.utils.time import utc_now
from forex.utils.types import OrderRequest, Price


class PaperSimBroker:
    name = "paper"

    def __init__(self, spread_pips: float = 0.8) -> None:
        self.spread_pips = spread_pips
        self.account = {"balance": 100000.0, "currency": "USD"}
        self.positions: list[dict] = []
        self.orders: Deque[dict] = deque()

    async def get_account(self) -> dict:
        return self.account

    async def get_instruments(self) -> Sequence[dict]:
        return []

    async def get_prices(self, instruments: Iterable[str]) -> Sequence[Price]:
        now = utc_now()
        prices: list[Price] = []
        for instrument in instruments:
            mid = 1.0
            spread = self.spread_pips * 0.0001
            prices.append(Price(instrument=instrument, bid=mid - spread / 2, ask=mid + spread / 2, time=now))
        return prices

    async def price_stream(self, instruments: Iterable[str]) -> AsyncIterator[Price]:
        while True:
            for price in await self.get_prices(instruments):
                yield price

    async def place_order(self, order: OrderRequest) -> dict:
        price = 1.0
        if order.side == "buy":
            self.positions.append({"instrument": order.instrument, "units": order.units, "price": price})
        else:
            self.positions.append({"instrument": order.instrument, "units": -order.units, "price": price})
        trade_id = f"SIM-{len(self.positions)}"
        return {"orderFillTransaction": {"id": trade_id, "price": price}}

    async def cancel_order(self, order_id: str) -> None:
        return None

    async def get_open_positions(self) -> Sequence[dict]:
        return self.positions

    async def get_orders(self) -> Sequence[dict]:
        return list(self.orders)

    async def get_candles(self, instrument: str, granularity: str, start=None, end=None, count=None) -> Sequence[dict]:
        return []


__all__ = ["PaperSimBroker"]
