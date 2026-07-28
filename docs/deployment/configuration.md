# Configuration Reference

This page describes the baseline environment variables included in the template.

## Core Application Variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/app` | Database connection string |
| `SECRET_KEY` | `change-me-in-production` | Application secret for auth/session signing or similar sensitive uses |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Reserved token lifetime setting for projects that add token-based auth |
| `PROTOTYPE_AUTH_ENABLED` | `false` | Enables the shared-credential prototype session gate |
| `PROTOTYPE_AUTH_USERNAME` | `prototype` | Shared prototype username supplied by the deployment environment |
| `PROTOTYPE_AUTH_PASSWORD` | empty | Shared prototype password; required when the gate is enabled |
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
| `ANTHROPIC_API_KEY` | empty | API credential for optional content generation and Achievement Suggestion ranking |
| `ANTHROPIC_BASE_URL` | empty | Optional Anthropic-compatible gateway base URL |
| `CONTENT_MODEL` | `claude-opus-4-7` | Model used by the existing game-content generator |
| `ARTICLE_MODEL` | empty | Model used by the evidence-bound Article writer; defaults to `CONTENT_MODEL` |
| `ARTICLE_GENERATION_MAX_TOKENS` | `4000` | Maximum output tokens for one Article writer request; valid range is 256–16000 |
| `ARTICLE_GENERATION_POLL_SECONDS` | `2` | Database polling interval for the durable Article generation worker |
| `ARTICLE_GENERATION_LEASE_SECONDS` | `300` | Worker lease duration before an abandoned `running` Article job is reclaimable |
| `ACHIEVEMENT_MODEL` | `claude-opus-4-7` | Model used only to rank and phrase verified Achievement Suggestions |
| `ACHIEVEMENT_AI_MAX_CANDIDATES` | `100` | Maximum verified candidates included in one ranking request; valid range is 1–100 |
| `NLQ_MODEL` | empty | Optional model for semantic questions; falls back to `ACHIEVEMENT_MODEL` |

## Deployment Notes

- Change `SECRET_KEY` before any non-development deployment.
- Keep prototype credentials in the deployment environment, never in source
  control. The prototype gate is a temporary shared-account control, not a
  replacement for individual accounts, SSO, or production RBAC.
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
- Keep AI credentials in the deployment environment. Achievement detection and
  direct semantic queries remain available when optional model access is absent;
  AI ranking, Article generation, and natural-language questions do not. A missing
  or unavailable Article provider creates a visible failed job while preserving the
  retryable Article Brief.
- Keep the Article worker lease longer than the expected provider request. Queued
  jobs and expired `running` jobs are read from PostgreSQL after service restart;
  no process-local queue is authoritative.

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
