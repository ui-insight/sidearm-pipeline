# Vandals Stats Pipeline — Domain Context

The shared language for the Vandals Stats Pipeline: a trusted system that ingests
University of Idaho athletics game data from Sidearm, holds it as a durable and
queryable record, surfaces notable achievements to comms staff, and publishes
website-ready data to the athletics web experience.

This file captures terms that are meaningful to domain experts (athletics comms
staff), not implementation details. It is maintained during grilling/design
sessions as terms are resolved.

## Language

### Users

**Sports Information Director (SID)**:
The primary user — athletics communications staff who track game results, maintain
the record book, produce coverage, and feed the athletics website. The person the
reboot is built to serve first; every other audience is downstream of their work.
_Avoid_: "comms person" (fine informally), "operator" (that is a system role, not this user)

### Sources

**Boxscore**:
Sidearm's per-game statistical summary (final score, team stats, per-player game
stats, scoring plays). Provides *game-grain* data — required for single-game records
("career high in a game," "most rebounds since 2019") and game detail. What the intern
pipeline already ingests.

**Cumulative Season Statistics**:
Sidearm's per-season, per-player totals-and-averages pages (e.g. the women's basketball
stats page), published back to ~2014-15. Provides *season-grain* pre-aggregated data —
the cheap seed for the Record Book's season and career aggregates, without reconstructing
history game-by-game. A distinct source from the Boxscore, doing a distinct job.

**Player Bio (identity anchor)**:
The Sidearm player bio page each stats-table name links to. Its URL carries a numeric
player id (e.g. `/roster/kyra-gardner/8435`) present on boxscore, roster, and
season-stats pages. This id is the **preferred Release 1 anchor** for identity
resolution — joining stat lines to one canonical **Player** across games and seasons.
Store it as a namespaced external identity (`source + institution + id`), not as a
globally unique bare number. Its stability across historical seasons must be verified;
name/jersey matching remains a reviewable fallback for missing links, transfers, and id
changes.

**Source Authority**:
The documented priority used when sources disagree. Prefer the most structured source
available to the University: institutional stat files first, then a supported Sidearm
export/API, then public HTML, with PDF/manual records as explicit historical fallbacks.
Source Authority is decided per sport, season, and grain rather than assumed globally.

### System

**Athletic Data Warehouse**:
The nature of the system — a single durable Postgres store holding player and team
histories across seasons, so any individual game can be compared against
accumulated history. Not a forward-only, per-game boxscore pipeline.
_Avoid_: "the pipeline" when you mean the whole system (ingestion is one part of the warehouse)

**Record Book**:
The accumulated career totals, season bests, and program leaderboards the warehouse
builds up over time. The reference history a single game's stats are compared against.
Every Record Book result has a **Coverage Window**; it is not automatically an all-time
institutional record book.

**Coverage Window**:
The seasons, grains, metrics, and known gaps that bound a warehouse fact. Comparative
claims must show their Coverage Window. Use "all-time" only when the underlying history
is demonstrably complete; otherwise say "since `<season>`" or "in warehouse history."

**Exploratory Workspace**:
The SID-facing surface for filtering, charting, comparing, and exporting verified
warehouse facts. It includes Record Book and leaders views, but also supports trends,
splits, streaks, opponent history, venue context, and evidence-backed story discovery.
It is curated around SID questions rather than a general-purpose chart builder.

**Notable Achievement**:
A *comparative* statement about a performance relative to the Record Book — e.g.
"career high," "most by a Vandal since 2019," "passed 1,000 career kills." Cannot be
derived from a single boxscore; requires the Record Book.
_Avoid_: "milestone," "highlight" (use as informal synonyms only)

### Editorial workflow

**Article**:
The canonical editorial work product prepared by the SID from one or more approved
Achievement Suggestions and other verified facts for a single game. An Article owns
workflow state and a history of Article Versions; it is not itself a channel-specific
post or a mutable text field.
_Avoid_: "GeneratedContent" (the legacy implementation record), "coverage bundle"

**Article Brief**:
The SID's approved editorial intent for an Article: selected Achievement Suggestions,
angle, article type, audience, and constraints. Creating an Article Brief is a human
action and freezes the first Evidence Bundle. It does not authorize publication.
_Avoid_: "prompt" (the brief is a domain record; a prompt is an implementation detail)

**Evidence Bundle**:
An immutable, hashed snapshot of every warehouse fact, Coverage Window, source
reference, and approval record that an Article writer may use. A writer may select and
phrase evidence but may not expand the bundle. Refreshing changed facts creates a new
Evidence Bundle and requires human revalidation.
_Avoid_: "context" when referring to the governed factual boundary

**Article Version**:
An append-only snapshot of Article copy produced by AI or a human editor. Each version
identifies its parent, author or model, Evidence Bundle, resolved Style Guide, validation
results, and creation time. Saving or revising creates a new version; prior versions are
never overwritten.
_Avoid_: "current draft" when the exact version matters

**Style Guide**:
A versioned editorial policy resolved from shared athletics, sport, article-type, and
channel rules. Rules may guide the writer or run as deterministic validation. A Style
Guide version used for an Article Version remains reproducible after newer rules are
activated.
_Avoid_: "system prompt" (the guide is governed editorial policy)

**Article Rendition**:
An immutable, channel-specific representation derived from a ready Article Version,
such as website, email, or social copy. A rendition may shorten or reshape approved
copy within the same Evidence Bundle, but it does not mutate the canonical Article.
_Avoid_: "Article Version" for channel-specific output

**Distribution Submission**:
The publisher's explicit, authenticated instruction to deliver selected Article
Renditions to named Channel Profiles. It creates durable outbox work and an auditable
delivery history; previewing or exporting a rendition is not a Distribution Submission.
_Avoid_: "publish" when the system has only queued delivery

### AI capabilities

**Deterministic-facts principle**:
The governing rule for every AI feature — all facts and numbers are computed by the
warehouse (SQL over the Record Book), never generated by an LLM. AI is confined to
*judging notability* and *phrasing*, always over facts the warehouse already verified.

**Achievement Suggestion**:
Proactive capability — after a game validates, the system presents the SID a ranked
list of detected Notable Achievements for review (human-in-the-loop verdict). The
warehouse detects and computes; the AI ranks newsworthiness and phrases.

**Notability**:
How the system decides which true comparative facts are worth surfacing. Primarily
*deterministic*: notability ≈ (scope of the mark: verified all-time record > career high >
season high > best-in-N-games) × (**stat-importance rubric** the SID defines per sport
— e.g. WBB points/rebounds/assists high; minutes/fouls/turnovers low or suppressed).
The AI ranks borderline cases and phrases survivors; it is a ranker/writer over a
SID-defined rubric, not the arbiter of what matters. Scope is capped by the applicable
Coverage Window.

**Verdict**:
The SID's approve/reject decision on a suggested achievement. Beyond gating what ships,
verdicts are a governed tuning signal. The current conservative feedback calibration
may down-weight later suggestions of the same metric and achievement type; each result
stores its prior counts, multiplier, and policy version so the score is reproducible.
Changes to the formula or broader editorial weights require an explicit ADR or new
Notability-policy version. Verdicts never mutate metric meaning or rewrite prior facts.
See ADR-009.
_Avoid_: "review" (the act is a verdict; "review view" is where verdicts happen)

**Ask-a-Question (NLQ)**:
Interactive capability — the SID asks a natural-language question ("how did volleyball
do in conference this year?") and gets an answer. Governed by the deterministic-facts
principle: the warehouse computes the numbers; the AI interprets the question and
phrases the answer. Implemented over the **Semantic Layer**, not free text-to-SQL.
_Avoid_: "chatbot" (it answers questions, it is not open-ended conversation)

**Semantic Layer**:
A curated set of human-authored, parameterized queries (vetted metrics and dimensions)
over the warehouse that the NLQ maps questions onto. Facts stay correct because the SQL
is written by humans; the AI selects a query and fills parameters, never authors raw SQL.
Grows over time as more question types are supported.
_Avoid_: "text-to-SQL" (the rejected alternative — see ADR-005)

## Relationships

- The **SID** is the keystone user: fans and web editors only receive value once
  the SID's data is trustworthy and published.
- An ingested game's stats update the **Record Book**; a **Notable Achievement** is
  detected by comparing that game against the **Record Book**.
- **Integrity check:** a **Player**'s per-game **Boxscore** stats summed over a season
  should reconcile to that player's row on the **Cumulative Season Statistics** page;
  a mismatch flags a parsing or identity-resolution error.
- Every Record Book answer, Notable Achievement, chart, and NLQ response carries its
  **Coverage Window** and source provenance.
- The **Athletic Data Warehouse** is the single system of record; the AI features
  read from it rather than maintaining their own separate stores.
- An approved **Achievement Suggestion** may enter an **Article Brief**; the resulting
  **Evidence Bundle** constrains every AI-authored **Article Version** and
  **Article Rendition**.
- A human marks one **Article Version** ready, then a publisher makes a separate
  **Distribution Submission**. No model may cross either human gate.

## Flagged ambiguities

- Athletics "wants all of these" (website data, internal tool, fan experience,
  editorial, achievements DB). Resolved for Release 1 by anchoring on a single
  primary user — the **SID** — and their jobs, rather than building for every
  audience at once.
- Records are only detectable within accumulated data. Resolved: both grains are
  backfillable from Sidearm. **Season/career** aggregates come from Cumulative Season
  Statistics pages; **single-game** records come from per-game Boxscores (~30/season,
  ~300 for one sport over a decade — bounded, and the intern parser already exists).
  Both should anchor on verified, namespaced Player identities. Remaining constraint:
  the **pre-2017-18 HTML version markup** likely will not work with the current parser —
  game-grain backfill may reach back only ~8 seasons, with older seasons falling back to
  cumulative season aggregates. Depth is both a parser-coverage question and a
  product-truth constraint: claims outside the verified Coverage Window must not be
  described as all-time.
- NLQ approach: free text-to-SQL (interns' ADR-003/004 direction) vs. curated
  semantic layer. Resolved: **curated semantic layer** — facts must be trustworthy
  because the SID may quote them publicly. See ADR-005.
- The legacy `GeneratedContent` bundle produces recap, spotlight, and social text
  directly from a boxscore without the governed Article workflow. Resolved: retain
  existing rows as read-only history, replace generation with Articles, and never
  treat legacy drafts as approved Article Versions. See ADR-010 and issue #152.
