# Epic Drafts

These drafts turn the core functionality roadmap into a set of GitHub-ready
epics. They are intentionally focused on the primary product objective:
integrating Sidearm sporting event data into a normalized database and
delivering website-ready data to the athletics web experience.

## Epic 1: Establish Sidearm Source Registry and Sport Coverage

**Target release:** Release 1

## Problem Statement

The current application can ingest a manually pasted Sidearm boxscore URL, but
it does not yet define the full set of authoritative Sidearm sources, sport-by-
sport parsing rules, or operational source coverage needed for a dependable
production integration.

## Proposed Solution

Create a formal Sidearm source integration foundation that:

- identifies the authoritative source pattern for each in-scope sport
- documents whether each sport depends on boxscore HTML, live-stat pages,
  schedule pages, or machine-readable endpoints
- defines polling, timeout, and rate-limit rules per source type
- captures representative sample fixtures for parser development and regression
- introduces a configurable source registry used by ingestion services

## Alternatives Considered

- continue with ad hoc URL-by-URL ingestion
- support only a single sport initially without a reusable source model

## Additional Context

This epic is the foundation for every later release because the team cannot
automate ingestion safely until source behavior is understood and documented.

## Acceptance Criteria

- a source inventory exists for each sport included in Release 1
- each source has a documented fetch strategy, polling rule, and fallback plan
- representative Sidearm samples are stored for parser and regression testing
- the codebase has a source registry or equivalent configuration model

## Suggested Child Issues

- inventory target sports and their Sidearm source patterns
- document live-data versus final-boxscore source behavior by sport
- add source registry configuration and schema
- capture sample payloads and regression fixtures

## Epic 2: Build Canonical Event Model and Idempotent Ingestion

**Target release:** Release 1

## Problem Statement

The current data model treats a game largely as a scrape result keyed by source
URL. That is enough for manual ingestion, but it is not enough for live refresh,
replay, auditing, or stable publication to the athletics website.

## Proposed Solution

Design and implement a canonical event model that:

- introduces a stable event identity beyond the raw Sidearm URL
- tracks event lifecycle states such as `scheduled`, `live`, `final`,
  `postponed`, and `canceled`
- stores normalized metadata for sport, season, opponent, venue, start time, and
  update timestamps
- preserves raw source snapshots and parser version metadata
- supports idempotent upsert behavior so repeated ingestion updates the same
  event record

## Alternatives Considered

- continue replacing entire records by URL on each ingest
- store only normalized tables without raw source snapshots

## Additional Context

This epic is what turns the current scraper demo into a durable event platform.

## Acceptance Criteria

- the same event can be ingested multiple times without changing identity
- the schema supports both in-progress and final games
- raw source snapshots are retained for replay and debugging
- parser version and last-ingested metadata are persisted

## Suggested Child Issues

- design canonical event schema and status model
- add raw source snapshot storage and parser metadata
- implement idempotent ingest and update rules
- add migration coverage and tests for repeated ingest behavior

## Epic 3: Automate Final Boxscore Ingestion

**Target release:** Release 1

## Problem Statement

The current workflow requires a user to paste a Sidearm URL manually. Athletics
needs final game data to move into the platform without manual copy-and-paste so
the website can be updated consistently and on time.

## Proposed Solution

Implement a production ingestion workflow for finalized games that:

- discovers or receives the target Sidearm source for completed contests
- runs ingestion automatically on a schedule or trigger
- records ingest run status, duration, and source response metadata
- retries failures with controlled backoff
- allows authorized staff to manually re-run failed ingests

## Alternatives Considered

- continue manual URL submission from the internal UI
- postpone automation until live updates are built

## Additional Context

This epic is the first operational milestone because it delivers value without
taking on the full complexity of near-live publishing.

## Acceptance Criteria

- final boxscores for Release 1 sports can be ingested automatically
- ingest failures are logged and visible
- operators can manually re-run a failed ingestion
- the system no longer depends on a paste-in workflow for final game data

## Suggested Child Issues

- implement scheduled or triggered ingest runner
- add ingest job history and status tracking
- add retry and timeout behavior for fetch failures
- add admin re-run control for a target event

## Epic 4: Implement Validation and Publish Workflow

**Target release:** Release 1

## Problem Statement

The athletics website should not publish incomplete, malformed, or conflicting
game data. Today the project stores parsed data, but it does not yet provide a
validation or publication readiness layer.

## Proposed Solution

Create a validation and publish workflow that:

- defines required fields by sport and event state
- flags inconsistent scores, missing metadata, or partial stat sets
- introduces publish states such as `draft`, `validated`, `published`, and
  `errored`
- provides operational review views or reports for questionable records
- records audit history for reprocessing and approval decisions

## Alternatives Considered

- publish every ingested event automatically without validation
- handle all validation downstream in the athletics website

## Additional Context

This epic is what makes the platform trustworthy enough to serve as the
website-facing system of record.

## Acceptance Criteria

- a publish-ready record must pass validation checks
- invalid or incomplete events are blocked from publication
- operators can review validation failures and retry publication
- publish state is queryable by downstream systems

## Suggested Child Issues

- define validation rules by sport and game status
- add publish-state fields and transitions
- build operator review and exception reporting views
- add audit logging for publish and reprocess actions

## Epic 5: Deliver Website Syndication APIs and Feed Contracts

**Target release:** Release 1

## Problem Statement

The athletics website needs a stable, website-ready contract for consuming game
data. It should not have to know Sidearm markup details or recreate parsing
logic in the website layer.

## Proposed Solution

Create versioned syndication APIs or feeds that:

- expose scoreboard, game summary, and game-detail payloads
- return website-ready field names and structures
- include freshness, publish status, and cache metadata
- support the integration pattern chosen for the athletics site
- are documented clearly for frontend or CMS consumers

## Alternatives Considered

- fetch Sidearm directly from the athletics website
- expose only internal normalized tables and ask consumers to compose them

## Additional Context

This epic is the contract boundary between this project and the athletics web
experience.

## Acceptance Criteria

- the athletics website can fetch final game data through a stable endpoint or
  feed
- payloads are documented and versioned
- downstream consumers do not need to parse Sidearm directly
- freshness and publishability are visible in the contract

## Suggested Child Issues

- define response shapes for scoreboard, summary, and detail views
- build versioned publish endpoints or feeds
- add caching and freshness headers or metadata
- document contracts for downstream site implementers

## Epic 6: Launch Athletics Website Final-Data Display Integration

**Target release:** Release 1

## Problem Statement

Even with a working syndication API, athletics still needs visible website
functionality that renders final game data in a way fans and editors can use.

## Proposed Solution

Implement the first website-facing display layer for finalized games, including:

- scoreboard or recent-games cards
- game-detail views with score, summary, team stats, and scoring summary
- responsive and accessible presentation for mobile and desktop
- graceful states for loading, stale data, and unavailable data
- an implementation path that works for the athletics site architecture, whether
  that is API pull, embedded widgets, or shared components

## Alternatives Considered

- stop at API delivery and defer all rendering work
- continue linking fans out to Sidearm pages instead of rendering on the
  athletics site

## Additional Context

This epic is where the project becomes visible to end users rather than only to
operations staff.

## Acceptance Criteria

- the athletics website can display finalized game data from this platform
- the core final-game experience works on desktop and mobile
- data-unavailable and stale-data states are handled gracefully
- the implementation does not depend on scraping Sidearm in the website layer

## Suggested Child Issues

- choose site integration mode for website rendering
- build final-game summary card or scoreboard module
- build final-game detail presentation
- implement loading, error, and stale-data UI states

## Epic 7: Add Near-Live Event Refresh and Scoreboard Updates

**Target release:** Release 2

## Problem Statement

Release 1 covers finalized data, but athletics also needs a dynamic integration
for games in progress. That requires refresh orchestration, freshness tracking,
and user-facing handling of near-live data.

## Proposed Solution

Extend the platform to support near-live event updates by:

- polling active Sidearm sources on a sport-appropriate cadence
- updating event status transitions from pregame through final
- exposing freshness timestamps and stale-data indicators
- delivering website payloads optimized for live or near-live scoreboard updates
- supporting manual override or re-run controls during active games

## Alternatives Considered

- continue publishing only final results
- attempt full real-time push architecture before the ingestion model is proven

## Additional Context

This epic should begin only after the final-data workflow is stable in
production.

## Acceptance Criteria

- in-scope live events refresh automatically within the agreed SLA
- event status transitions are reflected in stored records and published payloads
- the website can surface near-live scoreboard updates with freshness context
- operators can detect and recover from stalled refresh cycles

## Suggested Child Issues

- implement live polling cadence rules by sport
- add freshness timestamps and stale-state calculation
- extend website feeds for near-live scoreboard updates
- add operator controls for live ingest intervention

## Epic 8: Productionize Monitoring, Security, and Recovery

**Target release:** Cross-cutting, must be complete before broad production use

## Problem Statement

A data-integration platform that depends on third-party source markup will fail
in production unless it has monitoring, security controls, backups, and recovery
procedures. These capabilities are not optional once the athletics website
depends on the service.

## Proposed Solution

Harden the platform operationally by adding:

- authentication and role-based access for operational functions
- monitoring and alerting for ingest freshness, parser failure, and publish
  failure
- database backup and restore procedures
- retention rules for raw snapshots and published payloads
- runbooks for Sidearm markup changes, ingest outages, and website publishing
  failures

## Alternatives Considered

- defer production hardening until after the website launch
- rely on ad hoc troubleshooting instead of explicit runbooks and alerts

## Additional Context

This epic spans every release, but it becomes release-blocking before the
website depends on the platform operationally.

## Acceptance Criteria

- operators receive alerts for ingest and publish failures
- backup and restore procedures are documented and tested
- privileged actions require authenticated access
- incident runbooks exist for the most likely failure modes

## Suggested Child Issues

- add auth and role model for operational endpoints
- implement ingest and publish monitoring dashboards
- document and test database backup and restore
- create incident runbooks for parser and source failures
