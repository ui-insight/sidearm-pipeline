# Contributing to Vandals Stats Pipeline

Thank you for your interest in contributing! This document provides guidelines for
contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch from `main`
4. Follow the [development setup guide](docs/contributing/getting-started.md)
5. Review governance and documentation updates when your change affects schema,
   data movement, or publication behavior

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Install local dependencies with `make setup`
3. Optionally install local hooks with `make pre-commit-install`
4. Make your changes following the [coding standards](docs/contributing/coding-standards.md)
5. Write tests for new functionality
6. Run `make check-all` before opening a pull request
7. If docs or governance content changed, run `make docs-check`
8. Commit with a descriptive message
9. Push and create a pull request

When a pull request fully resolves an open issue, its description must include a
GitHub closing keyword such as `Closes #19`, `Fixes #19`, or `Resolves #19`.
Use `Related to #19` for partial work and briefly note what remains.

Pull requests that touch `frontend/**`, `e2e/**`, or the E2E workflow also run
the GitHub Actions Playwright smoke test automatically.

## Local Pre-Commit Hooks

The repository includes an optional `.pre-commit-config.yaml` for fast local
checks before changes reach CI.

- Install the hooks with `make pre-commit-install`
- Run them on demand with `make pre-commit-run`
- Commit-time hooks cover backend Ruff checks and a lightweight private-key scan
- Push-time hooks add frontend ESLint and docs integrity checks when
  matching files changed
- CI remains the source of truth for full validation, so keep running the normal
  test targets before opening a PR

## Backend Dependency Policy

- `backend/requirements.txt` is the authoritative install list for local setup,
  CI, containers, and security scans. Keep versions pinned there.
- `backend/pyproject.toml` declares backend package metadata and the minimum
  supported dependency versions for packaging consumers.
- Update both files together whenever backend dependencies change.
- Run `python scripts/check_backend_dependency_policy.py` or `make backend-test`
  to catch drift before you open a PR.
- Dependabot watches `/backend`; if it updates only one backend dependency file,
  sync the companion file before merging.

## Key Conventions

- **Backend**: Python 3.11+, FastAPI, async SQLAlchemy, Pydantic, Ruff formatting
- **Frontend**: React 19, TypeScript, Tailwind CSS only, functional components with hooks
- **Database**: PostgreSQL is the standard application database; SQLite is reserved for isolated tests or one-off local experiments
- **E2E**: Playwright smoke tests in `e2e/` for browser-level validation
- **CI smoke coverage**: frontend and e2e changes trigger the Playwright smoke
  workflow in GitHub Actions
- **Styling**: Tailwind utility classes only — no CSS component libraries
- **Testing**: pytest (backend), Vitest (frontend)
- **Branching**: feature branches from `main`, never direct commits to `main`

## AI-Assisted Contributions

When using AI coding agents:
- Include `Co-Authored-By: [Agent Name] <noreply@anthropic.com>` in commit messages
- Label pull requests with `ai-assisted`
- Fill in the Agent Context section of the PR template
- Treat `CLAUDE.md` as the maintained source of truth for tracked agent guidance
- Treat `AGENTS.md`, if used locally, as a derived or exported copy unless the project explicitly decides to track it
- See the [Agent Coordination Guide](docs/contributing/agent-coordination.md) for details

## Code of Conduct

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
