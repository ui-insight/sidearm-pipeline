# Architecture Overview

## System Architecture

Vandals Stats Pipeline follows a client-server architecture with clear separation of concerns:

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│   React SPA     │────▶│   FastAPI        │────▶│  PostgreSQL  │
│   (Frontend)    │◀────│   (Backend)      │◀────│  (Database)  │
│                 │     │                  │     │              │
│ - TypeScript    │     │ - Python 3.11+   │     │ - SQLite tst │
│ - Tailwind CSS  │     │ - SQLAlchemy     │     │ - PG16 std   │
│ - Vite          │     │ - Pydantic       │     │              │
│ - React Router  │     │ - Auth ext.      │     │              │
└─────────────────┘     └─────────────────┘     └──────────────┘
```

### Frontend

The frontend is a single-page application (SPA) built with:

- **React 19** with functional components and hooks
- **TypeScript** for type safety
- **Tailwind CSS v4** for styling (utility-first, no component libraries)
- **Vite** for development server and production builds
- **React Router v7** for client-side routing

In development, Vite proxies `/api` requests to the backend. In production, nginx serves
the built frontend and proxies API requests.

### Backend

The backend is a REST API built with:

- **FastAPI** with async request handling
- **SQLAlchemy 2.0** with async sessions
- **Pydantic v2** for request/response validation
- **Authentication / authorization extension point** under `backend/app/auth/`
- **PyJWT / bcrypt dependencies** available when projects add auth
- **Alembic** for database migrations

### Database

- **Standard application database**: PostgreSQL 16 via asyncpg
- **Testing / fallback**: SQLite via aiosqlite for isolated test runs or one-off experiments
- **Schema management**: Alembic migrations under `backend/migrations/`

### Deployment

- **Docker Compose** orchestration with separate frontend and backend containers
- Frontend container uses a multi-stage build (Node for build, nginx for serving)
- Frontend nginx serves on an unprivileged internal port as a non-root user
- Backend container runs uvicorn as a dedicated non-root app user

## Design Principles

1. **Async-first** — all I/O operations use async/await
2. **Type-safe** — TypeScript on frontend, Pydantic on backend
3. **Thin controllers** — route handlers delegate to service modules
4. **One file per resource** — models, schemas, and routes each get their own file
5. **Convention over configuration** — follow established patterns from OpenERA

## Reference

For a detailed example of this architecture in production, see:
[OpenERA Architecture Overview](https://github.com/ui-insight/OpenERA/blob/main/docs/architecture/overview.md)
