from datetime import datetime, timezone

from forex.strategy.sma_crossover import SMACrossoverStrategy
from forex.strategy.base import StrategyContext
from forex.utils.types import Price


def make_price(value: float) -> Price:
    return Price(instrument="EUR_USD", bid=value - 0.00005, ask=value + 0.00005, time=datetime.now(tz=timezone.utc))


def test_sma_crossover_signal():
    strat = SMACrossoverStrategy()
    context = StrategyContext(instrument="EUR_USD", granularity="M1", risk_pct=1.0, max_positions=1)
    strat.on_startup(context)
    for value in [1.0 + i * 0.0001 for i in range(50)]:
        price = make_price(value)
        strat.on_price_tick(price)
        strat.on_bar_close(price)
    signal = strat.get_signal()
    assert signal is not None
    assert signal.side in {"buy", "sell"}
