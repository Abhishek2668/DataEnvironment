from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from forex.backtest.engine import BacktestResult


def write_reports(result: BacktestResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    trades_df = pd.DataFrame(result.trades)
    equity_df = pd.DataFrame(result.equity_curve)
    trades_df.to_csv(output_dir / "trades.csv", index=False)
    equity_df.to_csv(output_dir / "equity_curve.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(result.metrics, indent=2), encoding="utf-8")


__all__ = ["write_reports"]
