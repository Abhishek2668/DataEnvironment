from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator, Iterable, Protocol, Sequence

from forex.utils.types import OrderRequest, Price


class Broker(ABC):
    name: str

    @abstractmethod
    async def get_account(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def get_instruments(self) -> Sequence[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_prices(self, instruments: Iterable[str]) -> Sequence[Price]:
        raise NotImplementedError

    @abstractmethod
    async def price_stream(self, instruments: Iterable[str]) -> AsyncIterator[Price]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_open_positions(self) -> Sequence[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_orders(self) -> Sequence[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        instrument: str,
        granularity: str,
        start: datetime | None = None,
        end: datetime | None = None,
        count: int | None = None,
    ) -> Sequence[dict]:
        raise NotImplementedError


class BrokerFactory(Protocol):
    async def __call__(self) -> Broker:
        ...


__all__ = ["Broker", "BrokerFactory"]
