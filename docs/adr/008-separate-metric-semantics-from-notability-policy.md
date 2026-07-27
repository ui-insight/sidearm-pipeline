# ADR-008: Separate Metric Semantics from Notability Policy

## Status

Accepted

ADR-009 clarifies how prior verdicts may calibrate a new suggestion's score
without mutating `StatDefinition` or an existing Notability-policy version.

## Context

`StatDefinition` describes objective properties of a metric: its entity scope,
value type, unit, aggregation method, comparison direction, qualifying threshold,
display rules, and source aliases. Those properties should change rarely because
they determine whether warehouse calculations are valid.

Notability is editorial. The SID may tune the relative importance of a metric,
thresholds, or suppression rules as communication priorities change. Verdicts on
achievement suggestions should inform explicit policy revisions without changing
the meaning of the underlying facts or silently rewriting earlier decisions.

ADR-007 originally identified `StatDefinition.importance_weight` as a convenient
home for the first notability rubric. Coupling an evolving editorial preference to
stable metric semantics would make historical decisions difficult to reproduce.

## Decision

`StatDefinition` stores metric semantics and boolean eligibility for Record Book
and Notability use. It does not store an editorial `importance_weight`.

Metric weights, thresholds, and suppression rules will live in a separate,
versioned `NotabilityPolicy` model when the achievement workflow is implemented.
Achievement suggestions and SID verdicts will retain the policy version used for
their evaluation. Verdict history may motivate a new policy version but will not
mutate an existing version or a `StatDefinition`.

This decision does not prohibit a separately documented, reproducible feedback
calibration over prior verdict counts. ADR-009 governs that implemented behavior.

This decision supersedes only ADR-007's placement of `importance_weight`; the
accepted long-form stat-storage decision remains unchanged.

## Consequences

- Metric aggregation and comparison behavior remains stable as editorial
  priorities evolve.
- Historical suggestions can be reproduced against the policy version that
  generated them.
- The normalized warehouse can be built before the Notability workflow without
  inventing premature weights.
- The later achievement phase requires a versioned policy model and an explicit
  association between evaluated suggestions and policy versions.
