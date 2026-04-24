# Schema Versioning

Vandals Stats Pipeline uses SQLAlchemy models for the current schema and keeps
Alembic available as the authoritative migration path for any shared or
production deployment.

## Current State

- The current local-development path bootstraps tables from ORM metadata when
  `DEV_MODE=true`.
- The migration framework exists under `backend/migrations/`, but the repository
  does not yet include committed Alembic revision files for the current model
  set.
- The current persisted model includes `games`, `team_stats`,
  `player_stat_groups`, `scoring_plays`, and `generated_content`.

This is acceptable for early local iteration, but it is not the long-term
change-management path for staging or production environments.

## Project Policy

1. Metadata-driven startup is allowed only for local development.
2. Alembic migrations are the required schema-management path for shared,
   staging, and production deployments.
3. Never change a deployed schema manually.
4. Every schema change must be reviewed alongside API contracts and governance
   artifacts.
5. Before the first shared deployment, create and commit a baseline Alembic
   revision covering the current schema.

## Change Checklist

- [ ] model changes reviewed
- [ ] matching Pydantic schemas updated
- [ ] migration generated and reviewed
- [ ] tests updated
- [ ] [Data Model](../architecture/data-model.md) updated if entity shape changed
- [ ] [Data Lineage](data-lineage.md) updated if data flow changed
- [ ] [Data Classification](data-classification.md) updated if classification changed

## Immediate Follow-Up Needed

The next schema-governance milestone for this repository should be:

- generate and commit the initial Alembic baseline revision
- wire deployment workflows to run `alembic upgrade head`
- stop treating ORM `create_all` as anything other than a local developer
  convenience
