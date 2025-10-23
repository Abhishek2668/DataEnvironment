from __future__ import annotations

from dataclasses import dataclass

from forex.utils.math import pip_size, units_for_risk


@dataclass
class RiskParameters:
    equity: float
    risk_pct: float
    stop_distance_pips: float
    instrument: str


def position_size(params: RiskParameters) -> int:
    return units_for_risk(
        equity=params.equity,
        risk_pct=params.risk_pct,
        stop_distance_pips=params.stop_distance_pips,
        instrument=params.instrument,
    )


__all__ = ["RiskParameters", "position_size"]
