# ADR-010: Evidence-Bound Editorial Article Generation

## Status

Accepted for prototype implementation on July 27, 2026. Athletics feedback is
required before production channel enablement.

## Context

The Athletic Data Warehouse already detects Achievement Suggestions from verified
facts and constrains AI ranking to server-generated phrasing. The separate legacy
`GeneratedContent` workflow sends a broad boxscore payload to a model and stores recap,
spotlight, and social text without approved-suggestion gating, claim-level evidence,
or deterministic factual validation.

Long-form writing creates more opportunity for an LLM to infer plausible but
unsupported narratives. Prompt instructions alone do not satisfy the
Deterministic-facts principle because they cannot prove which inputs support each
output claim.

## Decision

An Article writer may use only an immutable, hashed Evidence Bundle created by an
authenticated human from approved Achievement Suggestions and intentionally selected
warehouse facts.

The writer returns strict structured content whose factual blocks reference Evidence
Bundle item IDs. Before an AI Article Version is persisted, deterministic validation
must confirm evidence membership, allowed numerals and entities, comparative claim
scope, Coverage Window wording, and blocking Style Guide rules. Any blocking failure
rejects the entire output without partial persistence.

The model cannot browse, query arbitrary warehouse tables, fetch source URLs, approve
suggestions, expand its Evidence Bundle, or decide that content is ready.

Human-added facts require a source reference and explicit verification attestation.
They remain distinguishable from warehouse-computed facts in Article Version audit
metadata.

The full contract is defined in
[Editorial Article Workflow](../architecture/editorial-article-workflow.md).

## Consequences

- AI copy remains traceable to a reproducible factual boundary.
- Coverage Window qualifiers remain enforceable in long-form writing.
- Writers have less freedom to invent narrative transitions or external context.
- Evidence Bundle construction and claim validation become first-class services.
- Human-added facts need an explicit review path rather than silent free-text entry.
- The legacy GeneratedContent path cannot be the production editorial path and will be
  retired under issue #152 after replacement parity exists.
