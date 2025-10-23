from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from forex.strategy.base import Signal, Strategy, StrategyContext
from forex.utils.types import Price


@dataclass
class SMACrossoverConfig:
    fast: int = 10
    slow: int = 30
    spread_threshold: float = 0.0005


class SMACrossoverStrategy(Strategy):
    name = "sma"

    def __init__(self, config: SMACrossoverConfig | None = None) -> None:
        self.config = config or SMACrossoverConfig()
        self.context: StrategyContext | None = None
        self.prices: Deque[float] = deque(maxlen=self.config.slow)
        self.last_signal: Optional[Signal] = None

    def _sma(self, window: int) -> Optional[float]:
        if len(self.prices) < window:
            return None
        return sum(list(self.prices)[-window:]) / window

    def on_startup(self, context: StrategyContext) -> None:
        self.context = context
        self.prices.clear()
        self.last_signal = None

    def on_price_tick(self, price: Price) -> None:
        self.prices.append(price.mid)

    def on_bar_close(self, price: Price) -> None:
        if price.spread > self.config.spread_threshold:
            return
        fast = self._sma(self.config.fast)
        slow = self._sma(self.config.slow)
        if fast is None or slow is None:
            return
        if fast > slow and (not self.last_signal or self.last_signal.side != "buy"):
            self.last_signal = Signal("buy", fast - slow, "fast_above_slow")
        elif fast < slow and (not self.last_signal or self.last_signal.side != "sell"):
            self.last_signal = Signal("sell", slow - fast, "fast_below_slow")

    def on_stop(self) -> None:
        self.prices.clear()

    def get_signal(self) -> Optional[Signal]:
        return self.last_signal


__all__ = ["SMACrossoverStrategy", "SMACrossoverConfig"]
