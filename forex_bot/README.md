# Forex Paper Trading Application

This directory contains everything required to run the forex paper-trading
experience: infrastructure-as-code, Python backend, React frontend, automation
scripts, and tests.  The goal of this README is to orient developers so they can
quickly understand how each piece of the stack fits together.

## High-Level Architecture

```
┌──────────────────┐     HTTP + SSE      ┌────────────────────────┐
│ React Dashboard  │  ─────────────────▶ │ FastAPI Application    │
│ (frontend/)      │ ◀────────────────── │ (forex/api.py)         │
└──────────────────┘   REST + streaming  └─────────┬──────────────┘
                                                   │
                                                   ▼
                                        Domain Packages (forex/)
                                                   │
                                                   ▼
                                         Brokers, Strategies,
                                         Backtesting, Storage
```

- **frontend/** implements a Vite + React dashboard that authenticates to the
  API, streams live events, submits new runs, and renders metrics.
- **forex/** contains the Python domain model: broker adapters, strategy engine,
  backtesting loop, execution services, realtime orchestration, and shared
  utilities.
- **Dockerfile**, **docker-compose.yml**, and **Makefile** coordinate local and
  containerized workflows.
- **scripts/** provides helper shell commands (`dev_backend.sh`,
  `dev_frontend.sh`) for quick-start development.
- **tests/** contains pytest coverage for the critical code paths.

Each directory includes a README that explains its contents in detail.  Follow
those breadcrumbs whenever you dive deeper.

## Backend Runtime Overview

1. **Configuration** is loaded from environment variables via
   [`forex/config.py`](forex/config.py).  Secrets and ports are defined in `.env`.
2. **FastAPI** is initialised in [`forex/api.py`](forex/api.py).  The app wires
   together broker factories, data stores, event bus, strategy registry, and
   live runner.
3. **Broker adapters** under [`forex/broker`](forex/broker) implement either the
   OANDA practice API or a deterministic paper simulator.
4. **Strategies** in [`forex/strategy`](forex/strategy) produce trade signals.
5. **Execution** modules in [`forex/execution`](forex/execution) translate
   signals into orders and risk management rules.
6. **Realtime orchestration** in [`forex/realtime`](forex/realtime) manages
   streaming prices, event bus fan-out, and the live run lifecycle.
7. **Backtesting** code in [`forex/backtest`](forex/backtest) replays historical
   candles, calculates metrics, and writes summary reports.
8. **Data stores** in [`forex/data`](forex/data) persist candles and run
   metadata via SQLAlchemy models.

## Frontend Runtime Overview

1. [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts) wraps fetch calls and
   handles authentication headers.
2. [`frontend/src/hooks/useApi.ts`](frontend/src/hooks/useApi.ts) and
   [`frontend/src/hooks/useEventStream.ts`](frontend/src/hooks/useEventStream.ts)
   encapsulate REST + SSE interactions.
3. [`frontend/src/App.tsx`](frontend/src/App.tsx) is the primary dashboard
   container.  It fetches configuration, account snapshots, open positions, run
   history, and renders charts via Recharts.
4. [`frontend/src/components`](frontend/src/components) contains small UI
   primitives (button, card, input, select) used throughout the dashboard.

Consult `frontend/README.md` for a detailed breakdown of the React project and
its file-by-file responsibilities.

## Operational Files

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds a production-ready image that serves the API. |
| `docker-compose.yml` | Spins up the API, database, and frontend services for local experimentation. |
| `Makefile` | Provides shortcuts (`dev-api`, `dev-ui`, `lint`, `test`). |
| `pyproject.toml` | Poetry project definition with lint/test tooling configuration. |
| `scripts/dev_backend.sh` | Runs the FastAPI server with auto-reload. |
| `scripts/dev_frontend.sh` | Starts the Vite development server. |

## Testing Strategy

- `pytest` is the canonical test runner.  See [`tests/README.md`](tests/README.md)
  for the coverage map.
- Backtesting, broker integrations, math utilities, and strategies each have
  dedicated tests under `tests/`.
- End-to-end API sanity checks live in `tests/test_api.py` and exercise the
  FastAPI routes against a simulated broker.

## Next Steps

- Visit [`forex/README.md`](forex/README.md) for backend internals.
- Visit [`frontend/README.md`](frontend/README.md) for React project details.
- Review [`tests/README.md`](tests/README.md) to understand coverage.

This directory is the central hub that links all developer documentation in the
project.  Use the table of READMEs as a map when onboarding or planning work.
