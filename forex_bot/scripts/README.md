# Development Scripts (`forex_bot/scripts`)

These shell scripts wrap the most common development workflows.

| File | Purpose |
| --- | --- |
| `dev_backend.sh` | Activates the Poetry environment and runs `uvicorn forex.api:app --reload`. |
| `dev_frontend.sh` | Starts the Vite development server within `frontend/`. |

Use the scripts directly or invoke the equivalent targets in the project
`Makefile` (`make dev-api`, `make dev-ui`).
