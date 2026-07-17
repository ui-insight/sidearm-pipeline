# Security Overview

This document describes the security architecture and practices for Vandals Stats Pipeline.

The application includes a small shared-credential session gate for internal
prototype deployments. It does not yet include individual accounts, a user
model, or RBAC enforcement. Treat the prototype gate as a temporary access
boundary, not a production identity system.

## Authentication

- **Status**: optional shared prototype credential configured by environment
  variables
- **Session**: short-lived HS256 token held in an HttpOnly, same-site cookie
- **Password storage**: use bcrypt or an equivalent adaptive password hasher if
  you add username/password login
- **Token/session lifetime**: keep expiration configurable via environment
  variables or settings
- **Implementation location**: add auth logic under `backend/app/auth/` and
  wire FastAPI dependencies through `backend/app/api/deps.py`

## Authorization

- **Status**: RBAC is an extension point, not a built-in feature
- **Shared-view implication**: all authenticated operators can create, open,
  and delete deployment-wide workspace views; the recorded creator is context,
  not an ownership check
- **Suggested baseline**: define roles appropriate to your application and
  enforce them with FastAPI dependencies on protected endpoints
- **Documentation**: record your chosen role model and protected resources in
  `docs/security/` and `docs/governance/`

## Input Validation

- All API inputs validated through Pydantic schemas
- Frontend forms should implement client-side validation as well
- Never trust client-side validation alone — always validate server-side

## CORS

- Configured via `CORS_ORIGINS` environment variable
- Restricted to known frontend origins
- Must be properly configured for production deployment

## File Uploads

- Files stored with UUID-prefixed names to prevent path traversal
- Served through authenticated or otherwise access-controlled API endpoints when
  the data classification requires it
- File type and size validation required
- Never serve uploaded files directly from the filesystem

## Secrets Management

- All secrets via environment variables (`.env` files, never committed)
- The application refuses to start in production with default `SECRET_KEY`
  or wildcard CORS origins
- Use `SECRET_KEY` for auth/session signing or similar sensitive application
  needs once your project defines them
- See `.env.example` for all configurable secrets

## Logging and Request IDs

- The backend emits a request completion log line for each handled request.
- Responses include an `X-Request-ID` header for client-side correlation.
- If a caller provides `X-Request-ID`, the backend reuses it; otherwise it
  generates one.
- The default log format is plain text to stdout with timestamp, level, logger
  name, and `request_id`, which works well for local development and container
  log aggregation.

## Rate Limiting

- **Status**: optional starter middleware is available but disabled by default
- **Recommended baseline**: enforce coarse limits at the reverse proxy, load
  balancer, ingress, CDN, or API gateway for public traffic
- **Backend extension point**: `backend/app/rate_limit.py`, wired through
  `backend/app/main.py`
- **Default starter behavior**: a single-process, in-memory per-client rolling
  window that can be enabled with environment variables
- **Guidance**: see [Rate Limiting Guidance](rate-limiting.md) before enabling
  the starter middleware for production use

## Dependency Security

- **Dependabot** enabled for automated vulnerability alerts
- **pip-audit** scans Python dependencies in CI
- **npm audit** scans JavaScript dependencies in CI
- **CycloneDX SBOMs** generated in CI for Python and JavaScript dependencies
- Regular dependency updates via automated pull requests

### Security Artifacts

The template CI emits reviewable security artifacts:

- `pip-audit-results.json` from the Python dependency audit workflow
- `npm-audit-results.json` from the JavaScript dependency audit workflow
- `sbom-python.cdx.json` as the Python CycloneDX SBOM
- `sbom-javascript.cdx.json` as the JavaScript CycloneDX SBOM

These artifacts are intended for CI review and recordkeeping. Local generation
may require network access to install audit or SBOM tooling.

## Known Limitations

!!! warning "Development Defaults"
    The following are acceptable for development but must be addressed before production:

    - The shared prototype credential does not provide individual identity or
      RBAC; replace it before a production launch that requires accountability
    - If a project stores bearer tokens in localStorage during development,
      replace that with a safer production approach such as httpOnly cookies or
      another documented strategy
    - Default local PostgreSQL credentials and connection string (must be replaced for shared or production environments)
    - Optional SQLite fallback should stay limited to isolated local experiments
    - Default `SECRET_KEY` (must be changed)
    - `DEV_MODE=true` bypasses security checks

## Production Checklist

For the full launch gate, use the
[Production Readiness Gate](../deployment/production-readiness.md). The list
below is the security-specific slice of that broader review.

Before deploying to production, verify:

- [ ] `SECRET_KEY` changed from default
- [ ] `DEV_MODE` set to `false`
- [ ] Authentication approach selected and documented if the app is not fully public
- [ ] Authorization / RBAC model implemented for protected resources where required
- [ ] PostgreSQL configured as database
- [ ] CORS origins restricted to production domain(s)
- [ ] HTTPS configured (TLS termination at load balancer or reverse proxy)
- [ ] File upload limits configured
- [ ] Rate limiting configured
  See [Rate Limiting Guidance](rate-limiting.md).
- [ ] Logging and monitoring enabled
- [ ] Dependency audit passing (`pip-audit`, `npm audit`)
