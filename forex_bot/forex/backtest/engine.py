from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np

from forex.backtest.metrics import compute_metrics
from forex.logging_config import get_logger
from forex.strategy.base import Strategy, StrategyContext
from forex.utils.types import Price

logger = get_logger(__name__)


@dataclass
class CandleBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_price(self, instrument: str, spread: float) -> Price:
        bid = self.close - spread / 2
        ask = self.close + spread / 2
        metadata = {
            "bar": {
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
            }
        }
        return Price(instrument=instrument, bid=bid, ask=ask, time=self.time, metadata=metadata)


@dataclass
class BacktestConfig:
    instrument: str
    granularity: str
    risk_pct: float
    max_positions: int
    spread: float = 0.0002
    slippage: float = 0.00005
    initial_equity: float = 100000.0
    risk_per_trade_pips: float = 20.0


@dataclass
class BacktestResult:
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class Backtester:
    def __init__(self, strategy: Strategy, config: BacktestConfig) -> None:
        self.strategy = strategy
        self.config = config
        self.equity = config.initial_equity
        self.positions: list[dict] = []

    def run(self, candles: Sequence[CandleBar]) -> BacktestResult:
        context = StrategyContext(
            instrument=self.config.instrument,
            granularity=self.config.granularity,
            risk_pct=self.config.risk_pct,
            max_positions=self.config.max_positions,
        )
        self.strategy.on_startup(context)
        equity_curve: list[dict] = []
        trades: list[dict] = []
        returns: list[float] = []
        for candle in candles:
            price = candle.to_price(self.config.instrument, self.config.spread)
            self.strategy.on_price_tick(price)
            self.strategy.on_bar_close(price)
            signal = getattr(self.strategy, "get_signal", lambda: None)()
            if signal and len(self.positions) < self.config.max_positions:
                direction = 1 if signal.side == "buy" else -1
                entry_price = price.ask if direction > 0 else price.bid
                entry_price += self.config.slippage * direction
                risk_per_unit = self.config.risk_per_trade_pips * self.config.spread
                if risk_per_unit <= 0:
                    risk_per_unit = 0.0001
                units = max(int((self.config.initial_equity * (self.config.risk_pct / 100)) / risk_per_unit), 1)
                self.positions.append(
                    {
                        "direction": direction,
                        "entry_price": entry_price,
                        "units": units,
                        "time": candle.time,
                    }
                )
                logger.info(
                    "backtest_trade_open",
                    extra={"instrument": self.config.instrument, "side": signal.side, "units": units, "time": candle.time.isoformat()},
                )
            closed_positions: list[dict] = []
            for position in self.positions:
                direction = position["direction"]
                exit_price = price.bid if direction > 0 else price.ask
                exit_price -= self.config.slippage * direction
                pnl = (exit_price - position["entry_price"]) * direction * position["units"]
                if abs(pnl) > self.config.initial_equity * 0.02:
                    closed_positions.append(position)
                    trade = {
                        "entry_price": position["entry_price"],
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "direction": direction,
                        "opened_at": position["time"],
                        "closed_at": candle.time,
                    }
                    trades.append(trade)
                    self.equity += pnl
                    returns.append(pnl / self.equity)
            for position in closed_positions:
                self.positions.remove(position)
            equity_curve.append({"time": candle.time, "equity": self.equity})
        metrics = compute_metrics(trades, equity_curve, self.config.initial_equity)
        self.strategy.on_stop()
        return BacktestResult(trades=trades, equity_curve=equity_curve, metrics=metrics)


__all__ = ["Backtester", "BacktestConfig", "BacktestResult", "CandleBar"]
