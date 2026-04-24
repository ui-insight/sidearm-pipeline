# Quick Start

This guide gets the template running locally with the standard PostgreSQL
configuration.

## Prerequisites

- Python 3.11+
- Node.js 22+
- Git

## Run the Backend

```bash
docker compose up -d postgres

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000
```

The API should now be available at `http://localhost:8000`, with interactive
docs at `http://localhost:8000/docs`.
The default `.env.example` points to PostgreSQL on `localhost:5432`.

## Run the Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Verify the Template

- `http://localhost:5173` loads the starter homepage
- `http://localhost:5173/api/v1/health` returns a healthy response

## Useful Checks

```bash
# Backend
cd backend && pytest -v --tb=short

# Frontend
cd frontend && npm run build && npm test

# E2E smoke test
cd e2e && npm install && npm test

# Docs
python scripts/check_template_docs.py
mkdocs build --strict
```
