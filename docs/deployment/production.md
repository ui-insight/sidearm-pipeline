# Production Deployment

This template is designed to start simple in development and harden cleanly for
production deployments.

Use the [Production Readiness Gate](production-readiness.md) as the single
launch checklist before go-live. This page focuses on deployment expectations
and topology.

## Baseline Expectations

- run the FastAPI backend behind a production ASGI server
- standardize on PostgreSQL 16 via asyncpg
- manage schema changes through Alembic migrations
- terminate TLS at nginx, a load balancer, or your platform edge
- store secrets in environment variables or a managed secret store
- review CORS, upload paths, and log retention before launch

## Readiness Link

Before production launch, walk through the consolidated
[Production Readiness Gate](production-readiness.md), which links out to:

- deployment configuration and topology expectations
- security review, CORS, and access-control decisions
- governance, backups, and data classification requirements
- dependency scan and SBOM review steps
- logging and monitoring readiness

## Frontend nginx Security Headers

The starter frontend nginx config includes a conservative baseline for deployed
static traffic:

- `Content-Security-Policy`
- `Referrer-Policy`
- `X-Content-Type-Options`
- frame restrictions via both `X-Frame-Options` and `frame-ancestors`

Before production launch, review and adjust these headers for your actual app:

- tighten or relax the starter CSP if you need third-party scripts, fonts,
  images, analytics, or embeds
- revisit frame restrictions if the app must be embedded inside another site or
  platform
- review the referrer policy if integrations depend on fuller referrer data
- re-test the final header set after introducing custom assets, authentication
  flows, or external services

## Container Strategy

The included Docker setup is a starting point, not a complete institutional
deployment standard. Before production launch, confirm:

- backend containers still have write access to the configured upload path after
  switching to the non-root runtime user
- if you are reusing an older Docker volume for uploads, reset it or adjust its
  ownership before adopting the non-root backend image
- frontend nginx now listens on container port `8080` so it can run without root
- image provenance and update cadence
- persistent storage for uploads if your app needs them
- backup and restore plans
- monitoring and alerting expectations

## Container Hardening Baseline

The template now includes a modest runtime-hardening baseline:

- the backend image installs dependencies during build but serves requests as an
  unprivileged `app` user
- the frontend image keeps the existing multi-stage build and runs nginx as the
  bundled `nginx` user on port `8080`
- nginx stores its PID and temporary files under `/tmp` so the frontend
  container does not need root-owned runtime paths

These defaults improve reuse, but production teams should still review:

- digest pinning or another base-image provenance policy
- read-only root filesystems, dropped Linux capabilities, and seccomp/AppArmor
  profiles where the platform supports them
- image scanning, signing, and patch cadence in the deployment pipeline
- external storage ownership and retention for uploads or generated files

Use this page to document your project's final production topology once the
deployment target is known.
