# Data Lineage

This page records how important data moves through Vandals Stats Pipeline.

## Current Flow Summary

The current application handles a mostly one-way flow:

`Sidearm source page -> scraper/parser -> PostgreSQL -> internal API/UI -> future athletics website syndication`

The core release scope is public athletics event data plus internal operational
metadata and editorial drafts.

## Current Data Flows

| Data Set | Source | Processing | Storage | Consumers | Export / Retention Notes |
|---|---|---|---|---|---|
| Sidearm boxscore HTML snapshot | Public Sidearm boxscore page fetched by `sidearm_scraper.fetch_boxscore` | HTML fetched, stored as raw source, parsed into normalized event data | `games.raw_html` | parser debugging, replay analysis, future regression tooling | Not exported directly; retain with the parent game record until raw-snapshot retention automation is added |
| Game metadata and scores | Parsed from the source title, URL, and score regions | normalized into the `Game` record | `games` | backend API, internal frontend, future athletics website consumers | Core athletics record; retained as part of the event history |
| Team statistics | Parsed from Sidearm team-stat tables | normalized row-by-row with preserved source order | `team_stats` | backend API, internal frontend, future website game-detail views | Retained with the parent game record |
| Player stat groups | Parsed from category-specific Sidearm player stat tables | stored as structured JSON column-and-row groups | `player_stat_groups` | backend API, internal frontend, future website contracts after reshaping | Retained with the parent game record; not intended to be exposed downstream without contract shaping |
| Scoring timeline | Parsed from the Sidearm scoring summary table | normalized into scoring-play records with score progression | `scoring_plays` | backend API, internal frontend, future website timelines | Retained with the parent game record |
| AI-generated coverage drafts | Derived from normalized game data via `content_generator` | model prompt and response transformed into recap, spotlight, and social text | `generated_content` | athletics communications workflows, internal reviewers | Internal until publication decision; retained with the parent game unless a later editorial retention policy supersedes it |
| Website-ready event payloads | Derived from normalized game data and publish-state logic | not yet implemented; planned as versioned syndication API/feed responses | not currently persisted as a dedicated table | athletics website and CMS consumers | Export path planned under Release 1 and Release 2 website syndication work |
| Operational ingest metadata | Current `ingested_at` timestamp plus planned ingest job and audit records | used for freshness, retries, monitoring, and audit | `games.ingested_at`; future operational tables | platform maintainers, athletics operations | Internal operational data; retention policy to be implemented with monitoring and audit work |
| Shared workspace views | Named route and filter configuration submitted from the authenticated workspace UI | Pydantic validates the exact supported Season desk or Player comparison parameter set; the API records the prototype-session username | `workspace_views` | authenticated workspace UI users | Stores no result facts or source evidence; opening a view reruns the current governed query; any authenticated user can delete a shared view under the current shared-credential model |

## Governance Notes

- No student-record, health, or payment-card data is expected in the core event
  pipeline scope.
- The authoritative external integration is currently Sidearm source content.
- When publish-state, audit, or live-ingest tables are added, this page should
  be updated in the same change set as the schema change.
- Browser-local saved views remain outside server lineage in localStorage and
  are limited to route/filter definitions in the current browser.
