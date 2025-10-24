"""Light-weight trading strategy inspired by Murphy's candle analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from forex_bot.data.models import Candle


@dataclass(slots=True)
class Signal:
    direction: str
    confidence: float
    reason: str


class MurphyStrategy:
    """Naive moving-average crossover strategy."""

    def __init__(self, fast_window: int = 8, slow_window: int = 21) -> None:
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate(self, candles: List[Candle]) -> Optional[dict]:
        if len(candles) < self.slow_window:
            return None
        closes = [c.close for c in candles]
        fast = sum(closes[-self.fast_window :]) / self.fast_window
        slow = sum(closes[-self.slow_window :]) / self.slow_window
        distance = abs(fast - slow)
        confidence = min(1.0, distance * 500)
        if fast > slow:
            direction = "long"
            reason = "ma_crossover_long"
        elif fast < slow:
            direction = "short"
            reason = "ma_crossover_short"
        else:
            return None
        if confidence < 0.1:
            return None
        return {"direction": direction, "confidence": confidence, "reason": reason}


__all__ = ["MurphyStrategy", "Signal"]
