# Data Governance

This document defines the data governance standards for Vandals Stats Pipeline.

## Current Data Posture

The project currently handles two primary classes of information:

- public athletics event data sourced from publicly accessible Sidearm pages
- internal operational and editorial metadata created by the pipeline itself

The current schema is documented in [Data Model](../architecture/data-model.md),
and the current movement of data is captured in [Data Lineage](data-lineage.md).

## Principles

1. **Data is an asset** — treat all data with appropriate care and documentation
2. **Classify before storing** — determine data sensitivity before designing storage
3. **Minimize collection** — only collect data that is necessary for the application
4. **Document lineage** — track where data comes from and where it goes
5. **Secure by default** — apply the most restrictive access appropriate to the data class

## Database Conventions

### Development
- PostgreSQL 16 via asyncpg is the standard application database in local and deployed environments
- local development currently bootstraps tables automatically in `DEV_MODE=true`
- SQLite remains limited to tests or isolated one-off experiments

### Production
- PostgreSQL 16 via asyncpg
- Alembic for schema migrations (never modify production schema manually)
- Regular backups with tested restore procedures

### Schema Standards
- All models extend the common `Base` class from `backend/app/db/base.py`
- One SQLAlchemy model file per resource in `backend/app/models/`
- Corresponding Pydantic schema file in `backend/app/schemas/`
- Use SQLAlchemy relationships for foreign key associations
- Add database indexes for frequently queried columns
- Update the data-model and governance docs whenever entity shape or data movement changes

## Data Flow Documentation

The authoritative project data-flow inventory lives in
[Data Lineage](data-lineage.md). Update that document whenever a schema,
integration, or publication workflow change alters how data is ingested,
transformed, stored, or exported.

## Regulatory Compliance

Based on the current scope, the core Sidearm event-data pipeline is not expected
to process FERPA, HIPAA, PCI-DSS, or GLBA regulated records. That conclusion
depends on staying within public athletics event data, internal operational
metadata, and editorial drafts.

The following would require this posture to be revisited:

| Regulation | Applies When |
|---|---|
| **FERPA** | Student-athlete records beyond publicly released athletics statistics are introduced |
| **HIPAA** | Injury, treatment, or medical information is introduced |
| **GDPR** | The deployment meaningfully targets or profiles EU residents |
| **PCI-DSS** | Payment workflows are added |
| **GLBA** | Financial-account or student financial data is introduced |
| **State Laws** | New privacy-sensitive personal data is collected or retained |

If project scope expands in any of those directions, update this document and
the data-classification inventory before implementation ships.

## Data Retention

The table below defines the governing retention targets for the current scope.
Some of these controls are not yet automated in code and should be treated as
required operational policy until automation is added.

| Data Category | Retention Period | Disposal Method |
|---|---|---|
| Normalized game and stat records | Retain as part of the athletics historical event archive unless superseded by a future archive policy | Archive or export before destructive purge |
| Raw Sidearm source snapshots | Retain with the related source/game record until raw-snapshot retention automation is implemented; target future policy is one year from final ingest | Delete with an auditable disposal record once retention automation exists |
| Generated coverage drafts | Retain with the parent game record unless athletics communications adopts a different editorial retention rule | Delete or archive with the parent event when policy changes |
| Ingest-run operational metadata | Minimum one year; enforcement is currently an operational responsibility because automated expiration is not implemented | Archive then delete per operational policy |
| Data-quality issues and identity resolutions | Retain with the affected warehouse facts while those facts remain active; preserve enough history to explain corrections | Archive with the warehouse record before destructive purge |
| Achievement Suggestions, AI provenance, and current SID verdict | Retain with the source game and applicable policy version; an immutable verdict-event history is not yet implemented | Archive with the game or future editorial audit record |
| Shared workspace views | Retain until an authenticated user deletes the shared definition or a future workspace policy expires it | Delete through the authenticated workspace API |
| Secrets and service credentials | Retain only while active and necessary | Rotate, revoke, and remove from secret storage when no longer needed |

Retention periods are policy targets, not claims of automated enforcement. Raw
snapshot, ingest-run, and editorial-record expiration jobs do not currently
exist. Production owners must document who executes and verifies disposal until
automation and immutable audit events are implemented.

## Documentation Obligations

Every schema or workflow change that affects stored data should update:

- [Data Model](../architecture/data-model.md)
- [Data Lineage](data-lineage.md)
- [Data Classification](data-classification.md)
- [Schema Versioning](schema-versioning.md), when the migration policy or status changes
