# ADR-011: Append-Only Article Versions and Source Revalidation

## Status

Accepted for prototype implementation on July 27, 2026. Athletics feedback is
required before production channel enablement.

## Context

AI drafts, human revisions, validation findings, and approval decisions must remain
auditable. Updating one mutable headline/body pair would erase the path from verified
facts to submitted copy and make concurrent editing unsafe.

Warehouse reingestion can also change a source fact or Coverage Window after an Article
Brief is created. Silently keeping an unpublished draft ready would break the evidence
contract, while rewriting a delivered Article would destroy the historical record.

## Decision

Every AI or human save creates an immutable Article Version linked to its parent,
Evidence Bundle, resolved Style Guide, validation results, origin, and author or model.
No prior Article Version is edited in place.

Human saves use optimistic concurrency through `base_version_id`. A stale save is
rejected for explicit reconciliation rather than overwriting newer work.

An Article may point to one selected ready version, but the pointer does not make that
version mutable. Marking a version ready is an authenticated human action and requires
all blocking findings to be resolved.

When a linked Achievement Suggestion, source fact, source snapshot, approval state, or
Coverage Window changes, affected unpublished Articles enter `needs_revalidation`.
Refreshing creates a new Evidence Bundle and new version lineage. Existing delivered
versions and submissions remain immutable audit history, but cannot be reused for a new
submission without revalidation.

Verdicts also gain append-only event history before they become an external publishing
gate; the current latest-state columns may remain as a read optimization.

## Consequences

- Editors can compare, attribute, and recover every significant revision.
- Concurrent edits fail visibly instead of losing work.
- Reingestion cannot silently leave stale copy ready for distribution.
- Storage grows with each checkpoint and requires explicit retention policy.
- APIs must distinguish Article state, generation-job state, and distribution state.
- Delivered history remains truthful even when the warehouse later corrects a fact.
