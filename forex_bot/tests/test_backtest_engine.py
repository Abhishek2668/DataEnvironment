from datetime import datetime, timedelta, timezone

from forex.backtest.engine import BacktestConfig, Backtester, CandleBar
from forex.strategy.sma_crossover import SMACrossoverStrategy


def make_candles(count: int) -> list[CandleBar]:
    candles = []
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 1.1
    for i in range(count):
        price += 0.0001
        candles.append(
            CandleBar(
                time=base_time + timedelta(minutes=i),
                open=price,
                high=price + 0.0002,
                low=price - 0.0002,
                close=price,
                volume=1000,
            )
        )
    return candles


def test_backtester_runs(tmp_path):
    config = BacktestConfig(
        instrument="EUR_USD",
        granularity="M1",
        risk_pct=0.5,
        max_positions=1,
    )
    strategy = SMACrossoverStrategy()
    backtester = Backtester(strategy, config)
    result = backtester.run(make_candles(60))
    assert "cagr" in result.metrics
    assert result.equity_curve
