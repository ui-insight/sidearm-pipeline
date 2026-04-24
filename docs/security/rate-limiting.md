# Rate Limiting Guidance

This template does not force rate limiting on by default, but production
deployments should choose an abuse-control strategy before exposing public
traffic.

## Recommended Baseline

Use rate limiting in layers:

1. Apply coarse request limits at the reverse proxy, load balancer, ingress,
   CDN, or API gateway for any public-facing deployment.
2. Add application-aware limits in the backend for expensive, sensitive, or
   authentication-related endpoints when generic edge limits are not enough.

The default template keeps the development path simple by leaving backend rate
limiting disabled until a project opts in.

## Starter Backend Middleware

The backend includes an optional in-memory middleware hook in
`backend/app/rate_limit.py`, wired from `backend/app/main.py`.

- Enable it with `RATE_LIMIT_ENABLED=true`.
- Tune the limit with `RATE_LIMIT_REQUESTS` and
  `RATE_LIMIT_WINDOW_SECONDS`.
- Keep health and readiness probes exempt through `RATE_LIMIT_EXEMPT_PATHS`.
- Set `RATE_LIMIT_TRUST_PROXY_HEADERS=true` only when a trusted reverse proxy
  sanitizes `X-Forwarded-For`.

Example `.env` values:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_TRUST_PROXY_HEADERS=true
RATE_LIMIT_EXEMPT_PATHS=["/api/v1/health","/api/v1/ready"]
```

When enabled, the starter middleware:

- applies a per-client rolling window inside one app process
- returns HTTP `429` with `Retry-After` when the limit is exceeded
- emits `X-RateLimit-*` response headers for non-exempt requests

## Limits Of The Starter Middleware

The built-in middleware is intentionally lightweight. It is useful for:

- local or low-volume deployments
- simple internal tools running as a single backend process
- establishing a clear code location for future rate-limiting work

It is not sufficient by itself for:

- horizontally scaled deployments
- shared limit state across multiple app processes
- bot mitigation, credential-stuffing defense, or more advanced abuse controls

For those cases, replace or extend `backend/app/rate_limit.py` with a
deployment-appropriate solution, such as:

- rate limits enforced at nginx, an ingress controller, or an API gateway
- a shared-store backend limiter that uses Redis or another central service
- stricter per-route controls for auth, upload, export, or expensive search
  endpoints

## Operational Guidance

- Keep liveness/readiness endpoints exempt so orchestrators and uptime checks do
  not lock themselves out.
- Document the chosen rate-limiting owner: backend app, proxy/gateway, or both.
- Revisit limits whenever you add login, file uploads, bulk exports, or other
  high-cost endpoints.
- Link the chosen approach from production rollout or security review artifacts.
