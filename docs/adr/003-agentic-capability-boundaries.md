# ADR-003: Agentic Capability Boundaries

## Status
Accepted

## Context
The pipeline is adding AI agents that can read and write application data. Without
explicit boundary definitions, it is unclear which agents may take autonomous action,
which require human oversight, and which are strictly read-only. Different risk profiles
require different review gates.

Current agents:
- **recap-writer** — generates game coverage from boxscore data
- **nl-query** — answers natural language questions about the games database

## Decision

### Capability Tiers

| Tier | Label | Definition | Examples |
|------|-------|------------|---------|
| 0 | Autonomous | No human approval required before side effects. | Scheduled boxscore ingestion (Phase 3 scheduler). |
| 1 | Human-gated | Agent produces output; a human must approve before any write happens. | recap-writer: output is staged in `AgentRun`, `GeneratedContent` is only created after `verdict=approved`. |
| 2 | Read-only | Agent reads the database; it never writes. | nl-query: reads game data, returns answer, never persists changes. |

### Where the boundary lives in code

- `AgentRun.human_verdict` (`"approved" | "rejected" | None`) gates persistence for
  Tier-1 agents.
- `POST /api/v1/agent-runs/{id}/verdict` is the **only** path that creates
  `GeneratedContent` from a recap-writer run. No other code path may do so.
- nl-query enforces its read-only constraint by:
  1. Rejecting any SQL that does not begin with `SELECT` (case-insensitive).
  2. Executing inside a read-only transaction to be safe.

### Rollback procedure

- **Tier-0 (scheduler)**: Re-run `POST /api/v1/games/{id}/ingest` to refresh data.
  Ingestion is idempotent; snapshots are retained for audit.
- **Tier-1 (recap-writer)**: Reject the `AgentRun` via `verdict=rejected`.
  `GeneratedContent` is never created, so there is nothing to undo.
- **Tier-2 (nl-query)**: No writes occur; no rollback is needed.

### Adding a new agent

Before shipping a new agent:
1. Assign it a capability tier in this document.
2. If Tier 0, document why human oversight is not required.
3. If Tier 1, confirm `AgentRun.human_verdict` gates all writes.
4. If Tier 2, add a SQL guard and read-only transaction to the agent.
5. Add an entry to `agents/<name>/SKILL.md` documenting the tier explicitly.

## Consequences

- All recap generation goes through a human review step. This adds latency but
  prevents incorrect AI-generated content from being published automatically.
- The nl-query agent cannot modify data even if the model produces a mutating SQL
  statement; the guard is enforced at the application layer, not only by DB permissions.
- The `AgentRun` table provides a full audit trail: every invocation, its inputs,
  outputs, eval scores, and verdict are permanently recorded.
- Future agents must fit into one of the three tiers or this ADR must be amended.
