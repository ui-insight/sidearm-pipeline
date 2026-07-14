# 007 — Normalized long-form stat storage, not per-sport typed tables

**Status:** accepted

## Decision

Per-player, per-game statistics are stored in a single sport-agnostic table,
`player_game_stat(game_id, player_id, stat_key, value)` — one row per stat value —
paired with a `stat_definition(sport_slug, stat_key, display_name, aggregable,
higher_is_better, importance_weight)` reference table that describes each stat. We do
**not** use per-sport typed tables (e.g. a `wbb_game_stat` with `points`, `rebounds`,
`assists` columns).

## Context

The warehouse is explicitly multi-sport; women's basketball is only the first Release 1
slice. Records and leaderboards are the core value, and `stat_definition` also carries
`importance_weight`, which is the SID-defined notability rubric — so the reference table
does double duty (typing stats and encoding notability).

## Considered options

- **Per-sport typed tables** — strongly typed columns, but every new sport requires a new
  table, migration, parser mapping, and query code, and cross-sport queries must UNION
  heterogeneous tables. Optimizes for the current single sport and taxes every sport
  after it. Rejected.
- **Normalized long-form** (chosen) — adding a sport is inserting `stat_definition` rows,
  not authoring tables; records/leaderboards are `WHERE stat_key = '…'` plus aggregate or
  window functions; cross-sport queries are uniform. Fits CLAUDE.md rule 6 (ORM only).

## Consequences

- `value` is loosely typed (numeric); stat semantics (summable, higher-is-better) live in
  `stat_definition`, not in column types. Validation must lean on `stat_definition` rather
  than the schema.
- Sport fan-out becomes primarily data entry plus parser coverage, not schema work.
- The notability rubric has a natural home (`stat_definition.importance_weight`) instead of
  a separate bolt-on structure.
