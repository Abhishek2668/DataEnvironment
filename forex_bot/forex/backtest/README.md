# Backtest Engine (`forex/backtest`)

The backtest package replays historical candle data through strategy instances to
evaluate performance offline.  Use the following map to understand the module
layout:

| File | Purpose |
| --- | --- |
| `__init__.py` | Exposes convenience imports for the backtest package. |
| `engine.py` | Defines the `CandleBar`, `BacktestConfig`, `BacktestResult`, and `Backtester` classes that drive simulations. |
| `metrics.py` | Computes portfolio statistics (CAGR, drawdowns, Sharpe/Sortino-like metrics) from trade/equity histories. |
| `reports.py` | Writes JSON and CSV reports summarising runs and metrics. |

## Execution Flow

1. **Prepare candles** as `CandleBar` instances (e.g. from `CandleStore`).
2. **Instantiate a strategy** via `strategy.registry.create_strategy()`.
3. **Configure the run** with `BacktestConfig` (instrument, risk, spread, etc.).
4. **Run `Backtester.run()`** to iterate candles, trigger strategy callbacks,
   and record simulated trades.
5. **Generate reports** with `reports.write_reports()` to persist the results to
   disk for analysis or regression testing.

The tests in `tests/test_backtest_engine.py` showcase how to exercise the engine
with deterministic candles.
