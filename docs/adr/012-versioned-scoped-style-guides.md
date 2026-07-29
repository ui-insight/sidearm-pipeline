# ADR-012: Versioned and Scoped Editorial Style Guides

## Status

Implemented for the prototype on July 29, 2026. Athletics feedback is required
before production channel enablement.

## Context

Athletics copy must follow shared institutional guidance while also accommodating
sport, article-type, and channel constraints. Hard-coded prompts hide editorial policy
inside application releases. Mutating database rules in place would make past AI and
human decisions impossible to reproduce.

Channel limits such as social length are not appropriate for the canonical Article,
while shared naming, tone, and factual rules should apply everywhere.

## Decision

Style Guides are immutable versions composed of stable-keyed rules. Active rules
resolve in deterministic order:

1. shared athletics
2. sport
3. article type
4. channel, for Article Renditions only

Rules declare category, severity (`error`, `warning`, or `guidance`), enforcement type,
and whether a more specific rule explicitly overrides a shared rule. Supported
enforcement types include deterministic lint, required or forbidden terminology,
length or structure constraints, and writer instructions.

Conflicting active rules are rejected before activation. An activated successor does
not mutate its predecessor. Every Article Version and Article Rendition stores the
resolved Style Guide version identifiers and a snapshot hash.

The prototype stores immutable guide content and stable-keyed rules together in one
version row. Lifecycle metadata is separate from the hashed content. New versions
begin as `draft`; activation records actor and effective time and atomically retires
the prior active version in the same guide lineage. Explicit retirement is also
available, but the final effective shared-athletics guide cannot be retired.

Errors block the operation defined by the rule. Warnings require correction or an
attributed human acknowledgement with a reason. Guidance is visible but nonblocking.

## Consequences

- Editorial policy can evolve without rewriting historical drafts.
- Deterministic rules and model instructions have a shared governance surface.
- Channel rules cannot accidentally mutate the canonical Article.
- Maintainers need activation, preview, conflict-detection, and retirement workflows.
- A seeded default Style Guide is required before management UI exists.
- Approved before/after examples may be added in a successor decision, but they are not
  automatically learned from editor activity.
