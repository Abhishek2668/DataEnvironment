from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(slots=True)
class SMAState:
    period: int
    values: list[float] = field(default_factory=list)

    def update(self, price: float) -> float | None:
        self.values.append(price)
        if len(self.values) > self.period:
            self.values.pop(0)
        if len(self.values) < self.period:
            return None
        return sum(self.values) / self.period


@dataclass(slots=True)
class EMAState:
    period: int
    value: float | None = None

    def update(self, price: float) -> float:
        alpha = 2 / (self.period + 1)
        if self.value is None:
            self.value = price
        else:
            self.value = (price - self.value) * alpha + self.value
        return self.value


@dataclass(slots=True)
class RSIState:
    period: int
    avg_gain: float | None = None
    avg_loss: float | None = None
    last_price: float | None = None

    def update(self, price: float) -> float | None:
        if self.last_price is None:
            self.last_price = price
            return None
        change = price - self.last_price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        if self.avg_gain is None or self.avg_loss is None:
            self.avg_gain = gain
            self.avg_loss = loss
        else:
            self.avg_gain = ((self.avg_gain * (self.period - 1)) + gain) / self.period
            self.avg_loss = ((self.avg_loss * (self.period - 1)) + loss) / self.period
        self.last_price = price
        if self.avg_loss == 0:
            return 100.0
        if self.avg_gain is None or self.avg_loss is None:
            return None
        rs = self.avg_gain / self.avg_loss
        return 100 - (100 / (1 + rs))


@dataclass(slots=True)
class MACDState:
    fast_period: int
    slow_period: int
    signal_period: int
    ema_fast: EMAState = field(init=False)
    ema_slow: EMAState = field(init=False)
    ema_signal: EMAState = field(init=False)

    def __post_init__(self) -> None:
        self.ema_fast = EMAState(self.fast_period)
        self.ema_slow = EMAState(self.slow_period)
        self.ema_signal = EMAState(self.signal_period)

    def update(self, price: float) -> tuple[float, float, float]:
        fast = self.ema_fast.update(price)
        slow = self.ema_slow.update(price)
        macd_line = fast - slow
        signal_line = self.ema_signal.update(macd_line)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram


@dataclass(slots=True)
class ATRState:
    period: int
    value: float | None = None
    last_close: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        true_range = high - low
        if self.last_close is not None:
            true_range = max(true_range, abs(high - self.last_close), abs(low - self.last_close))
        self.last_close = close
        tr = true_range
        if self.value is None:
            self.value = tr
        else:
            self.value = ((self.value * (self.period - 1)) + tr) / self.period
        return self.value


def pip_value(instrument: str, base_currency: str = "USD") -> float:
    if instrument.endswith("JPY"):
        return 0.01
    return 0.0001


def sma(values: Iterable[float], period: int) -> float | None:
    window = list(values)[-period:]
    if len(window) < period:
        return None
    return sum(window) / period


__all__ = [
    "ATRState",
    "EMAState",
    "MACDState",
    "RSIState",
    "SMAState",
    "pip_value",
    "sma",
]

