# Forex Paper Trading App (Python + FastAPI + React)

A modular **paper-trading** forex application with an OANDA v20 **Practice** adapter, FastAPI backend, and a React/Vite dashboard. **Live money is disabled by design.**

> **Default timezone:** America/Winnipeg (store timestamps in UTC, format at UI).  
> **Safety:** If a live environment is detected, the API refuses to run.

---

## Table of Contents
- [What’s Inside](#whats-inside)
- [Requirements (macOS)](#requirements-macos)
- [Quick Start (macOS)](#quick-start-macos)
- [Configuration](#configuration)
- [Running the Backend API](#running-the-backend-api)
- [Running the Frontend](#running-the-frontend)
- [Using the App](#using-the-app)
- [Common Commands](#common-commands)
- [Backtesting Examples](#backtesting-examples)
- [Troubleshooting (macOS)](#troubleshooting-macos)
- [Project Structure](#project-structure)
- [Notes & Disclaimers](#notes--disclaimers)

---

## What’s Inside
- **Broker Abstraction:** OANDA Practice via REST + streaming; pluggable broker interface.
- **Strategy Engine:** SMA crossover & RSI mean-reversion (risk%, SL/TP in pips or ATR multiple).
- **Backtester:** Realistic spread/slippage/commission; metrics (CAGR, MDD, Sharpe, Sortino, etc.).
- **Storage:** SQLite + SQLAlchemy (candles, orders, positions, equity).
- **API:** FastAPI + SSE/WS for logs, prices, events.
- **UI:** React (Vite + TS), Tailwind, shadcn/ui, Recharts.
- **Ops:** Poetry, Ruff, Black, Pytest, MyPy; optional Docker.

---

## Requirements (macOS)
You can install everything with Homebrew:

```bash
# If you don't have Homebrew:
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew update

# Python 3.11+ and tooling
brew install python@3.11
python3.11 -m pip install --upgrade pip
pip3.11 install poetry

# Node.js LTS (choose one of the following)
brew install node@20
# or if you prefer nvm:
# brew install nvm && nvm install --lts

# Optional: Docker Desktop (for containerized run)
# https://www.docker.com/products/docker-desktop/


macOS may prompt to install Command Line Tools on first compile:
xcode-select --install
```

## Quick Start (macOS)

Clone your repo (personal branch) and run:

```bash
git clone <your-repo-url>
cd <your-repo-folder>

# 1) Python deps
poetry install

# 2) Node deps (frontend)
cd frontend && npm install && cd ..

# 3) Environment files
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Edit .env with your OANDA Practice credentials and dashboard token:

```bash
# .env
BROKER=oanda
OANDA_ENV=practice
OANDA_API_TOKEN=your_oanda_practice_api_token
OANDA_ACCOUNT_ID=101-001-xxxxxx-xxx
BASE_CURRENCY=CAD
DEFAULT_TIMEZONE=America/Winnipeg

# Dashboard/API
DASH_TOKEN=dev-token
API_HOST=0.0.0.0
API_PORT=8000
```

Ensure frontend points to your backend:

```bash
# frontend/.env
VITE_API_BASE=http://localhost:8000
VITE_DASH_TOKEN=dev-token
```

Start everything in two terminals:

```bash
# Terminal A (API)
make dev-api
# or: scripts/dev_backend.sh

# Terminal B (Frontend)
make dev-ui
# or: scripts/dev_frontend.sh
```

Open the UI: http://localhost:5173

## Configuration

Secrets & config: .env (root) and frontend/.env (UI).

Paper-only guardrails: If OANDA_ENV=live, API returns 409 and refuses to start live trading.

Ports: API 8000, UI 5173. Change via API_PORT and Vite config/env.

## Running the Backend API

You have multiple options:

```bash
# Using Poetry + uvicorn directly
poetry run uvicorn forex.api:app --host 0.0.0.0 --port 8000 --reload

# Using the script (recommended)
scripts/dev_backend.sh

# Using Makefile
make dev-api

# If you wired a Typer CLI entry like `forex api`:
poetry run forex api
```

Health check:

```bash
curl http://localhost:8000/api/health
# -> {"status":"ok"}
```

## Running the Frontend

```bash
cd frontend
npm run dev       # http://localhost:5173
# or, from project root:
make dev-ui
# or:
scripts/dev_frontend.sh
```

Build production assets:

```bash
cd frontend && npm run build
```

## Using the App

Connect: Ensure .env has valid OANDA Practice token & account.

Dashboard: Visit http://localhost:5173 to see balance/equity, logs, and controls.

Start a live (paper) session from the UI (or curl):

```bash
curl -X POST http://localhost:8000/api/run-live \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy":"sma",
    "instrument":"EUR_USD",
    "granularity":"M1",
    "risk":0.25,
    "sl_atr":1,
    "tp_atr":2,
    "spread_pips":0.8
  }'
```

Stop it:

```bash
curl -X POST http://localhost:8000/api/stop-live \
  -H "Authorization: Bearer dev-token"
```

Other handy endpoints:

```
GET /api/account, /api/instruments, /api/orders, /api/positions

Streams (SSE): /api/stream/logs, /api/stream/events, /api/stream/prices?instrument=EUR_USD
```

## Common Commands

```bash
# Install deps
poetry install
(cd frontend && npm install)

# Lint & format
poetry run ruff check .
poetry run ruff format .
poetry run black .

# Type-check & tests
poetry run mypy forex
poetry run pytest -q

# Back up your env files
cp .env .env.local.bak
cp frontend/.env frontend/.env.local.bak

# Makefile shortcuts (added by this repo)
make setup         # Poetry + Node install
make setup-py      # Python deps only
make setup-node    # Frontend deps only
make env           # Copies example env files
make dev           # Runs API + prints instructions for UI
make dev-api       # Backend only
make dev-ui        # Frontend only
make test          # pytest
make lint          # ruff + black
make typecheck     # mypy
make build-ui      # vite build
```

## Backtesting Examples

```bash
# Example backtest (no creds required if using CSV/public data fallback)
poetry run forex backtest \
  --strategy rsi \
  --instrument EUR_USD \
  --from 2025-04-01 \
  --to 2025-10-01 \
  --granularity M5 \
  --risk 0.5 \
  --spread-pips 0.8

# See metrics (depends on your CLI wiring)
poetry run forex show-metrics --run-id last
```

Outputs are typically saved under a run-specific folder (trades.csv, equity_curve.csv, metrics.json).

## Troubleshooting (macOS)

Ports already in use

```bash
lsof -i :8000   # or :5173
kill -9 <PID>
```

macOS Firewall prompts

Allow incoming connections for uvicorn and node.

OANDA auth errors

Verify OANDA_ENV=practice, OANDA_API_TOKEN, OANDA_ACCOUNT_ID.

API will reject if it detects a live env.

Command Line Tools missing

```bash
xcode-select --install
```

SSL / Cert issues

Use HTTP locally (http://localhost:8000 and http://localhost:5173).

Node version mismatch

Use Node 18/20 LTS. With nvm:

```bash
nvm install --lts
nvm use --lts
```

## Project Structure

```
forex_bot/
  README.md
  pyproject.toml
  Makefile
  scripts/
    dev_backend.sh
    dev_frontend.sh
  forex/
    api.py
    realtime/
      bus.py
    backtest/
    broker/
    data/
    execution/
    strategy/
    utils/
  frontend/
    .env.example
    src/
    index.html
  .env.example
  Dockerfile
  docker-compose.yml
  .ruff.toml
```

## Notes & Disclaimers

Educational use only. No live trading.

Markets entail risk. Backtests do not guarantee future results.
