# Source Registry

The source registry defines the authoritative Sidearm source patterns that the
ingestion layer is allowed to use. It is the implementation starting point for
[#10](https://github.com/ui-insight/sidearm-pipeline/issues/10) and
[#12](https://github.com/ui-insight/sidearm-pipeline/issues/12).

The bundled registry lives at
`backend/app/source_registry.json` and is loaded through
`app.services.source_registry`.

## Release 1 Scope

The first registry version supports final boxscore ingestion for these
Govandals sport slugs:

| Sport slug | Sport | Gender | Event shape | Schedule source |
| --- | --- | --- | --- | --- |
| `football` | Football | unset | `team_contest` | `/sports/football/schedule` |
| `mens-basketball` | Basketball | men | `team_contest` | `/sports/mens-basketball/schedule` |
| `womens-basketball` | Basketball | women | `team_contest` | `/sports/womens-basketball/schedule` |
| `womens-soccer` | Soccer | women | `team_contest` | `/sports/womens-soccer/schedule` |
| `womens-volleyball` | Volleyball | women | `team_contest` | `/sports/womens-volleyball/schedule` |

These entries are intentionally narrow. Tennis, golf, cross country, track and
field, and swimming and diving remain inventory work until representative
fixtures show how much result normalization they need.

## Registry Fields

Each sport entry includes:

- `sport_slug`: Sidearm URL slug used by Govandals
- `sport_name` and `gender`: normalized sport labels
- `release_scope`: release inclusion marker, currently `release_1`
- `event_shape`: canonical event shape from the athletic event model
- `parser_strategy`: parser family that should handle the source
- `source_patterns`: schedule, boxscore, roster, and cumulative-statistics URL
  templates when supported
- `supported_source_types`: source kinds expected for the sport
- `polling_policy`: final-only and future near-live cadence settings
- `notes`: sport-specific caveats for parser and display work

## Loader Contract

`load_source_registry(path)` validates any registry file with Pydantic.
`get_source_registry()` loads the bundled registry once per process.

Use `registry.require_sport(sport_slug)` when ingestion must fail clearly for an
unsupported sport. Use `registry.get_sport(sport_slug)` when discovery logic can
skip unsupported sports.

## Schedule Discovery Preview

The backend exposes a read-only preview endpoint:

```text
GET /api/v1/sources/{sport_slug}/schedule
```

The endpoint fetches the configured Sidearm schedule page, parses rendered
schedule rows, and returns discovered events without writing to the database.
It currently extracts Sidearm game id, opponent, home/away/neutral marker,
date/time text, result status, scores, location, venue, conference marker, and
known source URLs such as boxscore, recap, live stats, and gamefile links.

Pass `?season=YYYY` to preview a historical Sidearm schedule URL such as
`/sports/football/schedule/2025`. This is useful for finding completed events
that already expose final boxscore links.

## Women's Basketball Cumulative Statistics

The women's basketball registry entry also exposes the public cumulative-season
page as a characterized fallback source:

```text
GET  /api/v1/sources/womens-basketball/season-stats?season=2025-26
POST /api/v1/sources/womens-basketball/season-stats/import?season=2025-26
```

The preview parses the overall player table, preserving Sidearm player-bio ids,
source field names, and atomic season totals. The import writes idempotent
`PlayerSeasonStat` facts, retains a raw snapshot, compares complete game-grain
coverage with the source totals, and records Coverage Windows and reviewable
data-quality issues. Missing game coverage is reported before metric mismatches
so an incomplete backfill does not create false reconciliation failures.

### Historical season backfill

`POST /api/v1/sources/womens-basketball/seasons/{season}/backfill` runs one
bounded season at a time. It reuses the idempotent roster, schedule, and final
boxscore synchronizer with no correction lookback, then imports cumulative
season statistics and performs sum-to-season reconciliation.

The response includes an explicit coverage report for final games, missing
boxscore links, failed boxscore ingests, unresolved identities, and other open
quality issues. Each run upserts a game-grain `CoverageWindow`; missing links and
parser failures remain reviewable `DataQualityIssue` records until a successful
rerun resolves them. Public GoVandals HTML remains a documented fallback rather
than a permanent authoritative-source assumption.

This public GoVandals HTML is a publication-surface fallback while Athletics and
Sidearm confirm the supported authoritative file, feed, or API. It must not be
represented as an all-time or permanent source contract.

## Next Uses

The next ingestion slice should use the registry to:

- persist discovered schedule events as canonical event records
- associate schedule, boxscore, recap, live-stat, and gamefile URLs in
  `event_sources`
- enqueue final boxscore ingestion for completed events with boxscore links
- record source type and polling expectations in future ingest job records
