# Production Readiness Gate

Use this page as the explicit go/no-go checklist before launching a project
built from this template. It consolidates the minimum launch gates spread across
deployment, security, governance, and CI documentation.

## Required Before Launch

### Runtime and Deployment

- [ ] `DEV_MODE` is set to `false`.
  See [Configuration](configuration.md) and [Production Deployment](production.md).
- [ ] `SECRET_KEY` is changed from the template default and managed through a
  real secret store or deployment environment.
  See [Configuration](configuration.md) and [Security Overview](../security/overview.md).
- [ ] HTTPS is enabled at the reverse proxy, load balancer, or platform edge.
  See [Production Deployment](production.md).
- [ ] `CORS_ORIGINS` is limited to known production frontend origins.
  See [Configuration](configuration.md) and [Security Overview](../security/overview.md#cors).
- [ ] The deployment topology, runtime owner, and rollback path are documented.
  See [Production Deployment](production.md).

### Data and Database

- [ ] PostgreSQL is the active application database in the deployed environment.
  See [Data Governance](../governance/data-governance.md).
- [ ] Alembic migrations are the planned schema-management path.
  See [Production Deployment](production.md) and [Data Governance](../governance/data-governance.md#production).
- [ ] Backups are configured and a restore path has been tested.
  See [Production Deployment](production.md) and [Data Governance](../governance/data-governance.md#production).
- [ ] Data classification, retention expectations, and any applicable
  regulations are documented.
  See [Data Governance](../governance/data-governance.md) and [Data Classification](../governance/data-classification.md).

### Security and Access

- [ ] Authentication requirements are explicitly decided: public app, SSO,
  JWT/session-based auth, or another documented pattern.
  See [Security Overview](../security/overview.md).
- [ ] Authorization / RBAC expectations are implemented and documented for any
  protected resources.
  See [Security Overview](../security/overview.md#authorization).
- [ ] File upload restrictions, storage paths, and access controls are defined
  if uploads are enabled.
  See [Security Overview](../security/overview.md#file-uploads).
- [ ] Rate limiting or another abuse-control approach is selected before
  production traffic.
  See [Rate Limiting Guidance](../security/rate-limiting.md).
- [ ] The institutional security review checklist has been completed or
  formally accepted by the project owner.
  See [Institutional Review](../security/institutional-review.md).

### Dependency and Supply Chain

- [ ] Backend and frontend dependency updates have been reviewed recently.
  See [Security Overview](../security/overview.md#dependency-security).
- [ ] CI dependency scan artifacts have been reviewed:
  `pip-audit-results.json` and `npm-audit-results.json`.
  See [Security Overview](../security/overview.md#security-artifacts).
- [ ] CI SBOM artifacts are generated and retained:
  `sbom-python.cdx.json` and `sbom-javascript.cdx.json`.
  See [Configuration](configuration.md#security-automation-outputs).

### Observability and Operations

- [ ] Logging is enabled at a level appropriate for production support.
  See [Production Deployment](production.md) and [Security Overview](../security/overview.md#production-checklist).
- [ ] Monitoring and alerting expectations are defined for the deployment
  target, even if the implementation is external to this repo.
  See [Production Deployment](production.md).
- [ ] Security reporting and operational contacts are documented.
  See the repository `SECURITY.md` policy alongside
  [Security Overview](../security/overview.md).

## Recommended Follow-Up Hardening

These items are not intended to block an initial launch when the required gates
above are satisfied, but they should be planned and tracked explicitly:

- [ ] Structured request logging and request IDs
- [ ] Stronger rate limiting or bot-abuse controls
- [ ] Hardened container images and runtime users
- [ ] More extensive browser or Postgres-backed CI coverage
- [ ] Periodic backup-restore drills and incident-response exercises
- [ ] Tighter CSP, security headers, and session/token handling for the final deployment model

## How To Use This Gate

1. Review this page before opening a production readiness or launch approval PR.
2. Link any open follow-up hardening items to tracked GitHub issues.
3. Keep environment-specific details in your project docs, but leave this page
   as the reusable template baseline.
