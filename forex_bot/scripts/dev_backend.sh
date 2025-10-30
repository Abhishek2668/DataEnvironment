#!/usr/bin/env bash
set -euo pipefail
export API_PORT="${API_PORT:-8000}"
poetry run uvicorn forex_bot.main:app --host 0.0.0.0 --port "${API_PORT}" --reload
