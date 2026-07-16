# Vandals Stats Pipeline

> Sidearm boxscore ingestion pipeline for University of Idaho athletics

**New here?** Start with the [Onboarding doc](docs/onboarding.md) — it
points you through the existing files in the order they make sense.

## Project Overview

Vandals Stats Pipeline ingests public Sidearm boxscore data, normalizes it in
PostgreSQL, and prepares that data for internal review, AI-assisted content
generation, and downstream athletics website display.

The project currently provides:

- **Tech Stack**: React 19 + TypeScript + Tailwind CSS frontend, FastAPI + SQLAlchemy backend, PostgreSQL standard database
- **Structured ingestion**: Sidearm scraping and normalized storage for games, team stats, player stat groups, and scoring plays
- **Internal review UI**: list and detail views for ingested games
- **Record Book preview**: evidence-backed WBB points leaders with explicit coverage windows
- **Documentation Standards**: MkDocs Material site with architecture, governance, and security docs
- **Data Governance**: classification, lineage, retention, and schema-versioning guidance
- **Security Standards**: dependency scanning, configuration checks, and launch-readiness guidance
- **CI/CD**: GitHub Actions for testing, linting, and security scanning
- **Agent Guidance**: `CLAUDE.md` as the canonical tracked AI-agent context
- **Browser Smoke Tests**: Playwright `e2e/` scaffold for end-to-end validation

### Project Foundation

This repository was bootstrapped from the
[UI-Insight TEMPLATE-app](https://github.com/ui-insight/TEMPLATE-app).

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 22+ and npm
- Docker and Docker Compose (optional, for containerized development)

### Local Setup

```bash
git clone https://github.com/ui-insight/sidearm-pipeline.git
cd sidearm-pipeline
```

Then:

1. Install local dependencies with `make setup`
2. Copy `.env.example` to `.env` and review the values before you start local services
3. Review `.github/CODEOWNERS`, `SECURITY.md`, and the governance docs before a shared deployment

Before a real launch, work through the
[Production Readiness Gate](docs/deployment/production-readiness.md) to confirm
deployment, security, governance, backup, monitoring, and supply-chain checks.

This project tracks `CLAUDE.md` as the canonical repository agent guide and
`AGENTS.md` as a synchronized companion file for toolchains that read it. Keep
them aligned instead of maintaining two divergent rule sets by hand.

### Documentation Integrity Check

Run the docs integrity check at any time with:

```bash
python scripts/check_template_docs.py
```

That catches unexpected template placeholders and broken MkDocs nav links.

### Development Setup

#### One-Command Dependency Setup

```bash
make setup
```

That installs backend, frontend, and e2e dependencies. After that:

```bash
cp .env.example .env
docker compose up -d postgres
```

**Backend** (Terminal 1):
```bash
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Frontend** (Terminal 2):
```bash
npm --prefix frontend run dev
```

The frontend dev server runs at `http://localhost:5173` and proxies API requests to `http://localhost:8000`.
The standard local database is PostgreSQL on `localhost:5432`; SQLite is kept only as an optional fallback for isolated experiments.

### Docker

```bash
docker compose up --build
```

Access the application at `http://localhost:9200`. The stack includes PostgreSQL, the FastAPI backend, and the nginx-served frontend.

---

## Project Structure

```
├── backend/              # FastAPI application
│   ├── alembic.ini       # Migration configuration
│   ├── app/
│   │   ├── api/v1/       # Route handlers
│   │   ├── auth/         # Authentication / authorization extension point
│   │   ├── db/           # Database engine and seeds
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   ├── config.py     # Settings
│   │   └── main.py       # App entry point
│   ├── migrations/       # Alembic migration environment
│   └── tests/
├── frontend/             # React application
│   └── src/
│       ├── api/          # API client modules
│       ├── components/   # UI components
│       ├── pages/        # Route pages
│       └── types/        # TypeScript interfaces
├── docs/                 # MkDocs documentation
├── e2e/                  # Playwright smoke tests
├── AGENTS.md             # Synchronized agent guide for compatible toolchains
├── CLAUDE.md             # Canonical tracked AI agent context
├── .claude/README.md     # Local tool-helper guidance
├── scripts/              # Template maintenance helpers
└── docker-compose.yml
```

See `CLAUDE.md` for the complete project structure and conventions.

---

## Development

### Running Tests

```bash
make backend-test
make frontend-test
make e2e-test
make docs-check
make check-all
```

Frontend and `e2e/` changes also trigger the GitHub Actions `E2E Smoke Tests`
workflow, which builds the frontend and runs the Playwright smoke test against
the preview server.

### Backend Dependency Policy

- `backend/requirements.txt` is the authoritative install list for local setup,
  CI, containers, and security scans. It pins concrete backend dependency
  versions.
- `backend/pyproject.toml` records backend package metadata and the minimum
  supported dependency versions for packaging consumers.
- When you add or update backend dependencies, update both files together.
- `python scripts/check_backend_dependency_policy.py` and `make backend-test`
  catch drift between the two files.
- Dependabot monitors `/backend`; if a backend dependency PR changes one file
  but not the other, sync the companion file before merging.

### Linting and Formatting

```bash
cd backend && ./.venv/bin/ruff check . && ./.venv/bin/ruff format --check .
cd frontend && npm run lint
```

### Database Migrations

```bash
cd backend
./.venv/bin/alembic revision --autogenerate -m "describe change"
./.venv/bin/alembic upgrade head
```

The scaffold still auto-creates tables in `DEV_MODE=true` for quick local starts,
but Postgres plus Alembic is the standard path once the app has real schema history.

### End-to-End Smoke Test

```bash
make e2e-test
```

The Playwright config starts the frontend dev server automatically on
`http://127.0.0.1:4173` for the homepage smoke test.

In GitHub Actions, the smoke workflow builds the frontend first and runs the
same Playwright test against the preview server for a more production-like path.

If Playwright reports that Chromium is missing on first run, install it with:

```bash
npm --prefix e2e run install:browsers
```

### Documentation

```bash
make docs-check
backend/.venv/bin/mkdocs serve
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting instructions.
CI also generates dependency audit artifacts and SBOMs from the GitHub Actions workflows.

---

## Resources

External tools, skill collections, and references this project builds on
are catalogued in [docs/resources.md](docs/resources.md) — MindRouter, the
`mattpocock/skills` collection, and the `pbakaus/impeccable` design-language
skill family.
