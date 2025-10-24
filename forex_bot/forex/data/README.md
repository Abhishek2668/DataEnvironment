# Data Persistence (`forex/data`)

This package defines the SQLAlchemy models and data-access helpers used by the
backend.  Storage defaults to a SQLite database (`forex.db`) but any SQLAlchemy
engine can be injected.

| File | Purpose |
| --- | --- |
| `__init__.py` | Exposes the `CandleStore` and `RunStore` classes. |
| `candles_store.py` | Repository for inserting and querying candle data with idempotent upserts. |
| `models.py` | SQLAlchemy declarative models (candles, trades, equity curves, runs, metrics). |
| `run_store.py` | Persists backtest/live run metadata, metrics, and summaries. |

## Typical Usage

- **Candle ingestion**: `CandleStore.upsert_candles()` stores broker candles and
  avoids duplicates by `(instrument, time, granularity)`.
- **Run lifecycle**: `RunStore.start_run()` records metadata when a live or
  backtest session begins, `finish_run()` updates the status, and
  `save_metrics()` stores aggregated metrics/equity curves.
- **Analytics**: `RunStore.get_metrics()` and `.list_runs()` feed the API
  responses displayed on the dashboard.

All stores open short-lived SQLAlchemy sessions via context managers to keep
transactions isolated and explicit.
