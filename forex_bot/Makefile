SHELL := /bin/bash

.PHONY: setup setup-py setup-node env dev dev-api dev-ui test lint typecheck build-ui docker-up docker-down

setup: setup-py setup-node

setup-py:
	poetry install

setup-node:
	cd frontend && npm install

env:
	cp -n .env.example .env || true
	cp -n frontend/.env.example frontend/.env || true

dev: dev-api
	@echo "Frontend: run 'make dev-ui' or 'scripts/dev_frontend.sh' then open http://localhost:5173"

dev-api:
	chmod +x scripts/dev_backend.sh
	./scripts/dev_backend.sh

dev-ui:
	chmod +x scripts/dev_frontend.sh
	./scripts/dev_frontend.sh

test:
	poetry run pytest -q

lint:
	poetry run ruff check .
	poetry run black --check .

typecheck:
	poetry run mypy forex

build-ui:
	cd frontend && npm run build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
