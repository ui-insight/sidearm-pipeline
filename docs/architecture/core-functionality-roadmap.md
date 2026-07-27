# Core Functionality Roadmap

!!! note "Legacy website-delivery roadmap"
    The July 2026 [Reboot Implementation Plan](reboot-implementation-plan.md) and
    ADR-006 supersede this document's sequencing and Release 1 definition. Keep
    this page as background for later website syndication work; do not use its
    release labels as current commitments.

This roadmap defines the core product path for Vandals Stats Pipeline: a reliable
integration that pulls Sidearm event data, stores it in a normalized application
database, and publishes website-ready data to the athletics web experience.

## Goal

Build a trusted data pipeline that:

1. ingests Sidearm sporting event data as games progress and when games finalize
2. normalizes that data into a durable PostgreSQL schema
3. exposes website-ready APIs and feeds for the athletics site
4. supports operational review, reprocessing, and publish confidence

## Implementation Status

Historical snapshot: April 24, 2026. For current implementation status, use the
[Reboot Implementation Plan](reboot-implementation-plan.md),
[As-Built Data Model](data-model.md), and API documentation.

Implemented:

- canonical event metadata on the existing `games` table, including stable
  `canonical_uid`, source identity, lifecycle status, publish status, sport
  shape, venue/location placeholders, and freshness timestamps
- raw source lineage through `event_sources`, `source_snapshots`, parser version
  metadata, content hashes, and event status history
- idempotent boxscore ingestion that refreshes the same canonical event instead
  of deleting and recreating records
- Alembic baseline migration and regression tests for repeated ingest identity
  preservation
- Release 1 Sidearm source registry for football, men's basketball, women's
  basketball, women's soccer, and women's volleyball
- schedule discovery preview endpoint at
  `GET /api/v1/sources/{sport_slug}/schedule`
- reusable schedule and boxscore parser fixtures for every Release 1 sport,
  including academic-year basketball seasons and volleyball set scoring
- durable ingest run history for manual boxscore ingestion, exposed at
  `GET /api/v1/ingest-runs` with status, timing, source context, response
  status, retryability, and error detail
- configurable Sidearm fetch timeout and retry policy with exponential backoff
  for transient network errors and retryable HTTP responses

Issue status:

| Issue | Status | Notes |
| --- | --- | --- |
| [#10](https://github.com/ui-insight/sidearm-pipeline/issues/10) | Mostly complete | Release 1 sport inventory and source patterns are in the registry; leave open until ownership notes or additional source quirks are accepted. |
| [#11](https://github.com/ui-insight/sidearm-pipeline/issues/11) | Partial | Source types are classified in the registry, but live-versus-final behavior still needs sport-by-sport documentation. |
| [#12](https://github.com/ui-insight/sidearm-pipeline/issues/12) | Complete | Registry JSON, typed loader, tests, docs, and ingestion consumption are implemented. |
| [#13](https://github.com/ui-insight/sidearm-pipeline/issues/13) | Complete | Representative schedule and boxscore fixtures cover every Release 1 sport. |
| [#14](https://github.com/ui-insight/sidearm-pipeline/issues/14) | Complete | Canonical event schema and status vocabulary are documented and implemented. |
| [#15](https://github.com/ui-insight/sidearm-pipeline/issues/15) | Complete | Raw source snapshots, parser version, content hash, and fetch metadata are persisted. |
| [#16](https://github.com/ui-insight/sidearm-pipeline/issues/16) | Complete | Repeated boxscore ingestion preserves event identity and refreshes related stats. |
| [#17](https://github.com/ui-insight/sidearm-pipeline/issues/17) | Complete | Migration and repeated-ingest regression tests are in place. |
| [#19](https://github.com/ui-insight/sidearm-pipeline/issues/19) | Complete | Manual boxscore ingests now create durable `ingest_runs` records and expose recent history through the API. |
| [#20](https://github.com/ui-insight/sidearm-pipeline/issues/20) | Complete | Sidearm fetches now use configurable timeout, retry attempts, exponential backoff, and persisted attempt metadata. |

Recommended GitHub action: close #12, #13, #14, #15, #16, and #17. Keep #10
and #11 open as active follow-up work. Close #20 once this branch is merged.

## Current Baseline

The current scaffold provides:

- manual ingestion of a Sidearm boxscore URL
- parsing of game metadata, team stats, player stat groups, and scoring plays
- persistence in PostgreSQL through canonical event, source lineage, stats, and
  generated-content tables
- internal React views for listing ingested games and inspecting a single game
- registry-driven schedule discovery preview for Release 1 sports
- persisted ingest attempt history for manual boxscore ingests
- optional AI coverage generation from stored game data

That means the project proves the basic scrape-store-display loop and has the
first canonical event foundation. It does not yet provide persisted schedule
discovery, live refresh orchestration, website syndication contracts, or
publishing operations.

## Target State

The target production workflow is:

```text
Sidearm sources -> ingestion workers -> normalization + validation -> PostgreSQL
-> publishing API/feed layer -> athletics website components/pages
```

In the target state, athletics web pages should consume this project as the
system of record for game data presentation rather than scraping Sidearm
directly inside the website.

## Roadmap Phases

### Phase 1: Source Integration Foundation

Establish the system boundary and source inventory.

Deliverables:

- define the authoritative Sidearm inputs by sport
- document whether each sport depends on boxscore pages only or on additional
  live-stat views, schedule pages, or JSON endpoints
- create a source registry with per-sport URL patterns, polling rules, and
  parsing strategy
- add configuration for environment-specific source hosts and rate limits

Success criteria:

- the team can enumerate how football, basketball, volleyball, and other target
  sports will be sourced
- each source has an owner, polling rule, and fallback behavior

### Phase 2: Canonical Event Data Model

Move from one-off scraped records to durable event identity and publishable state.

Deliverables:

- introduce stable event identifiers beyond raw source URLs
- add event lifecycle fields such as `scheduled`, `live`, `final`, `canceled`,
  and `postponed`
- normalize source metadata for opponent, venue, start time, season, sport, and
  publish timestamps
- preserve raw source snapshots and parser version metadata for replay and audit
- define idempotent upsert rules so repeated ingestion updates the same event
  record instead of replacing it blindly

Success criteria:

- a single game can be refreshed many times without losing identity
- historical raw payloads can be replayed if parsing logic changes
- the schema supports both in-progress and final games

### Phase 3: Live Ingestion and Refresh Orchestration

Add the machinery that turns manual ingestion into an operational service.

Deliverables:

- background jobs or workers for scheduled ingestion
- polling cadence rules for pregame, live game, and postgame windows
- retry, backoff, timeout, and dead-letter handling for failed fetches
- ingest run logs with status, duration, and source response metadata
- manual re-run controls for operations staff

Success criteria:

- games can auto-refresh during a live event without manual paste-in workflows
- failures are visible and recoverable
- final game data settles automatically after the event ends

### Phase 4: Validation and Publishing Readiness

Ensure data is trustworthy before it reaches the athletics website.

Deliverables:

- validation rules for required fields by sport and event status
- conflict detection for incomplete or inconsistent score and stat updates
- publish state model such as `draft`, `validated`, `published`, and `errored`
- QA views that compare raw source data to normalized output
- audit trail for who reprocessed or approved a publish step

Success criteria:

- operators can determine whether a game is safe to publish
- the system can block invalid or partial data from flowing downstream

### Phase 5: Website Syndication API

Create the stable contract that the athletics website will consume.

Deliverables:

- versioned API endpoints or JSON feeds for scoreboard, game summary, and game
  detail views
- website-ready response shapes that avoid requiring the website to understand
  raw Sidearm structures
- cache behavior and freshness metadata for downstream consumers
- publish hooks or pull-based fetch strategy for the athletics site
- clear contract documentation for frontend and CMS consumers

Success criteria:

- the athletics website can render live or final game data directly from this
  service
- the website integration does not need to scrape Sidearm pages itself
- API contracts remain stable even if Sidearm parsing internals change

### Phase 6: Website Display Components

Turn the syndication layer into the actual audience-facing experience.

Deliverables:

- reusable website components or widgets for scoreboard cards, game detail
  views, team stats, player leaders, and scoring summary
- responsive mobile-first rendering for quick in-game checks
- graceful loading, stale-data, and unavailable-data states
- sport-specific presentation adjustments where needed
- archive and recent-games views for completed contests

Success criteria:

- athletics web editors have a reliable way to embed or surface current game
  data
- fans can view core game information without leaving the athletics site

### Phase 7: Operations, Security, and Reliability

Harden the platform for real production use.

Deliverables:

- authentication and role-based access for operational controls
- monitoring, alerting, and dashboarding for ingest freshness and failures
- backup and restore procedures for PostgreSQL
- retention policy for raw source snapshots and generated website payloads
- rate limiting and network controls for Sidearm fetch traffic
- incident runbooks for source markup changes or ingest outages

Success criteria:

- the service can be operated as a dependable production integration
- the team can detect source breakages quickly and recover without guesswork

## Recommended Release Slices

### Release 1: Final Boxscores to Website

Focus on completed games only.

Scope:

- final boxscore ingestion
- canonical event model
- publish validation
- website summary and game-detail feeds
- basic athletics-site rendering

This is the best first production milestone because it delivers visible value
with the lowest live-ops risk.

### Release 2: Near-Live Score Updates

Add live refresh and freshness controls.

Scope:

- live polling
- event status transitions
- freshness timestamps
- website scoreboard updates
- operator retry and override tools

### Release 3: Expanded Stats and Editorial Layer

Broaden the experience once the pipeline is trusted.

Scope:

- richer player leader modules
- historical archives
- automated recap generation and review workflow
- newsletter, homepage, or story modules driven by normalized event data

AI-generated coverage belongs here as an enhancement, not on the critical path
for the core data integration.

## Decisions To Make Early

- Which sports are in scope for the first production release
- Whether the athletics website will pull from APIs, receive pushed payloads, or
  embed widgets
- Whether Sidearm exposes reliable machine-readable endpoints for live data or
  whether HTML polling is the primary strategy
- What publish SLA is expected during live games
- Who owns validation and override decisions when source data is incomplete

## Definition of Core Platform Done

The core platform should be considered complete when:

- a target sport can be ingested automatically from Sidearm from pregame through
  final
- the normalized event record is durable, replayable, and auditable
- the athletics website can render the event from this system through a stable
  contract
- operators can monitor freshness, diagnose failures, and re-run publication
- the integration no longer depends on manual copy-and-paste workflows
