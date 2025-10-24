from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

TimeInForce = Literal["FOK", "GTC", "GFD", "IOC"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market"]


@dataclass(slots=True)
class Price:
    instrument: str
    bid: float
    ask: float
    time: datetime
    metadata: dict[str, Any] | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(slots=True)
class OrderRequest:
    instrument: str
    units: int
    side: OrderSide
    order_type: OrderType = "market"
    stop_loss: float | None = None
    take_profit: float | None = None
    time_in_force: TimeInForce = "FOK"


@dataclass(slots=True)
class Trade:
    instrument: str
    units: int
    price: float
    time: datetime
    pnl: float = 0.0


class PriceStream(Protocol):
    def __iter__(self) -> "PriceStream":
        ...

    def __next__(self) -> Price:
        ...


__all__ = [
    "OrderRequest",
    "OrderSide",
    "OrderType",
    "Price",
    "PriceStream",
    "TimeInForce",
    "Trade",
]
