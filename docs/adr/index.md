# Architecture Decisions

Architecture Decision Records (ADRs) capture significant technical choices and
their tradeoffs.

## When to Add an ADR

Add an ADR when a decision is likely to affect future contributors, generated
code, deployment expectations, or cross-team consistency.

Common triggers:

- introducing a new dependency or platform service
- changing deployment or authentication architecture
- defining a styling or data-model convention
- introducing a module boundary or ownership rule

## ADR Template

```markdown
# ADR-NNN: Title

## Status
Accepted | Proposed | Deprecated | Superseded

## Context
What decision needs to be made?

## Decision
What are we choosing?

## Consequences
What benefits, costs, and follow-on obligations come with that choice?
```

## Current ADRs

- [ADR-001: Preserve Explicit Template Customization Points](001-template-customization.md)
- [ADR-002: Tailwind CSS Only](002-tailwind-only.md)
- [ADR-005: Curated Semantic Layer for NLQ](005-semantic-layer-for-nlq.md)
- [ADR-006: Release 1 Is Internal-SID-First](006-release1-internal-sid-first.md)
- [ADR-007: Normalized Long-Form Stat Storage](007-normalized-long-form-stat-storage.md)
- [ADR-008: Separate Metric Semantics from Notability Policy](008-separate-metric-semantics-from-notability-policy.md)
- [ADR-009: Reproducible Verdict Feedback Calibration](009-reproducible-verdict-feedback-calibration.md)
