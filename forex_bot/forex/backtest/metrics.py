from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from forex.utils.math import EquityMetrics


def compute_metrics(trades: Iterable[dict], equity_curve: Iterable[dict], initial_equity: float) -> dict:
    trades_list = list(trades)
    equity_list = list(equity_curve)
    if not equity_list:
        return {}
    returns = []
    prev = initial_equity
    for point in equity_list:
        equity = point["equity"]
        returns.append((equity - prev) / prev if prev else 0.0)
        prev = equity
    metrics = EquityMetrics(np.array(returns))
    total_profit = sum(trade["pnl"] for trade in trades_list)
    wins = [trade for trade in trades_list if trade["pnl"] > 0]
    losses = [trade for trade in trades_list if trade["pnl"] <= 0]
    exposure = len(wins) + len(losses)
    per_instrument = defaultdict(float)
    for trade in trades_list:
        per_instrument[trade.get("instrument", "unknown")] += trade["pnl"]
    return {
        "cagr": metrics.cagr(),
        "max_drawdown": metrics.max_drawdown(),
        "sharpe": metrics.sharpe(),
        "sortino": metrics.sortino(),
        "win_rate": len(wins) / len(trades_list) if trades_list else 0,
        "profit_factor": (sum(tr["pnl"] for tr in wins) / abs(sum(tr["pnl"] for tr in losses)) if losses else float("inf"))
        if trades_list
        else 0.0,
        "avg_r": total_profit / len(trades_list) if trades_list else 0,
        "exposure": exposure,
        "per_instrument": dict(per_instrument),
        "total_profit": total_profit,
    }


__all__ = ["compute_metrics"]
