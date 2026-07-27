# Schema Versioning

Vandals Stats Pipeline uses SQLAlchemy models for the current schema and keeps
Alembic available as the authoritative migration path for any shared or
production deployment.

## Current State

- The current local-development path bootstraps tables from ORM metadata when
  `DEV_MODE=true`.
- The repository has a linear, tested Alembic history from
  `0001_canonical_event_foundation` through
  `0009_ai_achievement_ranking`.
- The migration suite upgrades a fresh database to `head`, checks ORM drift,
  and exercises rollback boundaries with SQLite in CI. PostgreSQL 16 remains
  the standard shared-deployment database.
- The current persisted model includes the canonical event foundation, ingest
  history, normalized warehouse, roster provenance, reviewed identity
  resolutions, shared workspace route definitions, versioned Notability policy,
  and deterministic Achievement Suggestions.

ORM `create_all` remains a local and test convenience. It is not the schema
change-management path for staging or production environments.

## Project Policy

1. Metadata-driven startup is allowed only for local development.
2. Alembic migrations are the required schema-management path for shared,
   staging, and production deployments.
3. Never change a deployed schema manually.
4. Every schema change must be reviewed alongside API contracts and governance
   artifacts.
5. Deployments must run `alembic upgrade head` before serving application
   traffic that depends on a new schema.

## Change Checklist

- [ ] model changes reviewed
- [ ] matching Pydantic schemas updated
- [ ] migration generated and reviewed
- [ ] tests updated
- [ ] [Data Model](../architecture/data-model.md) updated if entity shape changed
- [ ] [Data Lineage](data-lineage.md) updated if data flow changed
- [ ] [Data Classification](data-classification.md) updated if classification changed

## Current Head

`0009_ai_achievement_ranking` adds nullable AI ordering, model, prompt-version,
output-hash, and ranking-timestamp fields to `achievement_suggestions`.

Migration `0010_achievement_review_verdicts` adds reviewer and review-timestamp
provenance for SID approval and rejection decisions.
Downgrading to `0008_deterministic_achievements` removes only those AI metadata
fields and retains every deterministic suggestion and its optional phrasing.

The AI fields remain nullable because deterministic detection is fully usable
without model access. A validated ranking writes `phrasing`, `ai_rank`,
`ai_model`, `ai_prompt_version`, `ai_output_hash`, and `ai_ranked_at` together.

## Previous Head

`0008_deterministic_achievements` creates the versioned Notability policy,
metric-rule, and Achievement Suggestion tables. Downgrading to
`0007_shared_workspace_views` removes those tables without affecting warehouse
facts or shared workspace views.

### `notability_policies` and `notability_policy_metrics`

Defined in `backend/app/models/achievement.py`.

Purpose:
- retain immutable, sport-specific policy versions so earlier scores remain
  reproducible
- keep editorial importance weights, thresholds, and suppression rules separate
  from stable `StatDefinition` semantics per ADR-008
- assign deterministic scope weights and a program top-N boundary

### `achievement_suggestions`

Defined in `backend/app/models/achievement.py`.

Purpose:
- persist career highs, season highs, career threshold crossings, and program
  top-N game performances computed after a final WBB boxscore ingest
- retain the computed value, comparison value or rank, policy version, source
  snapshot, and a snapshot of the applicable Coverage Window
- provide pending, approved, and rejected states for the later SID Verdict
  workflow and a nullable phrasing field for validated AI assistance

The `all_time_top_n` detector name follows the issue contract, but its stored
coverage context limits presentation to “since `<season>`” or “in available
warehouse history” unless complete all-time coverage is actually verified.

## Earlier Head

`0007_shared_workspace_views` creates the deployment-wide saved-view table and
its creator/time indexes. Downgrading to `0006_player_identity_resolutions`
removes that table without affecting warehouse or identity-resolution data.
