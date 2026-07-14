# Reboot Implementation Plan — Release 1

This plan turns the reconstituted product vision (see [`CONTEXT.md`](https://github.com/ui-insight/sidearm-pipeline/blob/main/CONTEXT.md),
[ADR-005](../adr/005-semantic-layer-for-nlq.md), [ADR-006](../adr/006-release1-internal-sid-first.md))
into a phased build. Release 1 is **women's basketball only**, delivered as an
**internal tool for the Sports Information Director (SID)** — no public website
(deferred to Release 2 per ADR-006).

It supersedes the sequencing in [Core Functionality Roadmap](core-functionality-roadmap.md)
and [Epic Drafts](epic-drafts.md), which remain valid for the website-delivery work
that returns in Release 2.

## The critical-path insight

Everything valuable depends on one keystone: a **normalized `Player` + stat-line model
with working identity resolution**. Records, achievements, leaderboards, and NLQ cannot
exist until a stat line reliably attaches to a *canonical person*. So the plan
front-loads the data model and identity, then layers capabilities on top. The AI is the
*last* thing built, not the first — the inverse of the intern approach, which built AI
features on a data model (opaque per-game JSON blobs, no `Player` entity) that could not
support them.

## Salvage boundary

What the intern branches (`feature/phase3-scheduled-ingestion`,
`feature/phase4-validation-publish`) contribute to the reboot:

| Disposition | Components |
| --- | --- |
| **Keep / adapt** | Canonical event model (`Game`, `event_sources`, `source_snapshots`, `status_history`); boxscore parser (`sidearm_scraper`); schedule discovery + `source_registry`; idempotent `ingest.py`; `IngestRun` history; Phase 3 `scheduler.py`; Phase 4 `validation.py` + publish workflow + migration `0005`; frontend patterns — `IngestRunsPage`, `OperatorPage` (validate/publish), and the `CoverageReviewPanel` **verdict** pattern (repurposed for achievements) |
| **Rebuild** | Player-stat persistence: `PlayerStatGroup` JSON blobs → normalized stat lines (the core reason for the reboot) |
| **Build new** | `Player` / identity resolution, roster + bio scraper, cumulative-stats parser, Record Book / aggregates, achievement detection + notability, achievement-review UI, NLQ semantic layer |
| **Shelve on branch** | `backend/app/agents/*`, `mcp_servers/*`, `agent_runs` API, raw-SQL `nl_query`, migration `0004`, the as-built eval harness |

## Data model

A sport-agnostic normalized core, so adding sports later is *data*, not schema churn.
All models use the SQLAlchemy ORM (CLAUDE.md rule 6 — no raw SQL).

- **`Player`** — canonical identity, keyed on the stable Sidearm bio id
  (`/roster/kyra-gardner/8435` → `8435`). The identity anchor.
- **`PlayerSeason`** — roster membership per season (jersey, class, position); supports
  fallback matching when a bio link is missing.
- **`PlayerGameStat`** — one row per `(game, player, stat_key, value)`. Long/normalized
  form: leaderboards and records become `WHERE stat_key = 'points'` plus aggregate/window
  queries.
- **`StatDefinition`** — per-sport `(stat_key, display_name, aggregable, higher_is_better,
  importance_weight)`. Does double duty: it types the stats **and** encodes the
  SID-defined notability rubric (`importance_weight`).
- **`PlayerSeasonStat`** — season totals parsed from Cumulative Season Statistics pages;
  used for the reconciliation cross-check and as fallback aggregates where game-grain data
  is unavailable.
- **`AchievementSuggestion`** — `(game, player, stat_key, kind, value, notability_score,
  phrasing, verdict …)`; reuses the intern verdict pattern.

### Key decision — stat storage shape

Normalized long-form `PlayerGameStat` (**recommended** — sport-extensible, ORM-friendly,
records are trivial queries) vs. per-sport typed tables (`wbb_game_stat` with real
columns — more type-safe, but a table + migration per sport). Recommendation:
long-form + `StatDefinition`, so "add a sport" means inserting rows, not authoring new
tables. This is hard to reverse and will get its own ADR once confirmed.

## Phased sequence

Each phase ships something testable. ⭐ marks the keystone phases.

| Phase | Goal | Depends on | Exit criteria |
| --- | --- | --- | --- |
| **0 — Reboot baseline** | Salvaged Phase 3/4 backend on a fresh integration branch off `main`, agentic layer excluded | — | Ingestion + validation/publish + ingest-runs UI green; zero agent code |
| **1 — Normalized model** ⭐ | `Player`, `PlayerSeason`, `PlayerGameStat`, `StatDefinition`; WBB stat defs + SID weights; Alembic migration | 0 | Can persist a normalized stat line; tests pass |
| **2 — Identity resolution** ⭐ | Bio-id anchor + roster/bio scraper + resolver with fallback + unresolved-player review queue | 1 | Every boxscore row resolves to a `Player` or lands in the queue |
| **3 — Boxscore → normalized + WBB backfill** | Redirect parser persistence; backfill ~300 WBB boxscores (2017-18 → present) | 2 | WBB game-grain stats in warehouse; forward ingest writes normalized lines |
| **4 — Cumulative backfill + reconciliation** | Cumulative parser → `PlayerSeasonStat`; sum-to-season integrity check | 2 | ~10 seasons of season aggregates; reconciliation clean or triaged |
| **5 — Record Book & aggregates** | Career/season totals + leaderboards (SQLAlchemy) | 3, 4 | Answers "career points leaders," "season high," etc. |
| **6 — Achievement detection + notability** | Deterministic detectors; notability score from `StatDefinition` × record-scope tier | 5 | Finalizing a game yields ranked candidate achievements (no AI yet) |
| **7 — AI ranking/phrasing + SID review UI** | LLM ranks borderline cases + phrases; achievement queue with verdicts; verdict tuning | 6 | SID reviews a game's achievements end-to-end |
| **8 — NLQ semantic layer** | Curated parameterized SQLAlchemy queries + NL→query mapping + phrasing + UI | 5 | SID asks the seed question set and gets correct, sourced answers |

**Release 1** = Phases 0–8 for women's basketball. **Release 2** = website syndication
once the web team picks an integration mode. **Later** = sport fan-out (mostly new
`StatDefinition` rows + parser coverage), recap/editorial (roadmap Release 3), and
auth + ops hardening (roadmap Phase 7).

## AI boundary (recap)

Per the deterministic-facts principle: the warehouse computes every fact and number in
SQL; the AI only ranks borderline notability and phrases verified facts, and answers NLQ
via the curated semantic layer (ADR-005) — never authoring SQL or generating numbers.

## Open decisions

1. **Stat storage shape** — normalized long-form (recommended) vs. per-sport typed tables.
   Confirm before Phase 1; write an ADR on the choice.
2. **Aggregates** — query-time first, materialize only if performance requires it
   (recommended) vs. materialized rollups up front.
3. **Game-grain backfill depth** — accept that pre-2017-18 "HTML version" markup may not
   parse, falling back to cumulative season aggregates for those seasons.
4. **Auth** — stays deferred to roadmap Phase 7 (interns shipped none); acceptable for an
   internal-only Release 1, or gate write endpoints sooner.
