# Data Lineage

This page records the as-built movement of data through Vandals Stats Pipeline at
migration `0010_achievement_review_verdicts`.

## Flow summary

```text
Sidearm schedule / roster / boxscore / cumulative statistics
    -> registry-governed fetch and parser
    -> source snapshot + ingest-run evidence
    -> canonical identity and normalized facts
    -> reconciliation, quality issues, and Coverage Windows
    -> Record Book / semantic queries / workspace / achievements
    -> SID review and exports
```

Public GoVandals HTML is the implemented source surface, but it is a fallback
publication surface rather than a permanent authoritative-source contract.

## As-built data flows

| Data set | Source and processing | Persisted storage | Consumers and boundaries |
|---|---|---|---|
| Source registry | Reviewed `backend/app/source_registry.json`, validated by Pydantic | Repository configuration, not a table | Restricts supported sport/source patterns and guides schedule, roster, boxscore, and season-stat fetching |
| Schedule discovery/import | Sidearm schedule HTML parsed into event summaries and known links | `games`, `event_sources`, `source_snapshots`, `ingest_runs` | Backfill/current-season synchronization and game APIs; schedule preview can run without writes |
| Roster and player identity | Sidearm roster/bio links parsed; namespaced external identity preferred, reviewed fallback otherwise | `players`, `player_external_identities`, `player_seasons`, `player_identity_resolutions`, `data_quality_issues`, `source_snapshots` | Normalized fact imports, identity queue, player comparisons |
| Boxscore source evidence | Public boxscore fetched with timeout/retry policy; content hashed and parsed | `source_snapshots`, compatibility `games.raw_html`, `ingest_runs` | Parser replay, provenance, normalized imports; raw payload is not a downstream API contract |
| Canonical game and legacy display data | URL/source identity resolved idempotently; metadata, source-shaped tables, and status transitions refreshed | `games`, `team_stats`, `player_stat_groups`, `scoring_plays`, `event_status_history` | Game list/detail UI and compatibility paths |
| Normalized game facts | Player/team rows map through canonical identities and governed metric definitions | `player_game_stats`, `team_game_stats`, `stat_definitions`, source-snapshot links | Record Book, semantic catalog, comparisons, achievements |
| Cumulative season facts | Sidearm cumulative tables parsed into atomic totals with player-bio identity | `player_season_stats`, `team_season_stats`, `player_seasons`, `source_snapshots`, `ingest_runs` | Historical seed and independent reconciliation source |
| Historical/range backfill | Roster, schedule, final boxscores, and cumulative statistics processed per season; range parent run checkpoints each season | All applicable identity/fact/evidence tables plus `ingest_runs` | Operator backfill UI; resumable bounded execution; no implied all-time completeness |
| Reconciliation and coverage | Complete game-grain sums compared with season source totals; missing coverage is distinguished from metric mismatch | `coverage_windows`, `data_quality_issues` | Coverage reports, identity queue, Record Book qualification, achievement evidence |
| Shared workspace definitions | Validated Season-desk or Player-comparison route/filter configuration plus prototype username | `workspace_views` | Authenticated workspace; opening reruns governed queries, and any authenticated prototype user can delete any view |
| Record Book and semantic results | SQLAlchemy-authored, cataloged queries over normalized facts and metric semantics | Computed, not persisted as result tables | Record Book, exploratory workspace, Ask-a-Question, player comparisons, CSV export; responses carry evidence/coverage as supported by their contract |
| Pregame brief | Historical opponent/game facts assembled from the warehouse | Computed, not persisted | Internal pregame workflow |
| Notability policy | Seeded, reviewed, versioned editorial configuration | `notability_policies`, `notability_policy_metrics` | Deterministic achievement scoring; does not alter metric semantics |
| Achievement Suggestions | Final eligible facts compared with warehouse history; optional model ranks/phrases only supplied facts | `achievement_suggestions` with policy, source, coverage, AI, and current-verdict provenance | Authenticated SID review; feedback calibration is reproducible from stored context per ADR-009 |
| Generated coverage | Stored game data sent to the configured model and transformed into editorial drafts | `generated_content` | Internal editorial review; no implemented website publication record |

## Evidence and deletion behavior

- Normalized fact tables reference the source snapshot used to create the fact.
- Coverage is modeled by sport/program, metric or grain, source, season bounds,
  completeness, and known limitations; it is not automatically “all-time.”
- Deleting a parent can cascade or null related evidence according to ORM/migration
  constraints. Destructive production cleanup therefore requires an archive and
  retention review, not ad hoc row deletion.
- CSV files and other downloaded exports leave application control. The operator
  becomes responsible for appropriate storage and disposal.

## Known lineage gaps

- No immutable operator-action or verdict-event audit table exists.
- Raw snapshot and ingest-run retention are not automatically enforced.
- No scheduled worker/job definition is persisted; current synchronization and
  backfill are operator-invoked.
- No website syndication, CMS publication, or delivery-receipt path is implemented.
- The prototype session records a shared username rather than an institutional
  user identity.

Update this page with any change to a source, transformation, persisted entity,
computed consumer, export boundary, or deletion/retention behavior.
