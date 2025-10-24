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

## Run the Application Locally

Follow these steps to spin up the FastAPI backend and the React dashboard on
your machine:

1. **Install prerequisites**
   - Python 3.11+
   - [Poetry](https://python-poetry.org/) for backend dependencies
   - Node.js 18+ and npm for the frontend
2. **Install backend dependencies**
   ```bash
   cd forex_bot
   poetry install
   ```
3. **Create environment files**
   - Copy `forex_bot/.env.example` (or the appropriate sample files) to
     `.env` and fill in broker credentials and ports for the backend.
   - Optionally configure `forex_bot/frontend/.env` for frontend-specific
     overrides.
4. **Start the backend**
   ```bash
   ./scripts/dev_backend.sh
   ```
   The API runs at `http://localhost:8000` with auto-reload enabled.
5. **Start the frontend** (in a new terminal)
   ```bash
   ./scripts/dev_frontend.sh
   ```
   The Vite dev server exposes the dashboard at `http://localhost:5173` (or the
   next available port).

You can also launch both services via Docker Compose with
`docker compose up --build` inside `forex_bot/` if you prefer a containerized
workflow.

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
