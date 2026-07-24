# Schema Versioning

Vandals Stats Pipeline uses SQLAlchemy models for the current schema and keeps
Alembic available as the authoritative migration path for any shared or
production deployment.

## Current State

- The current local-development path bootstraps tables from ORM metadata when
  `DEV_MODE=true`.
- The repository has a linear, tested Alembic history from
  `0001_canonical_event_foundation` through
  `0007_shared_workspace_views`.
- The migration suite upgrades a fresh database to `head`, checks ORM drift,
  and exercises rollback boundaries with SQLite in CI. PostgreSQL 16 remains
  the standard shared-deployment database.
- The current persisted model includes the canonical event foundation, ingest
  history, normalized warehouse, roster provenance, reviewed identity
  resolutions, and shared workspace route definitions.

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

`0007_shared_workspace_views` creates the deployment-wide saved-view table and
its creator/time indexes. Downgrading to `0006_player_identity_resolutions`
removes that table without affecting warehouse or identity-resolution data.
