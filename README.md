# DataEnvironment Monorepo

This repository hosts a complete forex paper-trading environment composed of a FastAPI
backend, a React dashboard, developer tooling, and tests.  Use this README as a
starting point for understanding the project structure and for locating
additional, directory-specific READMEs that drill into each subsystem.

## How to Navigate This Repo

1. **Read the app overview** in [`forex_bot/README.md`](forex_bot/README.md) to
   understand the runtime architecture and workflows.
2. **Explore backend modules** by following the breadcrumbs in
   [`forex_bot/forex/README.md`](forex_bot/forex/README.md).  Every backend
   package provides its own README that explains the available classes,
   functions, and responsibilities.
3. **Inspect the frontend** by reading
   [`forex_bot/frontend/README.md`](forex_bot/frontend/README.md) and its nested
   READMEs to see how the React dashboard is organized.
4. **Look at the automation entry points** in [`forex_bot/scripts`](forex_bot/scripts)
   and [`forex_bot/tests`](forex_bot/tests) to understand the development loops.
5. **Return to this file** whenever you need a map of the documentation tree.

## Repository Layout

| Path | Description |
| --- | --- |
| `forex_bot/` | Self-contained forex paper-trading application (backend, frontend, tooling). |
| `forex_bot/forex/` | Python package implementing domain logic: strategies, brokers, data stores, execution pipelines, and the API. |
| `forex_bot/frontend/` | React + Vite dashboard for visualizing account data, launching runs, and streaming events. |
| `forex_bot/scripts/` | Helper scripts for running the dev backend and frontend. |
| `forex_bot/tests/` | Pytest suite covering API endpoints, backtest logic, broker adapters, and strategies. |

Each of these directories contains a README with deeper documentation so you
can drill down level by level.

## Developer Quick Reference

- **Python tooling**: Poetry manages dependencies (`pyproject.toml`).  Ruff,
  Black, and Pytest enforce code quality (configured in `pyproject.toml`).
- **Node tooling**: The frontend is a Vite + TypeScript project using Tailwind
  and shadcn/ui.  Install dependencies with `npm install` inside
  `forex_bot/frontend`.
- **Docker support**: `forex_bot/Dockerfile` and `forex_bot/docker-compose.yml`
  provide containerized workflows.  See the application README for details.
- **Environment variables**: `.env` files at the backend and frontend levels
  configure broker credentials, tokens, and ports.

The goal of this documentation refresh is to provide developers with a guided
path for understanding every file that powers the application.  Continue into
`forex_bot/README.md` next.
