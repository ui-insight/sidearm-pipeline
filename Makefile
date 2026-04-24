SHELL := /bin/bash

BACKEND_VENV := backend/.venv
BACKEND_PYTHON := $(BACKEND_VENV)/bin/python
BACKEND_PIP := $(BACKEND_VENV)/bin/pip
BACKEND_PYTEST := $(BACKEND_VENV)/bin/pytest
BACKEND_RUFF := $(BACKEND_VENV)/bin/ruff
BACKEND_MKDOCS := $(BACKEND_VENV)/bin/mkdocs
PRE_COMMIT := $(BACKEND_VENV)/bin/pre-commit
PRE_COMMIT_HOME := $(CURDIR)/.cache/pre-commit

.PHONY: help setup pre-commit-install pre-commit-run backend-deps-check backend-test frontend-test e2e-test docs-check docker-smoke check-all

help:
	@echo "Available targets:"
	@echo "  setup         Install backend, frontend, and e2e dependencies"
	@echo "  pre-commit-install Install local pre-commit and pre-push hooks"
	@echo "  pre-commit-run Run the configured pre-commit hooks across the repo"
	@echo "  backend-deps-check Validate backend dependency policy"
	@echo "  backend-test  Run backend dependency check, lint, format check, and pytest"
	@echo "  frontend-test Run frontend lint, type check, build, and unit tests"
	@echo "  e2e-test      Run the Playwright smoke test"
	@echo "  docs-check    Run template docs checks and strict MkDocs build"
	@echo "  docker-smoke  Build the Docker stack and verify frontend/API health"
	@echo "  check-all     Run backend, frontend, e2e, and docs checks"

$(BACKEND_PYTHON):
	python3 -m venv $(BACKEND_VENV)

setup: $(BACKEND_PYTHON)
	$(BACKEND_PIP) install -r backend/requirements.txt
	$(BACKEND_PIP) install mkdocs-material
	npm ci --prefix frontend
	npm ci --prefix e2e
	@echo "Setup complete."
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and review the values."
	@echo "  2. Start Postgres with: docker compose up -d postgres"
	@echo "  3. Start the backend and frontend dev servers."

pre-commit-install: $(BACKEND_PYTHON)
	$(BACKEND_PIP) install pre-commit
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PRE_COMMIT) install
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PRE_COMMIT) install --hook-type pre-push

pre-commit-run: $(BACKEND_PYTHON)
	$(BACKEND_PIP) install pre-commit
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PRE_COMMIT) run --all-files --hook-stage pre-commit
	PRE_COMMIT_HOME=$(PRE_COMMIT_HOME) $(PRE_COMMIT) run --all-files --hook-stage pre-push

backend-deps-check:
	python3 scripts/check_backend_dependency_policy.py

backend-test: backend-deps-check $(BACKEND_PYTHON)
	cd backend && \
		./.venv/bin/ruff check . && \
		./.venv/bin/ruff format --check . && \
		./.venv/bin/pytest -v --tb=short

frontend-test:
	cd frontend && \
		npm run lint && \
		npx tsc -b && \
		npm run build && \
		npm test

e2e-test:
	cd e2e && npm test

docs-check: $(BACKEND_PYTHON)
	python3 scripts/check_template_docs.py
	$(BACKEND_MKDOCS) build --strict

docker-smoke:
	@set -euo pipefail; \
	trap 'docker compose down >/dev/null 2>&1 || true' EXIT; \
	docker compose up --build -d; \
	until curl -fsS http://localhost:9200 >/dev/null 2>&1; do sleep 2; done; \
	curl -fsS http://localhost:9200/api/v1/health >/dev/null

check-all: backend-test frontend-test e2e-test docs-check
