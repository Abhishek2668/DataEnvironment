# Forex Backend Package (`forex/`)

This package hosts the Python runtime that powers the paper-trading backend.
It is organised by domain concern so each module has a clear responsibility.
Use this document to understand how the files collaborate and where to locate
logic when adding features.

## Module Map

| File | Purpose |
| --- | --- |
| `__init__.py` | Marks the directory as a package and exposes high-level exports. |
| `api.py` | Defines the FastAPI application, request models, dependency wiring, and REST/SSE endpoints. |
| `cli.py` | Typer-powered command-line entry points for running the API, backtests, and utility tasks. |
| `config.py` | Pydantic settings loader that validates the environment, protects against live trading, and exposes runtime configuration. |
| `logging_config.py` | Centralised logger initialisation shared across modules. |
| `utils/` | Math, time, and type helpers used by strategies, execution, and tests. |
| `strategy/` | Strategy protocol, registry, and concrete strategy implementations. |
| `broker/` | Broker interface and adapters (OANDA v20 practice + internal paper simulator). |
| `execution/` | Services that turn strategy signals into executable orders while enforcing risk constraints. |
| `realtime/` | Event bus and live runner orchestration for streaming market data and managing active sessions. |
| `backtest/` | Backtesting engine, metrics, and reporting utilities. |
| `data/` | SQLAlchemy models and repositories for candles and run metadata. |

Each subpackage has its own README with detailed breakdowns.

## Request/Response Models

The API defines several Pydantic models:

- `LiveRunRequest` (start a live paper-trading run)
- `BacktestRequest` (launch backtests with optional parameter overrides)
- `OrderCreateRequest` and `CancelOrderRequest`

These models validate JSON payloads, enforce defaults, and provide aliasing for
`sl`/`tp` abbreviations.  See `api.py` for the full schema definitions.

## Dependency Wiring

`create_app()` in `api.py` is the central factory.  It wires together:

1. **Settings** from `config.get_settings()`
2. **Broker instance** via `create_broker()` with a fallback to the simulator if
   OANDA auth fails
3. **Persistence** using `CandleStore` and `RunStore`
4. **Realtime infrastructure** using `EventBus` and `LiveRunner`
5. **Strategy registry** from `strategy/registry.py`

This design keeps runtime configuration injectable for tests (see `tests/` for
examples).

## CLI Entry Points

`cli.py` exposes Typer commands:

- `forex api` runs the FastAPI server
- `forex backtest` executes configured strategies against stored candles
- `forex ingest` populates the candle store from the broker

The CLI is optional but provides parity with the Makefile/shell scripts.

## Data Flow Summary

1. **Market data** arrives through broker adapters (`broker/`).
2. **Realtime runners** publish updates to the `EventBus` while persisting to
   `RunStore`.
3. **Strategies** consume price ticks, emit signals, and the execution layer
   (`execution/`) converts signals into order requests.
4. **Backtests** replay `CandleBar` sequences from `backtest/` to evaluate
   strategies with historical data.
5. **API endpoints** expose current account state, open orders, positions,
   available strategies, stored runs, metrics, and streaming logs.

Continue into the subdirectory READMEs to learn about their internals.
