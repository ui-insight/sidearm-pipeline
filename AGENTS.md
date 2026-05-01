# AGENTS.md — Agent Context for Vandals Stats Pipeline

> This file is the authoritative guide for AI coding agents working on this project.
> It defines the tech stack, conventions, standards, and boundaries that agents must follow.
> Keep this file synchronized with `CLAUDE.md`, which is the tracked source of truth.

---

## Project Overview

**Vandals Stats Pipeline** is a web application for University of Idaho business operations,
built with a React frontend and FastAPI backend. This project was scaffolded from
the [TEMPLATE-app](https://github.com/ui-insight/TEMPLATE-app) repository template.

**Description**: Sidearm boxscore ingestion pipeline for University of Idaho athletics

**Status**: in development

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.x | UI framework |
| TypeScript | ~5.x | Type safety |
| Vite | 7.x | Build tool and dev server |
| Tailwind CSS | v4.x | Utility-first styling |
| React Router | v7.x | Client-side routing |
| Vitest | latest | Unit/component testing |
| ESLint | latest | Code linting |

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | >=3.11 | Runtime |
| FastAPI | >=0.115.0 | API framework |
| SQLAlchemy (async) | >=2.0.0 | ORM with async support |
| Pydantic | >=2.0.0 | Data validation and settings |
| PyJWT[crypto] | >=2.8.0 | JWT support for optional auth scaffolding |
| bcrypt | >=4.0.0 | Password hashing for optional auth scaffolding |
| aiosqlite | >=0.20.0 | Test database / optional SQLite fallback |
| asyncpg | >=0.29.0 | Standard PostgreSQL driver |
| Alembic | >=1.13.0 | Database migrations |
| Ruff | >=0.6.0 | Python linting and formatting |
| pytest / pytest-asyncio | latest | Testing |

### Infrastructure
| Technology | Purpose |
|---|---|
| Docker / Docker Compose | Containerized deployment |
| PostgreSQL 16 | Standard application database (local and production) |
| SQLite | Test isolation / optional one-off fallback |
| nginx | Frontend static serving and API proxy |
| MkDocs Material | Documentation site |

---

## Agent Rules

These rules are **normative constraints** — agents must follow them without exception.

### Never Do
1. **Never add CSS component libraries** — use Tailwind CSS utility classes only (no Bootstrap, Material UI, Chakra, etc.)
2. **Never introduce class components** — use functional components with hooks only
3. **Never commit secrets or credentials** — use environment variables via `.env` files
4. **Never modify `.env` files directly** — update `.env.example` and instruct the user
5. **Never skip type safety** — all frontend code must be TypeScript; all backend endpoints must use Pydantic schemas
6. **Never use raw SQL** — use SQLAlchemy ORM for all database operations
7. **Never make unsolicited improvements** — only change what is requested or directly necessary
8. **Never add unnecessary abstractions** — three similar lines of code is better than a premature abstraction

### Always Do
9. **Always use async patterns** — FastAPI endpoints and SQLAlchemy sessions must be async
10. **Always validate inputs** — Pydantic schemas on all API endpoints; form validation on all frontend forms
11. **Always run tests before claiming work is complete** — `pytest` for backend, `npm run build && npm test` for frontend
12. **Always use feature branches** — never commit directly to `main`
13. **Always include Co-Authored-By** — AI-assisted commits must include:
    ```
    Co-Authored-By: [Agent Name] <noreply@anthropic.com>
    ```
14. **Always follow existing patterns** — when adding new code, match the conventions already present in the codebase
15. **Always document new API endpoints** — include docstrings on FastAPI route functions

---

## Project Structure

```
Vandals Stats Pipeline/
├── .github/              # GitHub templates and CI workflows
│   ├── ISSUE_TEMPLATE/   # Bug report and feature request templates
│   ├── workflows/        # CI/CD pipeline definitions
│   ├── CODEOWNERS        # Review ownership rules
│   └── pull_request_template.md
├── backend/
│   ├── app/
│   │   ├── api/v1/       # API route handlers (one file per resource)
│   │   ├── auth/         # Authentication extension point (JWT, passwords, roles)
│   │   ├── db/           # Database engine, seed data
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic and external integrations
│   │   ├── config.py     # Pydantic Settings configuration
│   │   └── main.py       # FastAPI application entry point
│   ├── tests/            # pytest test files
│   ├── alembic.ini       # Migration configuration
│   ├── migrations/       # Alembic migration environment
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt  # Pinned production dependencies
├── frontend/
│   ├── src/
│   │   ├── api/          # API client modules (one per resource)
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Top-level route pages
│   │   ├── types/        # TypeScript interfaces
│   │   ├── App.tsx       # Root component with routing
│   │   └── main.tsx      # Application entry point
│   ├── Dockerfile
│   ├── nginx.conf        # Production reverse proxy config
│   ├── package.json
│   └── vite.config.ts
├── docs/                 # MkDocs documentation source
│   ├── adr/              # Architecture Decision Records
│   ├── architecture/     # System architecture docs
│   ├── deployment/       # Deployment and configuration guides
│   ├── governance/       # Data governance policies
│   ├── security/         # Security documentation
│   └── contributing/     # Development guidelines
├── .claude/              # Optional local tool-helper files (not project policy)
├── .env.example          # Environment variable template
├── CLAUDE.md             # This file — canonical tracked agent context
├── CONTRIBUTING.md       # Contribution guidelines
├── CODE_OF_CONDUCT.md    # Community standards
├── SECURITY.md           # Security policy
├── docker-compose.yml    # Container orchestration
├── mkdocs.yml            # Documentation site config
├── scripts/              # Repository maintenance helpers
└── README.md             # Project overview
```

---

## Development Workflow

### First-Time Setup
```bash
# Backend
docker compose up -d postgres

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
# Backend
cd backend && pytest -v --tb=short

# Frontend
cd frontend && npm run build && npm test

# Docs / template integrity
python scripts/check_template_docs.py
mkdocs build --strict
```

### Database Migrations
```bash
cd backend
./.venv/bin/alembic revision --autogenerate -m "describe change"
./.venv/bin/alembic upgrade head
```

### Docker
```bash
docker compose up --build
# Frontend: http://localhost:9200
# Backend API: http://localhost:9200/api/
```

---

## Coding Conventions

### Backend (Python)
- **Formatter/Linter**: Ruff (`ruff check . && ruff format .`)
- **Line length**: 88 characters
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Imports**: sorted by Ruff (stdlib → third-party → local)
- **Models**: one file per resource in `backend/app/models/`
- **Schemas**: one file per resource in `backend/app/schemas/`
- **Routes**: one file per resource in `backend/app/api/v1/`
- **Tests**: mirror the source structure in `backend/tests/`

### Frontend (TypeScript/React)
- **Linter**: ESLint (zero warnings policy)
- **Type checking**: `tsc -b` must pass with no errors
- **Components**: functional components with hooks, one component per file
- **Styling**: Tailwind CSS utility classes only — no inline styles, no CSS modules
- **State management**: React Context for shared state; local useState/useReducer otherwise
- **API calls**: centralized in `frontend/src/api/` modules
- **Naming**: PascalCase for components, camelCase for functions/variables

### Git Conventions
- **Branch naming**: `feature/description`, `fix/description`, `docs/description`
- **Commit messages**: imperative mood, concise subject line
- **PR process**: all changes go through pull requests; CI must pass before merge

---

## Data Governance

### Database Conventions
- Standard app environments: PostgreSQL 16 via asyncpg
- SQLite via aiosqlite is reserved for tests or isolated local experiments
- All models must extend a common `Base` class from `backend/app/db/base.py`
- Use the Alembic scaffold in `backend/migrations/` for schema migrations
- Seed data for development goes in `backend/app/db/seed.py`

### Data Classification
Before storing any data, classify it according to university data governance policy:
- **Public**: no restrictions
- **Internal**: requires authentication
- **Confidential**: requires encryption at rest and role-based access
- **Restricted**: PII, FERPA, HIPAA data — requires additional safeguards

### Data Handling Rules
- Never store Social Security Numbers, dates of birth, or banking information in the application database
- Personally identifiable information (PII) must be documented in a data inventory
- File uploads must be UUID-prefixed and served through authenticated API endpoints only
- All data flows should be documented in `docs/governance/`

---

## Security Standards

### Authentication & Authorization
- The template reserves `backend/app/auth/` as the extension point for authentication and RBAC
- If authentication is required, use JWT (HS256) or another documented approach appropriate to your application
- Use bcrypt or an equivalent adaptive hasher for password-based login flows
- Session or token expiration must be configurable
- All authentication configuration via environment variables

### Application Security
- Pydantic validation on all API inputs
- CORS restricted to known origins (configured in `.env`)
- File uploads: validate type, limit size, store with UUID names
- No secrets in source code — use `.env` and environment variables
- HTTPS required in production

### Dependency Security
- Dependabot enabled for automated vulnerability alerts
- `pip-audit` for Python dependency scanning
- `npm audit` for JavaScript dependency scanning
- Regular dependency updates via automated PRs

### Security Documentation
- Maintain `SECURITY.md` with vulnerability reporting instructions
- Document known limitations and security assumptions
- Prepare an institutional security review checklist for IT teams
- See `docs/security/` for detailed security documentation

---

## Documentation Standards

### Required Documentation
Every project built from this template must maintain:
1. **README.md** — project overview, quick start, current status
2. **CLAUDE.md** — this file, kept current as the project evolves
3. **CONTRIBUTING.md** — how to contribute
4. **SECURITY.md** — security policy and vulnerability reporting
5. **docs/architecture/** — system architecture and design decisions
6. **docs/deployment/** — runtime and deployment guidance
7. **docs/governance/** — data governance and classification
8. **docs/security/** — detailed security documentation
9. **docs/adr/** — architecture decision records

### Agent Guidance Policy
- `CLAUDE.md` is the tracked source of truth for repository agent guidance
- Tool-specific local helper files in `.claude/` are optional and must not replace project policy
- If your workflow also uses `AGENTS.md`, keep it derived from or synchronized with `CLAUDE.md`

### Architecture Decision Records (ADRs)
Document significant technical decisions in `docs/adr/` using this format:
```markdown
# ADR-NNN: Title

## Status
Accepted | Proposed | Deprecated

## Context
What is the issue we are deciding on?

## Decision
What did we decide?

## Consequences
What are the trade-offs?
```

### MkDocs
- Documentation site built with MkDocs Material theme
- Run locally: `python scripts/check_template_docs.py && mkdocs serve`
- Configuration in `mkdocs.yml`

---

## Getting Help

- **Agent coordination**: See `docs/contributing/agent-coordination.md` for multi-agent workflows
- **Stack questions**: Consult framework documentation — [FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/), [SQLAlchemy](https://docs.sqlalchemy.org/), [Tailwind CSS](https://tailwindcss.com/)
- **University standards**: Contact the UI-Insight team
