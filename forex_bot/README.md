# Forex RL Trading Platform

This repository provides a production-ready paper/real FX trading stack composed of a
FastAPI backend and a Vite + React dashboard.  The platform streams market data
through a transparent pipeline, applies PPO-based reinforcement-learning signals,
enforces robust risk management, and executes trades via a broker adapter.

## Architecture Overview

```
┌──────────────────────┐      HTTP + SSE       ┌────────────────────────────┐
│ React Dashboard      │  ⇄  /api/* & events  │ FastAPI Application         │
│ (frontend/)          │                      │ (forex_app/)                │
└──────────────────────┘                      └────────────┬────────────────┘
                                                         ┌─┴──────────────┐
                                                         │ Engine Stages │
                                                         └───────────────┘
     Market Data → Feature Calc → RL Signal → Risk Check → Order Intent → Broker
            ↓             ↓              ↓             ↓              ↓
        Position Tracking → PnL Update → News Alerts → Metrics/Logs → Dashboard
```

### Backend (`forex_app/`)

| Module | Purpose |
| --- | --- |
| `settings.py` | Pydantic settings (env driven) with toggles for risk, RL, CORS, and broker selection. |
| `models.py` | Typed Pydantic schemas for candles, signals, orders, positions, news items, and engine status. |
| `event_bus.py` | Async in-process pub/sub bus powering the dashboard SSE feed. |
| `data.py` | Candle persistence (SQLite) plus feature engineering (EMA, RSI, ATR). |
| `rl_agent.py` | PPO policy loader with deterministic inference and heuristic fallback. |
| `rl_env.py` | Minimal Gymnasium environment for PPO training/backtesting experiments. |
| `risk.py` | ATR-based sizing, leverage/drawdown guards, and order intent builder. |
| `broker.py` | Broker interface + paper simulator with mark-to-market updates. |
| `news.py` | Cached polling of the free GDELT news API with naive sentiment tagging. |
| `engine.py` | Heartbeat-driven orchestration state machine that logs every pipeline stage. |
| `routes.py` | FastAPI app wiring, CORS, Prometheus metrics, REST routes, and SSE streaming. |
| `logging.py` | Structlog JSON logging configuration. |
| `main.py` | Uvicorn entry point exposing `app`. |

The engine enforces the prescribed state machine:

```
IDLE → DATA_READY → FEATURES_READY → SIGNAL_READY → RISK_OK → ORDER_SENT → POSITION_OPEN → MONITORING
        ↘ (blocked/error transitions publish reason codes and keep the dashboard informed)
```

Each tick publishes structured events capturing decisions, confidence levels, and
why trades may have been rejected (e.g., `low_confidence`, `drawdown_stop`).

### Frontend (`frontend/`)

The Vite + React dashboard consumes `/api/*` routes via React Query and listens
for engine events via server-sent events.  Dedicated panels render:

- Top status bar (mode, broker, equity, heartbeat)
- Pipeline monitor with live badges per stage
- Event log (filterable) that surfaces the latest 200 events
- Open positions & pending orders tables
- RL signal panel (direction, confidence, feature snapshot)
- News feed with per-symbol impact badges
- Backtest runner showing equity curves
- Settings drawer for risk toggles (`TRADE_ALLOCATION_PCT`, `RISK_PCT_PER_TRADE`, etc.)

## Running Locally

### Backend

```bash
poetry install
poetry run uvicorn forex_app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The default CORS configuration allows http://localhost:5173 so the Vite dev
server can interact with the API.

## Key Features

- **RL Signal Engine** – Loads a PPO model (`data/models/ppo_fx.zip`) if present
  or falls back to a deterministic EMA/RSI heuristic.
- **Risk Discipline** – Trades a configurable percentage of free equity, applies
  ATR-based stops/take-profits, caps leverage, and halts trading when drawdown
  thresholds are exceeded.
- **Paper & Live Modes** – Paper broker ships with deterministic pricing; swap
  to the OANDA adapter via `BROKER=oanda` once credentials are configured.
- **Transparency First** – Every pipeline stage produces structured JSON events,
  including explicit reasons for idle states.  Prometheus metrics expose engine
  heartbeats, trade counts, and equity levels.
- **Backtesting** – `/api/backtest/run` replays candles through the same feature
  and risk pipeline to generate an equity curve and trade ledger.
- **News Awareness** – Polls GDELT every five minutes, tags relevant FX symbols,
  and surfaces sentiment/impact on the dashboard.

## Testing

Run the full suite (risk sizing, RL gating, and API smoke tests) via:

```bash
poetry run pytest
```

## Environment Variables

All configuration lives in `.env`.  Key entries:

| Variable | Default | Description |
| --- | --- | --- |
| `BROKER` | `paper` | `paper` or `oanda`. |
| `TRADE_ALLOCATION_PCT` | `0.02` | Fraction of equity allocated per trade. |
| `RISK_PCT_PER_TRADE` | `0.5` | Fraction of the allocation risked at stop-loss. |
| `MAX_LEVERAGE` | `20` | Leverage guardrail. |
| `MAX_DRAWDOWN_STOP` | `0.2` | Hard stop once drawdown exceeds 20%. |
| `MIN_SIGNAL_CONF` | `0.6` | Minimum RL confidence to accept a trade. |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed origins for dashboard traffic. |
| `NEWS_PROVIDER` | `gdelt` | News adapter (`gdelt` or `alphavantage`). |

## Screenshots

Update the `docs/` folder with dashboard screenshots once the frontend is
connected to a running engine.
