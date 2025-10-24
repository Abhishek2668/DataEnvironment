from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from typing import Any, Dict, Iterable

from forex.strategy.rsi_mean_revert import RSIMeanRevertConfig, RSIMeanRevertStrategy
from forex.strategy.sma_crossover import SMACrossoverConfig, SMACrossoverStrategy
from forex.strategy.murphy_candles import MurphyCandlesConfig, MurphyCandlesV1Strategy

StrategyParams = Dict[str, Any]


class UnknownStrategyError(ValueError):
    """Raised when a requested strategy is not registered."""


STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {
    "sma": {"factory": SMACrossoverStrategy, "config": SMACrossoverConfig},
    "rsi": {"factory": RSIMeanRevertStrategy, "config": RSIMeanRevertConfig},
    "murphy_candles_v1": {"factory": MurphyCandlesV1Strategy, "config": MurphyCandlesConfig},
}


def _config_schema(config_cls: type | None) -> list[dict[str, Any]]:
    if not config_cls or not is_dataclass(config_cls):
        return []
    schema: list[dict[str, Any]] = []
    for field in fields(config_cls):
        default = None
        if field.default is not MISSING:
            default = field.default
        elif field.default_factory is not MISSING:  # type: ignore[truthy-function]
            default = field.default_factory()  # type: ignore[misc]
        schema.append(
            {
                "name": field.name,
                "type": getattr(field.type, "__name__", str(field.type)),
                "default": default,
            }
        )
    return schema


def list_strategies() -> list[dict[str, Any]]:
    """Return a serialisable description of available strategies."""

    payload: list[dict[str, Any]] = []
    for name, data in STRATEGY_REGISTRY.items():
        payload.append(
            {
                "name": name,
                "params": _config_schema(data.get("config")),
            }
        )
    return payload


def create_strategy(name: str, params: StrategyParams | None = None):
    """Instantiate a registered strategy with optional parameter overrides."""

    key = name.lower()
    if key not in STRATEGY_REGISTRY:
        raise UnknownStrategyError(f"Unknown strategy '{name}'")
    entry = STRATEGY_REGISTRY[key]
    factory = entry["factory"]
    config_cls = entry.get("config")
    params = params or {}
    if config_cls and is_dataclass(config_cls):
        config_kwargs = {field.name: params[field.name] for field in fields(config_cls) if field.name in params}
        config = config_cls(**config_kwargs)
        return factory(config)  # type: ignore[call-arg]
    return factory()


__all__ = ["create_strategy", "list_strategies", "UnknownStrategyError", "STRATEGY_REGISTRY"]

