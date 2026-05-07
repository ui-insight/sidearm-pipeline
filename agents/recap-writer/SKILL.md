# Skill: recap-writer

**Capability Tier**: 1 — Human-gated (see ADR-003)

## Purpose

Generate publication-ready game coverage from a Sidearm boxscore. Output includes
a headline, a 250–350 word AP-style recap, a player spotlight, and a social post.

## Inputs

| Field | Type | Description |
|-------|------|-------------|
| `game_id` | int | ID of the ingested `Game` record |
| `trigger` | str | `"manual"` or `"api"` |

The agent serializes the full game (team stats, player stats, scoring plays) into
a compact JSON payload before calling the model.

## Outputs

The agent produces a `GeneratedCoverage` object persisted inside `AgentRun.output_payload`:

| Field | Constraint |
|-------|-----------|
| `headline` | ≤ 90 characters |
| `recap` | 250–350 words, AP style, past tense, no emoji |
| `spotlight_player` | Player name as written in stat tables ("Last, First") |
| `spotlight_body` | 2–3 sentences with concrete stat-line numbers |
| `social_post` | ≤ 280 characters, final score + stat nugget |

## Constraints

- **Must not invent statistics, quotes, attendance, weather, or injuries** — every
  number cited must appear in the provided boxscore JSON.
- AP style, third person, past tense.
- No emoji in recap or spotlight. At most one tasteful emoji in social post.
- Hype must be measured. Avoid "all cylinders", "statement win", "came to play".

## Human Review Requirement

Per ADR-003 Tier 1, the agent's output is **staged** as an `AgentRun` record.
`GeneratedContent` is **not** created until a human calls:

```
POST /api/v1/agent-runs/{id}/verdict
{"verdict": "approved"}
```

Calling with `"rejected"` discards the run; no content is persisted.

## Evaluation Criteria

Deterministic checks run automatically after generation:

| Check | Pass condition |
|-------|---------------|
| `score_present` | Both final scores appear in the recap |
| `teams_mentioned` | Both team names appear in the recap |
| `word_count` | Recap is 250–350 words |
| `headline_length` | Headline ≤ 90 characters |
| `social_length` | Social post ≤ 280 characters |
| `stats_cited` | At least one stat from the team stats table is cited |

An optional LLM-as-judge scorer (requires `ANTHROPIC_API_KEY`) rates overall
factual accuracy and style on a 0.0–1.0 scale.

## Upgrade Path

The prompt is versioned via SHA-256 hash stored in `AgentRun.prompt_version`.
To update the prompt, edit `agents/recap-writer/prompt.md` and redeploy.
All historical runs retain their prompt version for auditability.
