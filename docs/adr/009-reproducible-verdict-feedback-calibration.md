# ADR-009: Reproducible Verdict Feedback Calibration

## Status

Accepted as documentation of the implemented achievement-scoring behavior.

## Context

ADR-008 separates stable metric semantics from versioned editorial weights and
thresholds. The SID verdict workflow subsequently introduced a conservative
feedback signal: repeated rejection of the same metric and achievement type can
reduce its priority in later detection runs.

Leaving this behavior outside the decision record would make the effective
Notability score appear to come only from the referenced policy version. Mutating
the policy or metric definition in response to every verdict would instead make
historical configuration difficult to understand.

## Decision

New Achievement Suggestions may apply feedback calibration version 1 to the base
score produced by the referenced Notability policy:

```text
base score = scope weight * metric importance weight
multiplier = (prior approvals + 2) / (prior approvals + prior rejections + 2)
final score = base score * multiplier
```

The multiplier is bounded above by `1.0`, so verdict feedback may down-rank a
pattern but never promote it above the explicit policy score. Counts are scoped
to the same metric definition and achievement type.

Every resulting suggestion stores the base score, prior approval/rejection
counts, multiplier, final score, and Notability-policy version in its context.
Prior suggestion rows and facts are not rewritten.

A change to the formula, smoothing constants, scope, or interpretation requires
a new ADR and a distinguishable calibration version in persisted suggestion
context. A change to editorial weights, thresholds, or suppression rules requires
a new Notability-policy version. Neither mechanism may change `StatDefinition`
semantics.

## Consequences

- The implemented score is explainable from persisted suggestion context.
- SID feedback affects later prioritization without silently mutating an existing
  policy or historical suggestion.
- Verdicts remain editorial signals and cannot change facts, metric semantics, or
  Coverage Windows.
- The current schema stores only the latest verdict on a suggestion, not an
  immutable sequence of verdict events. Production-grade audit history remains a
  separate model gap.
- Before changing feedback calibration, implementation must add an explicit
  calibration-version value to persisted context and retain regression coverage.
