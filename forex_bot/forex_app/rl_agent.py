"""RL policy loading and inference utilities."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .models import FeatureSnapshot, Signal, SignalDirection
from .settings import Settings

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from stable_baselines3 import PPO
except Exception:  # pragma: no cover - fallback when package missing
    PPO = None


@dataclass(slots=True)
class RLSignalService:
    settings: Settings
    feature_size: int = 5
    model: Any | None = None

    def __post_init__(self) -> None:
        if PPO is None:
            LOGGER.warning("stable-baselines3 not available; falling back to heuristic signals")
            return
        model_path = Path(self.settings.MODEL_PATH)
        if model_path.exists():
            self.model = PPO.load(model_path)
        else:
            LOGGER.warning("RL model not found at %s; fallback heuristic will be used", model_path)

    def _heuristic_signal(self, features: FeatureSnapshot) -> Signal:
        bullish = features.ema_fast > features.ema_slow and features.rsi > 55
        bearish = features.ema_fast < features.ema_slow and features.rsi < 45
        if bullish and not bearish:
            direction = SignalDirection.LONG
            confidence = min(1.0, 0.6 + (features.rsi - 55) / 100)
        elif bearish and not bullish:
            direction = SignalDirection.SHORT
            confidence = min(1.0, 0.6 + (45 - features.rsi) / 100)
        else:
            direction = SignalDirection.FLAT
            confidence = 0.2
        return Signal(direction=direction, confidence=float(confidence), features=features)

    def predict(self, features: FeatureSnapshot) -> Signal:
        if self.model is None:
            return self._heuristic_signal(features)
        obs = np.array([
            features.returns,
            features.rsi / 100,
            features.ema_fast - features.ema_slow,
            features.atr,
            features.ema_fast,
        ])
        action, _ = self.model.predict(obs, deterministic=True)
        if isinstance(action, (np.ndarray, list)):
            action_value = float(action[0])
        else:
            action_value = float(action)
        if action_value > 0.2:
            direction = SignalDirection.LONG
        elif action_value < -0.2:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.FLAT
        confidence = min(1.0, abs(action_value))
        return Signal(direction=direction, confidence=confidence, features=features)


__all__ = ["RLSignalService"]
