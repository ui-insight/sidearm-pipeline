# ADR-013: Human-Gated Distribution Through a Durable Outbox

## Status

Accepted for prototype implementation on July 27, 2026. Athletics feedback is
required before production channel enablement.

## Context

Ready copy must be adaptable to website, email, social, and future institutional
channels. Sending directly from an Article editor would couple canonical content to
one platform, hide the exact submitted payload, and make retries vulnerable to
duplicate publication.

External delivery is a materially different action from generating, editing,
previewing, or exporting copy. It requires individual authorization, an exact target
selection, reliable attempt history, and credentials that never enter editorial data.

## Decision

The canonical Article remains channel-neutral. A ready Article Version produces
immutable Article Renditions for named Channel Profiles. Any AI-assisted rendition
transformation remains within the source Evidence Bundle and passes the same factual
validators plus channel Style Guide rules.

An authenticated `publisher` must preview exact rendition payloads and explicitly
confirm selected targets. That confirmation creates the Distribution Submission,
targets, and outbox records in one database transaction. No model or schedule may
perform this action.

Workers claim durable outbox records and call channel adapters with stable idempotency
keys. Each attempt appends a normalized receipt or classified failure. Retries reuse
the target's logical idempotency key and never create a second logical submission.

Channel Profiles store capabilities, destination metadata, enabled state, and secret
references only. Secret values stay in approved environment-backed secret storage and
must not appear in database rows, logs, receipts, or payload previews.

The generic signed-webhook adapter is the first implementation contract. All nonlocal
profiles remain disabled until per-user RBAC and security review are complete. The
first live institutional adapter requires a separate HITL decision in issue #151.

## Consequences

- Editorial readiness and external delivery have distinct, auditable human gates.
- Channel-specific formatting does not alter the canonical Article.
- Transactional outbox work survives process restarts and supports safe retries.
- Per-user identity and publisher authorization are prerequisites for live delivery.
- Adapter implementation must normalize receipts, timeouts, retryability, and errors.
- Export remains useful without implying that the application delivered content.
