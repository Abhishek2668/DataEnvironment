from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from forex.utils.types import Price


@dataclass
class StrategyContext:
    instrument: str
    granularity: str
    risk_pct: float
    max_positions: int


class Strategy(Protocol):
    name: str

    def on_startup(self, context: StrategyContext) -> None:
        ...

    def on_price_tick(self, price: Price) -> None:
        ...

    def on_bar_close(self, price: Price) -> None:
        ...

    def on_stop(self) -> None:
        ...


class Signal:
    def __init__(
        self,
        side: str,
        strength: float,
        reason: str,
        *,
        stop_distance_pips: float | None = None,
        take_profit_pips: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.side = side
        self.strength = strength
        self.reason = reason
        self.stop_distance_pips = stop_distance_pips
        self.take_profit_pips = take_profit_pips
        self.metadata = metadata or {}


__all__ = ["Strategy", "StrategyContext", "Signal"]
