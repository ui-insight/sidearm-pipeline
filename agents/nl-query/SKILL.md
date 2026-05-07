# Skill: nl-query

**Capability Tier**: 2 — Read-only (see ADR-003)

## Purpose

Answer natural language questions about the games database by translating them to
SQL and executing a read-only query. Returns both the generated SQL and a plain
English summary of the results.

## Inputs

| Field | Type | Constraint |
|-------|------|-----------|
| `question` | str | Max 500 characters |

## Outputs

| Field | Description |
|-------|-------------|
| `question` | Echo of the original question |
| `sql` | Generated SELECT statement (or null if no SQL was needed) |
| `rows` | Raw result rows as a list of dicts |
| `answer` | Natural language summary of the results |
| `agent_run_id` | ID of the `AgentRun` record for full provenance tracing |

## Constraints

- **Read-only**: The agent only executes `SELECT` statements. Any SQL not beginning
  with `SELECT` (case-insensitive) is rejected before execution.
- The agent executes queries inside a read-only transaction as an additional safeguard.
- The agent never writes to the database, regardless of what the model generates.
- Maximum result rows returned: 100.

## Queryable Tables

The agent introspects the live SQLAlchemy metadata to build its schema description.
Key tables include:

| Table | Key columns |
|-------|------------|
| `games` | id, sport, season, game_date, home_team, away_team, home_score, away_score |
| `team_stats` | game_id, stat_name, home_value, away_value |
| `player_stat_groups` | game_id, category, team, columns, rows |
| `scoring_plays` | game_id, period, clock, team, description |
| `generated_content` | game_id, headline, recap, model, generated_at |
| `agent_runs` | agent_name, status, eval_score, human_verdict, started_at |

## MCP Upgrade Path

The nl-query agent can be upgraded to a tool-using MCP server that exposes:
- `describe_schema()` — returns live table/column metadata
- `execute_read_query(sql)` — runs a SELECT and returns rows

This makes the agent truly tool-using (multi-step) rather than one-shot.
Implementation requires the `mcp` Python SDK and a separate server process or
embedded FastAPI mount. Defer to a follow-up PR.
