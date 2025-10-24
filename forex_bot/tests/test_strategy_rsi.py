from datetime import datetime, timezone

from forex.strategy.rsi_mean_revert import RSIMeanRevertStrategy
from forex.strategy.base import StrategyContext
from forex.utils.types import Price


def make_price(value: float) -> Price:
    return Price(instrument="EUR_USD", bid=value - 0.00005, ask=value + 0.00005, time=datetime.now(tz=timezone.utc))


def test_rsi_strategy_signal():
    strat = RSIMeanRevertStrategy()
    context = StrategyContext(instrument="EUR_USD", granularity="M1", risk_pct=1.0, max_positions=1)
    strat.on_startup(context)
    base = 1.2
    for i in range(40):
        if i < 20:
            level = base - 0.0008 * i
        else:
            level = base - 0.016 + 0.0006 * (i - 20)
        swing = 0.00025 if i % 2 == 0 else -0.00025
        price = make_price(level + swing)
        strat.on_price_tick(price)
        strat.on_bar_close(price)
    signal = strat.get_signal()
    assert signal is not None
    assert signal.side in {"buy", "sell"}
