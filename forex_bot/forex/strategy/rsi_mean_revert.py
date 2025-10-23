from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

import numpy as np

from forex.strategy.base import Signal, Strategy, StrategyContext
from forex.utils.math import atr
from forex.utils.types import Price


def rsi(values: list[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    deltas = np.diff(values)
    ups = np.clip(deltas, 0, None)
    downs = np.clip(-deltas, 0, None)
    roll_up = np.mean(ups[-period:])
    roll_down = np.mean(downs[-period:])
    if roll_down == 0:
        return 100.0
    rs = roll_up / roll_down
    return 100 - 100 / (1 + rs)


@dataclass
class RSIMeanRevertConfig:
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    atr_period: int = 14
    atr_multiplier: float = 1.5


class RSIMeanRevertStrategy(Strategy):
    name = "rsi"

    def __init__(self, config: RSIMeanRevertConfig | None = None) -> None:
        self.config = config or RSIMeanRevertConfig()
        self.context: StrategyContext | None = None
        self.prices: Deque[float] = deque(maxlen=200)
        self.last_signal: Optional[Signal] = None

    def on_startup(self, context: StrategyContext) -> None:
        self.context = context
        self.prices.clear()
        self.last_signal = None

    def on_price_tick(self, price: Price) -> None:
        self.prices.append(price.mid)

    def on_bar_close(self, price: Price) -> None:
        prices_list = list(self.prices)
        value = rsi(prices_list, self.config.period)
        if value is None:
            return
        try:
            volatility = atr(prices_list, self.config.atr_period)
        except ValueError:
            volatility = None
        if value < self.config.oversold and (not self.last_signal or self.last_signal.side != "buy"):
            reason = "rsi_oversold"
            if volatility is not None:
                reason += "_vol"
            self.last_signal = Signal("buy", self.config.oversold - value, reason)
        elif value > self.config.overbought and (not self.last_signal or self.last_signal.side != "sell"):
            reason = "rsi_overbought"
            if volatility is not None:
                reason += "_vol"
            self.last_signal = Signal("sell", value - self.config.overbought, reason)

    def on_stop(self) -> None:
        self.prices.clear()

    def get_signal(self) -> Optional[Signal]:
        return self.last_signal


__all__ = ["RSIMeanRevertStrategy", "RSIMeanRevertConfig", "rsi"]
