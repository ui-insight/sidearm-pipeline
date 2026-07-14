# 005 — Curated semantic layer for natural-language query, not free text-to-SQL

**Status:** accepted — records the direction chosen instead of the shelved
`003-agentic-capability-boundaries` / `004-mcp-tool-transport` approach.

## Decision

The Ask-a-Question (NLQ) capability answers the SID's natural-language questions
over a **curated semantic layer** — a set of human-authored, parameterized queries
(vetted metrics and dimensions) over the warehouse. The AI interprets the question,
selects a query, and fills parameters; it never authors raw SQL and never computes
numbers. All facts come from the warehouse (the **deterministic-facts principle**).

## Context

An earlier prototype (shelved on `feature/phase4-validation-publish`) let an LLM
generate arbitrary SQL, guarded only by a regex that the statement started with
`SELECT`, running on a full-privilege database connection. Two problems make that
unacceptable for this system: (1) an LLM can write subtly wrong SQL — wrong joins or
filters — and state a confidently wrong number, and the SID may quote that number
publicly or to a coach; (2) LLM-authored SQL over a privileged connection is a
security and denial-of-service risk.

## Considered options

- **Free text-to-SQL** — broadest question range, but can produce wrong facts and
  carries the security risk above. Rejected.
- **Curated semantic layer** (chosen) — facts are always correct because the SQL is
  human-authored and reviewed; questions outside the layer simply aren't answerable
  yet.

## Consequences

- The range of answerable questions is bounded by the semantic layer and grows
  deliberately over time; "I can't answer that yet" is an acceptable Release 1 answer.
- The "agentic tools" idea from the shelved work is preserved in safer form: the AI
  composes answers by calling vetted query tools, not by writing SQL.
