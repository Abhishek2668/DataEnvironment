from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

PIP_POSITION = {
    "JPY": 0.01,
}


def pip_size(instrument: str) -> float:
    quote = instrument.split("_")[1]
    return PIP_POSITION.get(quote, 0.0001)


def pip_value(instrument: str, units: int) -> float:
    return pip_size(instrument) * abs(units)


def units_for_risk(
    equity: float,
    risk_pct: float,
    stop_distance_pips: float,
    instrument: str,
) -> int:
    if risk_pct <= 0 or stop_distance_pips <= 0:
        msg = "risk_pct and stop_distance_pips must be positive"
        raise ValueError(msg)
    risk_amount = equity * (risk_pct / 100)
    pip_val = pip_size(instrument)
    units = risk_amount / (stop_distance_pips * pip_val)
    return int(np.floor(units))


def atr(values: Iterable[float], period: int) -> float:
    arr = np.array(list(values), dtype=float)
    if len(arr) < period:
        msg = "Not enough data for ATR"
        raise ValueError(msg)
    diffs = np.abs(np.diff(arr))
    atr_values = np.convolve(diffs, np.ones(period), "valid") / period
    return float(atr_values[-1])


@dataclass
class EquityMetrics:
    returns: np.ndarray

    def cagr(self, periods_per_year: int = 252) -> float:
        cumulative = self.returns + 1
        total_return = np.prod(cumulative)
        n_periods = len(self.returns)
        if n_periods == 0:
            return 0.0
        years = n_periods / periods_per_year
        return total_return ** (1 / years) - 1

    def max_drawdown(self) -> float:
        cumulative = np.cumprod(self.returns + 1)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - peak) / peak
        return float(drawdowns.min())

    def sharpe(self, risk_free: float = 0.0, periods_per_year: int = 252) -> float:
        excess = self.returns - risk_free / periods_per_year
        std = np.std(excess)
        if std == 0:
            return 0.0
        return np.sqrt(periods_per_year) * excess.mean() / std

    def sortino(self, risk_free: float = 0.0, periods_per_year: int = 252) -> float:
        downside = np.minimum(self.returns - risk_free / periods_per_year, 0)
        downside_std = np.sqrt(np.mean(downside**2))
        if downside_std == 0:
            return 0.0
        return np.sqrt(periods_per_year) * np.mean(self.returns) / downside_std


__all__ = [
    "atr",
    "EquityMetrics",
    "pip_size",
    "pip_value",
    "units_for_risk",
]
