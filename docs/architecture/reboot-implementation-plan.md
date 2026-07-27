# Reboot Implementation Plan — Athletics Data Warehouse

**Last updated:** July 15, 2026

This plan turns the reconstituted product vision (see
[`CONTEXT.md`](https://github.com/ui-insight/sidearm-pipeline/blob/main/CONTEXT.md),
[ADR-005](../adr/005-semantic-layer-for-nlq.md), and
[ADR-006](../adr/006-release1-internal-sid-first.md)) into an executable build.

Release 1 is a **women's basketball vertical slice** delivered as an internal
tool for the **Sports Information Director (SID)**. It proves that the system can
acquire trustworthy data, build a usable Record Book, surface Notable
Achievements, and support visual exploration. Public website delivery and
all-sport coverage follow only after that slice is trusted.

This plan supersedes the sequencing in
[Core Functionality Roadmap](core-functionality-roadmap.md) and
[Epic Drafts](epic-drafts.md). Those documents remain useful background for the
website-delivery work that returns after the internal warehouse pilot.

## North star and Release 1 boundary

The north star is an **Athletic Data Warehouse** and **Exploratory Workspace**
covering every University of Idaho sport. Athletics staff should be able to:

- trust that games and results arrive without manual copy-and-paste
- compare players, teams, opponents, seasons, venues, and competition contexts
- visualize trends, leaders, streaks, and notable performances
- find accurate story ideas with the underlying evidence attached
- ask supported natural-language questions without giving an LLM authority to
  invent facts or write arbitrary SQL

Release 1 proves those jobs for women's basketball. It is not a promise of
all-sport or all-time coverage. Until a Coverage Window proves otherwise, every
historical claim must say "since `<season>`" or "within warehouse history," not
"all-time."

## Non-negotiable principles

1. **SID first.** The SID is the primary Release 1 user and participates in
   question discovery, metric definitions, Notability policy, and pilot review.
2. **Most structured source first.** Prefer institutional stat files or a
   supported Sidearm export/API over scraping presentation HTML. HTML remains a
   fallback, not an assumed permanent contract.
3. **Coverage is part of every fact.** Store and display the seasons, grains,
   and known gaps that bound a comparison.
4. **Model broadly, implement narrowly.** The core represents different event
   shapes, while Release 1 implements only women's basketball.
5. **Deterministic facts.** The warehouse computes every number. AI may map a
   question to a vetted query, rank borderline Notability, and phrase verified
   facts.
6. **Human-visible uncertainty.** Ambiguous identities, source conflicts, and
   reconciliation failures enter review queues; the system never guesses
   silently.
7. **Provenance by default.** Every normalized fact can be traced to its source,
   parser version, fetch time, and applicable Coverage Window.
8. **Safe before shared.** Authentication, authorization, recovery, and basic
   monitoring are Release 1 pilot gates, not post-pilot hardening.

## Current implementation status

The repository now implements substantial WBB vertical slices described across
Phases 1–8:

- canonical programs, teams, players, external identities, roster membership,
  metric definitions, and normalized game/season facts
- schedule, roster, boxscore, cumulative-season, one-season backfill, and
  resumable range-backfill paths with source snapshots and ingest-run evidence
- identity-resolution and data-quality queues plus explicit Coverage Windows and
  sum-to-season reconciliation
- Record Book, semantic-query catalog, exploratory workspace, player comparison,
  shared workspace views, CSV export, and historical pregame briefs
- deterministic Achievement Suggestions, optional validated AI ranking/phrasing,
  and an authenticated SID verdict queue

The legacy source-shaped `PlayerStatGroup` tables remain for game-detail
compatibility, but governed Record Book and semantic queries use normalized facts.

Release 1 is still not production-complete. Phase -1 source-contract/SID decisions
remain external governance work, and Phase 9 still requires individual identity,
RBAC, immutable consequential-action auditing, backup/restore evidence, monitoring,
and an operational scheduling/ownership decision. Public website syndication and
generalized non-team-contest result models remain later work.

## Phase -1 — Source contract and product discovery

Do this before creating the warehouse migration. It prevents the schema and
parser from being optimized around an avoidable HTML-scraping constraint.

### Source-contract investigation

Ask Athletics and Sidearm:

- Does Idaho's contract include a supported machine-to-machine interface, such
  as an API, XML/JSON feed, SFTP/File Distributor location, Nexus integration,
  webhook, or scheduled export?
- If authenticated access is required, does Sidearm provide an OAuth client,
  API token, or dedicated least-privileged service account for this purpose?
  Document credential ownership, scopes, rotation, rate limits, and whether a
  sandbox is available.
- Which raw stat files are uploaded after a game, and can this project receive
  the same files?
- Which scoring/statistics system originally creates each sport's data (for
  example, NCAA LiveStats/Genius, StatCrew, or DakStats), and is that original
  file or feed available directly to Idaho?
- Which sources are authoritative for corrections, season totals, career totals,
  rosters, and historical records?
- What automated-access, retention, redistribution, and rate-limit terms apply?
- How are retroactive corrections communicated?
- Which sports and seasons have structured data, HTML only, PDFs, or no digital
  history?

Treat these as three separate provenance layers:

1. the **originating statistics system** that records or exports the facts
2. the **Sidearm client integration** that receives, manages, or transforms them
3. the **GoVandals publication surface** that presents them as public HTML

An authenticated Sidearm staff portal proves that Idaho can administer content;
it does not by itself establish a supported automated-ingestion contract. Do not
automate a person's CMS login or MFA session. Portal automation is a last-resort
adapter only if Sidearm confirms in writing that no supported machine interface
exists, permits the automation, and provisions a dedicated non-human account.
Until the access decision is complete, retain public GoVandals HTML ingestion
only as a discovery, comparison, and fallback path—not as an assumed
authoritative source.

Record the result in a source-coverage matrix with one row per
`sport × season × grain`:

| Field | Meaning |
| --- | --- |
| Sport and season | Program and season covered |
| Grain | game, season, career, match, heat, round, meet, or tournament |
| Originating system | System or workflow that first records/exports the facts |
| Sidearm role | Receives, transforms, stores, or only publishes the data |
| Publication surface | GoVandals page or other human-facing destination |
| Authoritative source | institutional file, Sidearm feed/API, HTML, PDF, or manual record |
| Acquisition and authentication | API/feed/file protocol, auth method, service identity, scopes, and credential owner |
| Identity keys | event, player, team, and opponent identifiers available |
| Coverage status | complete, partial, unknown, or unavailable |
| Known gaps | missing games, missing fields, parser limitations, or corrections |
| Access policy | cadence, rate limit, retention, and owner |

### SID discovery

Document at least:

- 15–25 recurring questions the SID wants answered
- 10 representative story types, such as career highs, streaks, rivalry history,
  venue splits, comebacks, threshold crossings, and program leaders
- the dimensions used in those questions: season, conference, opponent,
  home/away/neutral, player, venue, result, starter status, and postseason
- the evidence the SID needs before quoting an answer
- the first sport-specific Notability rubric

### Exit criteria

- Sidearm or Idaho's contract owner has confirmed the supported automated-access
  options and applicable use terms in writing
- the team has chosen the Release 1 source path, authentication mechanism, and
  documented fallback without depending on a staff member's portal credentials
- provenance identifies the originating system, Sidearm's role, and the public
  publication surface rather than labeling all three simply "Sidearm"
- WBB source and historical Coverage Windows are explicit
- the seed question and story catalogs exist
- unresolved source-contract questions have owners and decision dates

## Salvage boundary

What the intern branches (`feature/phase3-scheduled-ingestion` and
`feature/phase4-validation-publish`) contribute to the reboot:

| Disposition | Components |
| --- | --- |
| **Keep / adapt** | Canonical event model (`Game`, `event_sources`, `source_snapshots`, `status_history`); schedule discovery and `source_registry`; idempotent ingest service; `IngestRun` history; validation ideas; `IngestRunsPage` and `OperatorPage` patterns; the `CoverageReviewPanel` Verdict interaction pattern |
| **Rework before use** | The in-process scheduler, hard-coded seasons, validation rules, publish workflow, and WBB player-stat parser fixtures |
| **Rebuild** | `PlayerStatGroup` JSON persistence into normalized player and team facts with identity resolution |
| **Build new** | Source adapters; program/team/opponent dimensions; Coverage Windows; Record Book; data-quality queues; Exploratory Workspace; deterministic achievement detection; Notability policy; SID review; semantic layer; NLQ |
| **Shelve on branch** | `backend/app/agents/*`, `mcp_servers/*`, `agent_runs` API, raw-SQL `nl_query`, migration `0004`, and the as-built eval harness |

## Revised warehouse model

[ADR-007](../adr/007-normalized-long-form-stat-storage.md) remains the decision
for long-form stat storage. The warehouse needs a broader core than the first
ADR listed, however. All application access uses SQLAlchemy ORM/Core; route
handlers do not use raw SQL.

### Dimensions and identity

- **`SportProgram`** — an Idaho program such as women's basketball, with sport,
  gender, and governing-season conventions.
- **`Team` / `OpponentAlias`** — canonical Idaho and opponent identities plus
  observed source labels such as "Idaho State," "Idaho St.," and "ISU."
- **`Player`** — canonical person within the warehouse.
- **`PlayerExternalIdentity`** — namespaced source identity such as
  `(source_system, institution, source_player_id)`. A bare numeric Sidearm id is
  not assumed to be globally unique.
- **`PlayerSeason`** — roster membership by program and season, including jersey,
  class, position, and source bio URL.
- **`Game` / future `AthleticEvent`** — the existing canonical event anchor.
- **`EventParticipant`** — generalized participant/result rows needed beyond
  two-team contests.

The Sidearm player-bio id is the preferred WBB identity anchor, but its stability
must be verified across multiple seasons and correction scenarios. Missing or
ambiguous matches enter an unresolved-player queue.

### Fact tables

- **`PlayerGameStat`** — one atomic player fact per game and stat definition.
- **`TeamGameStat`** — one atomic team fact per game and stat definition.
- **`PlayerSeasonStat`** — authoritative or source-provided season aggregates.
- **`TeamSeasonStat`** — authoritative or source-provided team aggregates.
- **`EventResult`** — placements, marks, rounds, heats, matches, or attempts for
  sports that are not simple two-team contests; introduced when its first sport
  cohort requires it.

Game facts are the preferred basis for single-game and derived season analysis.
Season facts provide a cheap historical seed and an independent reconciliation
source. Derived percentages and rates are recomputed from atomic components; they
are not averaged or summed directly.

### Metric definitions

`StatDefinition` must describe enough semantics to prevent invalid aggregation:

- sport/program and stable `stat_key`
- entity scope: player, team, event, or participant
- value type and unit
- aggregation method: sum, maximum, minimum, average, ratio-from-components,
  latest, or non-aggregable
- comparison direction and qualifying thresholds
- display label, format, and source-field aliases
- whether the metric is eligible for Record Book or Notability use

ADR-007 currently stores `importance_weight` on `StatDefinition`. Before Phase 1,
record a follow-on decision on whether editorial weights remain there or move to
a separate, versioned **`NotabilityPolicy`**. This plan recommends separation so
metric meaning stays stable while SID preferences evolve.

### Trust and product records

- **`CoverageWindow`** — sport, metric/grain, first and last season, completeness,
  and known limitations.
- **`DataQualityIssue`** — unresolved identity, reconciliation mismatch, source
  conflict, parser failure, or missing event.
- **`AchievementSuggestion`** — verified comparative fact, scope, Coverage
  Window, Notability score, phrasing, and state.
- **`NotabilityPolicy`** — versioned sport-specific rubric and thresholds.
- **`Verdict`** — SID approve/reject decision and reason. Verdict history informs
  an explicit policy revision; it does not silently rewrite metric semantics.

## Phased sequence

Each phase has an observable product or trust outcome. ⭐ marks keystone phases.

| Phase | Goal | Depends on | Exit criteria |
| --- | --- | --- | --- |
| **-1 — Source and SID discovery** ⭐ | Choose the WBB source contract and supported machine-access path, document Coverage Windows, and define seed questions/stories | — | Sidearm access response, three-layer source matrix, auth decision, question/story catalogs, owners, and decision dates exist |
| **0 — Reboot baseline** | Salvage only the ingestion/validation/UI patterns that fit the reboot; add full-fidelity WBB fixtures | -1 | Tests include WBB player rows and bio links; no shelved agentic/raw-SQL code; baseline checks green |
| **1 — Normalized core** ⭐ | Add dimensions, external identities, player/team game and season facts, rich `StatDefinition`, coverage, and quality models | 0 | Migration upgrades cleanly; atomic WBB facts persist; invalid metric aggregation is rejected |
| **2 — WBB source adapters and identity** ⭐ | Ingest roster/bio and chosen game/season sources; resolve players and opponents | 1 | Every source row resolves canonically or enters a visible queue; links and provenance are retained |
| **3 — Current-season WBB vertical slice** | Redirect forward ingest to normalized facts, validate, and schedule safely | 2 | Current WBB season ingests idempotently; new/changed games refresh without repeated full-history fetching |
| **4 — WBB historical backfill and reconciliation** | Backfill available game and season grains; compare additive facts and derived metrics | 3 | Coverage report exists; additive mismatches are clean or triaged; unparseable seasons are explicit |
| **5 — Record Book and semantic catalog** | Build career/season totals, leaders, splits, and vetted query functions | 4 | Seed deterministic questions return correct facts, provenance, and Coverage Windows |
| **6 — Exploratory Workspace** ⭐ | Add filters, charts, comparisons, leaders, saved views, and export over the semantic catalog | 5 | SID can answer the priority visual-analysis questions without SQL and inspect source evidence |
| **7 — Deterministic achievements** | Detect career/season highs, thresholds, streaks, top-N marks, and other verified story candidates | 5, 6 | A final game produces explainable candidates with scope and coverage; no AI is required |
| **8 — AI assistance and NLQ** | Add optional phrasing/ranking, Verdict workflow, and NLQ mapping to vetted queries | 7 | AI cannot create numbers or SQL; out-of-catalog questions fail honestly; underlying facts remain viewable |
| **9 — Staff pilot readiness** | Gate access, make ingestion operational, and prepare recovery/monitoring | 3–8 | Auth/RBAC, backups, alerts, correction workflow, runbook, and agreed freshness target are in place |

Release 1 is complete only when Phases -1 through 9 are satisfied for women's
basketball. Phases 6 and 7 may proceed in parallel once Phase 5 is stable. Phase 8
is optional for the first staff pilot if deterministic exploration and
achievements already deliver value.

## Release 1 acceptance gates

### Data integrity

- 100% of ingested WBB player rows either resolve to a canonical Player or appear
  in an actionable review queue.
- Additive core metrics reconcile to the authoritative season source, except for
  documented source corrections or explicitly accepted gaps.
- Percentages and rates are derived from atomic components.
- Duplicate games, players, aliases, and season rows are detected.
- Every result exposes source provenance and the applicable Coverage Window.

### Product usefulness

- The SID can answer the agreed seed questions through filters, charts,
  leaderboards, or the semantic query catalog.
- The SID can move from a finalized game to evidence-backed story candidates
  without manually searching historical pages.
- Exploratory views support at least season, player, opponent,
  home/away/neutral, conference, result, and date filters where the source data
  permits them.
- The pilot records time-to-answer, accepted/rejected Achievement Suggestions,
  missing question types, and data-trust failures for prioritization.

### Operations and safety

- Final WBB games ingest without a paste-in workflow.
- Failed, stale, or corrected ingests are visible and recoverable.
- Shared write actions require authenticated, authorized staff access.
- PostgreSQL backup/restore has been tested.
- Source-markup or source-feed failure has an owner and runbook.

## Sport expansion after the WBB pilot

Adding a sport is not assumed to be only `StatDefinition` data entry. Expansion
proceeds one sport at a time through cohorts based on event shape:

| Cohort | Sports | Expected reuse and new work |
| --- | --- | --- |
| **A — closest analogue** | Men's basketball | Reuse WBB facts, identity, views, and most metrics; verify independent source fixtures and definitions |
| **B — other team contests** | Volleyball, soccer, football | Reuse event/team/player core; add sport-specific set/period/scoring/stat adapters and validation |
| **C — matches and dual meets** | Tennis, swimming/diving duals | Add nested matches/events, participant results, and dual scoring |
| **D — multi-team and tournament events** | Cross country, track and field, golf, swimming invitationals/championships | Add parent/child events, rounds/heats, attempts, placements, marks, qualifiers, and PDF/result adapters |

Every sport must pass the same entry gates before implementation:

1. representative current and historical fixtures
2. authoritative-source and access decision
3. event-shape and identity mapping
4. metric definitions and aggregation rules
5. coverage and reconciliation plan
6. SID questions, visual views, and Notability rubric

Public website syndication remains a separate release after Athletics chooses API
pull, embedded widget, shared component, or another integration mode.

## AI boundary

Per the deterministic-facts principle:

- SQLAlchemy-authored warehouse queries compute every fact and number.
- AI may select a query id and typed parameters from the Semantic Layer.
- AI may rank borderline Notability and phrase already verified facts.
- AI may not author SQL, invent metrics, calculate values, expand the Coverage
  Window, or turn a partial history into an all-time claim.
- Every AI-assisted answer shows the underlying query result and provenance.

## Backlog alignment

The existing Release 1 epic and issues remain useful, but they should be updated
to match this plan before implementation:

- add Phase -1 issues for source contract, coverage matrix, SID questions, and
  story taxonomy
- make supported machine access, service-account security, and the prohibition
  on personal portal credentials explicit acceptance criteria for source work
- expand the normalized-model issue to include team facts, external identity,
  metric semantics, coverage, and quality records
- make full-fidelity WBB fixtures and player-link preservation part of the reboot
  baseline
- add an Exploratory Workspace epic between the Record Book and AI work
- add authenticated pilot readiness and operational ingestion as Release 1 gates
- treat sport cohorts and website syndication as later epics

`PlayerSeasonStat`, `TeamGameStat`, `TeamSeasonStat`, `CoverageWindow`,
`DataQualityIssue`, `AchievementSuggestion`, and the Verdict/Notability policy
must each have an explicit schema-owning issue. No consuming issue should assume
that another phase will create its table implicitly.

## Start tomorrow

### Morning — remove the highest-risk assumptions

1. Send the source-contract and machine-access questions above to the Athletics
   contract owner and the Sidearm account contact; request a written answer and
   the technical-integration contact rather than requesting a staff password.
2. Hold or schedule a 60-minute SID discovery session. Capture recurring
   questions, story types, definitions, evidence needs, and current pain points.
3. Capture full-fidelity WBB fixtures for:
   - one current boxscore with complete player tables and bio links
   - one older parseable boxscore
   - one cumulative season statistics page
   - the corresponding roster page
4. Start the WBB source-coverage matrix and mark unknowns rather than inferring
   completeness.

### Afternoon — turn discovery into the first implementation slice

5. Draft the first 15 deterministic questions and 10 story types.
6. Select the first atomic WBB metrics, including makes/attempts components for
   percentages and the rules for minutes/durations.
7. Update the Release 1 epic and child issues to reflect Phase -1, the broader
   model, the Exploratory Workspace, and the staff-pilot gate.
8. Make the first implementation PR a **full-fidelity WBB parser
   characterization**:
   - preserve player bio URLs and numeric ids
   - identify Idaho versus opponent player rows
   - parse atomic stat columns without yet committing to the final migration
   - add regression tests that expose unsupported WBB structures explicitly

Do not begin the large historical backfill or AI implementation tomorrow. The
highest-leverage first step is proving the source contract and full player-stat
shape that the warehouse must preserve.

## Decisions requiring explicit records

Before Phase 1 closes, record decisions for:

1. authoritative source order, the role of each provenance layer, permitted
   automated access, authentication method, and service-account ownership
2. external player/team identity namespaces and transfer handling
3. final metric semantics and derived-stat rules
4. whether Notability weights remain on `StatDefinition` or move to a versioned
   policy
5. accepted WBB Coverage Window and language for incomplete history
6. staff authentication/SSO and role boundaries
7. scheduler/worker ownership, concurrency control, and deployment model
8. raw-source retention location and duration
