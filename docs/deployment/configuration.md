# Configuration Reference

This page describes the baseline environment variables included in the template.

## Core Application Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/app` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | Application secret for auth/session signing or similar sensitive uses |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Reserved token lifetime setting for projects that add token-based auth |
| `DEV_MODE` | `true` | Enables development-friendly behavior |
| `UPLOAD_DIR` | `./uploads` | Root directory for uploaded files |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:9200"]` | Allowed frontend origins |
| `RATE_LIMIT_ENABLED` | `false` | Enables the starter in-memory backend rate limiter |
| `RATE_LIMIT_REQUESTS` | `60` | Max requests per client within the starter limiter window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rolling window size for the starter limiter |
| `RATE_LIMIT_TRUST_PROXY_HEADERS` | `false` | Uses `X-Forwarded-For` when the proxy is trusted to set it correctly |
| `RATE_LIMIT_EXEMPT_PATHS` | `["/api/v1/health","/api/v1/ready"]` | Path prefixes excluded from starter limiter checks |
| `SIDEARM_REQUEST_TIMEOUT_SECONDS` | `20` | Timeout for Sidearm HTML fetch requests |
| `SIDEARM_FETCH_MAX_ATTEMPTS` | `3` | Maximum attempts for retryable Sidearm fetch failures |
| `SIDEARM_FETCH_BACKOFF_SECONDS` | `0.5` | Initial retry backoff in seconds; retries use exponential backoff |

## Deployment Notes

- Change `SECRET_KEY` before any non-development deployment.
- Set `DEV_MODE=false` in staging and production.
- PostgreSQL is the standard app database for local, staging, and production environments.
- Keep SQLite only as an isolated fallback for tests or temporary experiments.
- Set `CORS_ORIGINS` as a JSON array or comma-separated list of absolute
  HTTP(S) origins.
- Restrict `CORS_ORIGINS` to real application origins in deployed environments;
  wildcard origins are rejected when `DEV_MODE=false`.
- Keep `RATE_LIMIT_ENABLED=false` unless the project has chosen either the
  starter middleware or an external abuse-control layer intentionally.
- If you enable the starter middleware behind a reverse proxy, only set
  `RATE_LIMIT_TRUST_PROXY_HEADERS=true` when that proxy sanitizes
  `X-Forwarded-For`.
- Keep Sidearm retry settings conservative. The default retry policy only
  retries transient network errors plus HTTP 408, 429, and 5xx responses.

## Optional Documentation Deployment

The template includes a GitHub Pages docs deployment workflow in
`.github/workflows/docs.yml`.

- Keep it if the project will publish docs from GitHub Pages.
- Remove or disable it if documentation is hosted elsewhere.

## Security Automation Outputs

The template now includes:

- dependency audit artifacts from `.github/workflows/security-scan.yml`
- CycloneDX SBOM artifacts from `.github/workflows/sbom.yml`

Expected artifact filenames:

- `pip-audit-results.json`
- `npm-audit-results.json`
- `sbom-python.cdx.json`
- `sbom-javascript.cdx.json`

Document any additional project-specific environment variables here as the
application evolves.
