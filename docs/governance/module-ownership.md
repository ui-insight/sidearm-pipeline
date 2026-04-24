# Module Ownership

This template starts with a flat structure, but ownership still matters.

## Default Ownership Model

Use one clear owner for each high-impact area, even before the application grows
into domain modules.

| Scope | Suggested Owner | Responsibility |
|---|---|---|
| `backend/app/db/`, `backend/app/config.py`, auth code | Platform maintainer | Shared infrastructure, settings, persistence conventions |
| `frontend/src/api/`, app shell, routing | Frontend/platform maintainer | Shared UX shell and client integration points |
| `docs/`, `mkdocs.yml` | Documentation owner | Docs accuracy and governance alignment |
| `.github/`, `SECURITY.md` | Release or security owner | CI, dependency policy, security automation |

## CODEOWNERS Alignment

The template now includes `.github/CODEOWNERS` so repository review rules can
match this ownership model from the start.

When your project grows beyond the starter layout:

- assign domain-level ownership before reorganizing code
- keep shared infrastructure paths under explicit review
- document any module boundaries here before mirroring them in `CODEOWNERS`
