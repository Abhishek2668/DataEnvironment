from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(slots=True)
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def direction(self) -> str:
        return "bull" if self.close >= self.open else "bear"


@dataclass(slots=True)
class PatternMatch:
    name: str
    direction: str
    confidence: float


def _as_candles(bars: Iterable[dict]) -> list[Candle]:
    candles: list[Candle] = []
    for bar in bars:
        candles.append(
            Candle(
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=float(bar.get("volume")) if bar.get("volume") is not None else None,
            )
        )
    return candles


def engulfing(bars: Sequence[dict]) -> PatternMatch | None:
    candles = _as_candles(bars[-2:])
    if len(candles) < 2:
        return None
    prev, current = candles
    if current.direction == prev.direction:
        return None
    if current.body <= prev.body:
        return None
    direction = current.direction
    confidence = min(current.body / (prev.body + 1e-9), 3.0)
    return PatternMatch(name="engulfing", direction=direction, confidence=min(confidence / 3, 1.0))


def hammer(bars: Sequence[dict]) -> PatternMatch | None:
    candle = _as_candles(bars[-1:])
    if not candle:
        return None
    c = candle[0]
    lower_wick = c.open - c.low if c.direction == "bull" else c.close - c.low
    upper_wick = c.high - c.close if c.direction == "bull" else c.high - c.open
    if lower_wick < c.body * 2 or upper_wick > c.body:
        return None
    return PatternMatch(name="hammer", direction="bull", confidence=0.6)


def shooting_star(bars: Sequence[dict]) -> PatternMatch | None:
    candle = _as_candles(bars[-1:])
    if not candle:
        return None
    c = candle[0]
    upper_wick = c.high - max(c.open, c.close)
    lower_wick = min(c.open, c.close) - c.low
    if upper_wick < c.body * 2:
        return None
    range_total = c.high - c.low
    if lower_wick > max(c.body * 2, range_total * 0.35):
        return None
    return PatternMatch(name="shooting_star", direction="bear", confidence=0.6)


def doji(bars: Sequence[dict], tolerance: float = 0.1) -> PatternMatch | None:
    candle = _as_candles(bars[-1:])
    if not candle:
        return None
    c = candle[0]
    if c.body > (c.high - c.low) * tolerance:
        return None
    return PatternMatch(name="doji", direction="neutral", confidence=0.4)


def harami(bars: Sequence[dict]) -> PatternMatch | None:
    candles = _as_candles(bars[-2:])
    if len(candles) < 2:
        return None
    prev, current = candles
    if prev.direction == current.direction:
        return None
    if not (min(prev.open, prev.close) <= current.open <= max(prev.open, prev.close)):
        return None
    if not (min(prev.open, prev.close) <= current.close <= max(prev.open, prev.close)):
        return None
    return PatternMatch(name="harami", direction=prev.direction, confidence=0.5)


def morning_star(bars: Sequence[dict]) -> PatternMatch | None:
    candles = _as_candles(bars[-3:])
    if len(candles) < 3:
        return None
    first, second, third = candles
    if first.direction != "bear" or third.direction != "bull":
        return None
    if second.body > first.body * 0.6:
        return None
    if third.close <= (first.open + first.close) / 2:
        return None
    return PatternMatch(name="morning_star", direction="bull", confidence=0.7)


def evening_star(bars: Sequence[dict]) -> PatternMatch | None:
    candles = _as_candles(bars[-3:])
    if len(candles) < 3:
        return None
    first, second, third = candles
    if first.direction != "bull" or third.direction != "bear":
        return None
    if second.body > first.body * 0.6:
        return None
    if third.close >= (first.open + first.close) / 2:
        return None
    return PatternMatch(name="evening_star", direction="bear", confidence=0.7)


def pin_bar(bars: Sequence[dict]) -> PatternMatch | None:
    candle = _as_candles(bars[-1:])
    if not candle:
        return None
    c = candle[0]
    range_total = c.high - c.low
    if range_total == 0:
        return None
    upper_wick = c.high - max(c.open, c.close)
    lower_wick = min(c.open, c.close) - c.low
    if upper_wick / range_total > 0.66 and c.direction == "bear":
        return PatternMatch(name="pin_bar", direction="bear", confidence=0.6)
    if lower_wick / range_total > 0.66 and c.direction == "bull":
        return PatternMatch(name="pin_bar", direction="bull", confidence=0.6)
    return None


PATTERN_FUNCTIONS = {
    "engulfing": engulfing,
    "hammer": hammer,
    "shooting_star": shooting_star,
    "doji": doji,
    "harami": harami,
    "morning_star": morning_star,
    "evening_star": evening_star,
    "pin_bar": pin_bar,
}


def detect_patterns(bars: Sequence[dict], enabled: Iterable[str]) -> list[PatternMatch]:
    matches: list[PatternMatch] = []
    for name in enabled:
        func = PATTERN_FUNCTIONS.get(name)
        if not func:
            continue
        match = func(bars)
        if match:
            matches.append(match)
    return matches


__all__ = [
    "Candle",
    "PatternMatch",
    "PATTERN_FUNCTIONS",
    "detect_patterns",
    "doji",
    "engulfing",
    "evening_star",
    "hammer",
    "harami",
    "morning_star",
    "pin_bar",
    "shooting_star",
]

