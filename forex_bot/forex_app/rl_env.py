"""Gymnasium environment for FX candles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - optional dependency
    import gymnasium as gym
    import numpy as np
except Exception:  # pragma: no cover - fallback placeholder
    gym = None
    np = None  # type: ignore[assignment]

from .models import Candle


@dataclass(slots=True)
class FXEnvConfig:
    window: int = 50
    spread: float = 0.0001


class FXTradingEnv:  # type: ignore[misc]
    """Minimal environment modelling FX price changes for PPO training."""

    metadata = {"render_modes": []}

    def __init__(self, candles: list[Candle], config: FXEnvConfig | None = None) -> None:
        if gym is None or np is None:  # pragma: no cover - optional dependency
            raise RuntimeError("gymnasium is required to use FXTradingEnv")
        super().__init__()
        self.candles = candles
        self.config = config or FXEnvConfig()
        self.index = self.config.window
        self.action_space = gym.spaces.Discrete(3)
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(self.config.window, 5))
        self.position = 0
        self.equity = 1.0

    def _window(self) -> np.ndarray:
        window = self.candles[self.index - self.config.window : self.index]
        data = np.array([[c.open, c.high, c.low, c.close, c.volume] for c in window], dtype=np.float32)
        return data

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:  # type: ignore[override]
        super().reset(seed=seed)
        self.index = self.config.window
        self.position = 0
        self.equity = 1.0
        return self._window(), {}

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:  # type: ignore[override]
        if self.index >= len(self.candles) - 1:
            return self._window(), 0.0, True, False, {}
        prev = self.candles[self.index - 1]
        current = self.candles[self.index]
        price_change = (current.close - prev.close) / prev.close
        reward = 0.0
        if action == 1:  # long
            reward = price_change - self.config.spread
        elif action == 2:  # short
            reward = -price_change - self.config.spread
        self.equity *= 1 + reward
        self.index += 1
        done = self.index >= len(self.candles)
        return self._window(), reward, done, False, {"equity": self.equity}

    def render(self) -> None:  # pragma: no cover - no rendering
        return None


__all__ = ["FXTradingEnv", "FXEnvConfig"]
