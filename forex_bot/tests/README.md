# Test Suite (`forex_bot/tests`)

Pytest files in this directory provide coverage for critical backend features.
Use the table below to understand what each module verifies.

| File | Coverage |
| --- | --- |
| `test_api.py` | Exercises FastAPI routes using the paper simulator, including config, strategies, and run management endpoints. |
| `test_backtest_engine.py` | Validates the `Backtester` run loop, trade generation, and metrics aggregation. |
| `test_broker_oanda.py` | Mocks HTTP requests to confirm the OANDA adapter builds URLs, headers, and payloads correctly. |
| `test_math.py` | Ensures utility math functions (pip sizing, ATR, risk calculations) behave as expected. |
| `test_strategy_rsi.py` | Covers RSI mean-reversion signal generation across oversold/overbought scenarios. |
| `test_strategy_sma.py` | Covers SMA crossover behaviour and spread threshold handling. |

Run `poetry run pytest` from the project root or via `make test`.
