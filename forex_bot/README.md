# Forex Paper Trading Bot

A modular, production-ready forex paper trading toolkit supporting OANDA v20 practice accounts with extensible broker abstractions, deterministic strategies, and CLI utilities for live paper trading and backtesting.

## Features

- Broker abstraction with OANDA v20 practice implementation and local paper simulator
- Strategy engine with SMA crossover and RSI mean reversion examples
- Risk management helpers for pip calculations and sizing
- SQLite candle store with SQLAlchemy models
- Candle-based backtester producing metrics and CSV/JSON reports
- Typer-powered CLI with commands for live runs, backtests, importing candles, and viewing metrics
- Structured JSON logging to stdout and rotating log files
- Configurable via `.env` using `pydantic-settings`
- Docker and Docker Compose for local execution

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- OANDA practice account and API token (for broker operations)

## Setup

```bash
cd forex_bot
poetry install
cp .env.example .env
# Edit .env with your OANDA practice credentials
```

## Running the CLI

Activate the Poetry shell or use `poetry run`:

```bash
poetry run forex backtest --strategy rsi --instrument EUR_USD --granularity M5 --risk 0.5 --spread-pips 0.8 --data-csv sample.csv
poetry run forex import-candles --instrument EUR_USD --granularity H1 --days 30
poetry run forex run-live --strategy sma --instrument USD_JPY --granularity M1 --risk 0.25 --max-trades 2
poetry run forex show-metrics --run-id last
```

## Docker

Build and run services using Docker Compose:

```bash
docker compose build
docker compose run forex backtest --strategy rsi --instrument EUR_USD --granularity M5 --risk 0.5
```

## Testing

```bash
poetry run pytest
```

## Risk Disclaimer

This project is for educational and paper-trading purposes only. Do **not** use with live funds. Always verify strategies in simulation before trading real money.
