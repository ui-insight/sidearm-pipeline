# Getting Started

## Prerequisites

- Python 3.11 or later
- Node.js 22 or later (with npm)
- Git
- Docker and Docker Compose (optional, for containerized development)

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ui-insight/sidearm-pipeline.git
cd sidearm-pipeline
```

### 2. Install Dependencies

```bash
make setup
```

This installs backend, frontend, and e2e dependencies. It does not create `.env`
for you, so review `.env.example` and copy it manually before starting services.

### Optional: Install Local Hooks

```bash
make pre-commit-install
```

This installs optional `pre-commit` and `pre-push` hooks for quick local checks.
The commit hook runs backend Ruff checks and a lightweight private-key scan. The
push hook adds frontend ESLint and docs integrity checks when relevant
files changed. CI still remains the source of truth for full validation.

### 3. Start Postgres

```bash
docker compose up -d postgres
```

### 4. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your settings (defaults target the local Postgres container)
```

### 5. Start the Backend

```bash
cd backend
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`. Visit `http://localhost:8000/docs`
for the interactive API documentation (Swagger UI).

### 6. Frontend Setup (New Terminal)

```bash
npm --prefix frontend run dev
```

The frontend is now available at `http://localhost:5173`.

### 7. Verify Everything Works

- Frontend loads at `http://localhost:5173`
- API health check at `http://localhost:5173/api/v1/health` returns `{"status": "healthy"}`

## Docker Alternative

```bash
docker compose up --build
```

Access the application at `http://localhost:9200`.

## Running Tests

```bash
make backend-test
make frontend-test
make e2e-test
make docs-check
make check-all
make pre-commit-run
```

## Running the E2E Smoke Test

```bash
make e2e-test
```

The Playwright config starts the frontend dev server automatically, so this
smoke test does not require the backend for the default homepage check.

Frontend and `e2e/` pull requests also run this smoke path in GitHub Actions.
CI builds the frontend first and serves the built app through Vite preview
before Playwright runs.

If Playwright reports that Chromium is missing on first run, run:

```bash
npm --prefix e2e run install:browsers
```

## Next Steps

- Read `CLAUDE.md` to understand the project conventions
- Treat `CLAUDE.md` as the canonical tracked agent guide; keep any local `AGENTS.md` copy in sync rather than editing both independently
- Use PostgreSQL as the default application database; keep SQLite limited to tests or isolated experiments
- Review the [Data Model](../architecture/data-model.md)
- Review the [Coding Standards](coding-standards.md)
- Check the [Architecture Overview](../architecture/overview.md)
- Review the [Deployment Quick Start](../deployment/quickstart.md)
