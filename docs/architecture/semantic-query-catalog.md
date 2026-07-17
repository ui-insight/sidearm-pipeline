# Semantic Query Catalog

The semantic query catalog is the bounded set of questions that the application
can answer from reviewed SQLAlchemy queries. It implements
[ADR-005](../adr/005-semantic-layer-for-nlq.md): an interface or future NLQ layer
may select a stable query ID and supply typed parameters, but it cannot author SQL
or invent a metric.

The Release 1 catalog is scoped to women's basketball. Each result returns
warehouse-computed facts, source evidence, the applicable Coverage Window, and a
count of unresolved quality issues in scope.

## Question-to-query mapping

| Query ID | Supported questions | Typed parameters | Warehouse grain |
| --- | --- | --- | --- |
| `team_season_record` | Idaho's overall, conference, non-conference, or opponent-specific record in a season | `season`, `conference_scope`, optional `opponent` | Final games |
| `stat_leaders` | Career or season leaders for a vetted Record Book metric | `stat_key`, `scope`, optional `season`, `limit` | Authoritative player-season facts |
| `opponent_stat_leaders` | Season leaders for a vetted metric against one opponent | `stat_key`, `season`, `conference_scope`, `opponent`, `limit` | Player-game facts |
| `player_career_total` | One player's career aggregate for a vetted metric | `player_id`, `stat_key` | Authoritative player-season facts |
| `player_game_split` | One player's metric aggregate by season, conference scope, venue, or opponent | `player_id`, `stat_key`, optional `season`, `conference_scope`, `venue_scope`, `opponent` | Player-game facts |

Only player metrics whose `StatDefinition` is Record Book eligible and has a
supported aggregation and comparison rule may be selected. The service rejects
unknown query IDs during request validation and returns a not-found response for
unvetted metrics or players outside the women's basketball program.

## API contract

`GET /api/v1/semantic-queries/catalog` returns the stable query IDs, example
question templates, and the JSON Schema generated from each Pydantic parameter
model. Consumers should use this response to discover supported questions rather
than construct arbitrary database requests.

`GET /api/v1/semantic-queries/options` returns the women's basketball seasons,
Record Book metrics, canonical players and observed opponents with vetted game
evidence, and supported leaderboard sizes that currently have warehouse
evidence. Each player and opponent option includes its available game-fact
seasons. The Exploratory Workspace uses these server-governed options instead of
maintaining a second list of available filters in the frontend.

`POST /api/v1/semantic-queries/execute` accepts a discriminated request. For
example, a conference-only player split is:

```json
{
  "query_id": "player_game_split",
  "player_id": 42,
  "stat_key": "points",
  "season": "2025-26",
  "conference_scope": "conference",
  "venue_scope": "all"
}
```

The response repeats `query_id` and wraps the query-specific typed result:

```json
{
  "query_id": "player_game_split",
  "result": {
    "player_id": 42,
    "stat_key": "points",
    "value": "184.000000",
    "games_count": 12,
    "coverage": {
      "grain": "game",
      "first_season": "2025-26",
      "last_season": "2025-26",
      "completeness": "complete"
    },
    "games": []
  }
}
```

The abbreviated example omits other response fields. Source URLs and snapshot IDs
are included on the evidence rows returned by career-total, opponent-leaderboard,
and game-split queries.

## Exploratory Workspace consumer

The first workspace slice is the **Season desk** at `/workspace`. For all
opponents, it combines `team_season_record` with season-scoped `stat_leaders`, so
the leaderboard remains grounded in authoritative cumulative season facts. When
an SID selects one observed opponent, the desk applies the same season,
conference scope, and opponent to `team_season_record` and
`opponent_stat_leaders`. That second leaderboard aggregates only vetted final,
non-exhibition player-game facts and keeps every contributing game source
attached to the ranked player. The game ledger, coverage statements, and open
quality-issue counts remain beside the result, and the assembled evidence can be
exported as CSV.

The **Player comparison** at `/workspace/compare` applies one shared season,
metric, conference, venue, and optional opponent filter set to two distinct
canonical players. It executes `player_game_split` independently for each
player, then aligns the returned evidence by canonical game ID for inspection.
The frontend does not derive a new authoritative aggregate: displayed totals,
games reviewed, coverage, quality counts, and source links all come from the
governed responses. The comparison and aligned evidence can also be exported as
CSV.

Both workspace routes encode their complete validated filter state in canonical
query parameters. Incoming parameters are checked against the current
server-governed options, and stale values are replaced with valid defaults. This
makes a copied workspace URL a complete, reproducible view of the governed
question.

Users can also give that same route-and-filter configuration a name. These saved
views are stored only in the current browser, are limited to 20 validated
entries, and do not contain result facts or source evidence. They are explicitly
not account-synced or team-shared; opening one still executes the current
governed query. Account-backed sharing, multi-player comparisons, multi-season
opponent leaderboards, and free-form questions remain later Phase 6 work built on
the same bounded catalog.

## Deterministic boundary

All aggregation, record classification, filters, and ranking are expressed as
reviewed SQLAlchemy statements over the warehouse. Application code validates and
serializes results; it does not accept raw SQL. A future AI layer may choose one of
these query IDs and fill its documented parameters. If no catalog entry matches a
question, the correct answer is that the question is not supported yet.

Adding a query requires:

1. a stable query ID and typed Pydantic request model
2. a human-authored SQLAlchemy query over canonical warehouse models
3. source evidence and Coverage Window context in its response
4. fixture-backed tests for filters, aggregation, and rejection behavior
5. an entry in the question-to-query mapping above
