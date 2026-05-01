# Data Classification

All data stored or processed by Vandals Stats Pipeline must be classified
according to the following framework, aligned with university data governance
policy.

## Classification Levels

### Public
- **Definition**: Information that can be freely shared with anyone
- **Examples**: published athletics event information, public schedules, public boxscores
- **Controls**: no special access controls required
- **Storage**: standard database storage

### Internal
- **Definition**: information intended for use within the university community or project team
- **Examples**: operational metadata, unpublished editorial drafts, internal run notes
- **Controls**: authentication required; least-privilege access preferred
- **Storage**: standard database storage with authenticated access

### Confidential
- **Definition**: information that could cause harm if disclosed inappropriately
- **Examples**: internal staffing notes, unpublished strategy or communications plans
- **Controls**: role-based access control; encryption at rest recommended
- **Storage**: encrypted database fields or encrypted volumes when stored

### Restricted
- **Definition**: information protected by law, regulation, or security policy
- **Examples**: API keys, secret tokens, account credentials, regulated personal data
- **Controls**: strict role-based access; encryption at rest required; audit logging
- **Storage**: secret manager or protected environment configuration; minimize storage

## Data Inventory

Current project inventory:

| Data Element | Classification | Location | Access Roles | Regulation |
|---|---|---|---|---|
| Game metadata, team names, scores, game dates, source URLs | Public | `games` | backend API, internal UI, future athletics website consumers | None currently expected |
| Team statistics, player stat groups, scoring plays | Public | `team_stats`, `player_stat_groups`, `scoring_plays` | backend API, internal UI, future athletics website consumers | None currently expected |
| Raw source HTML snapshots from public Sidearm pages | Public | `games.raw_html` | platform maintainers, parser regression tooling | None currently expected |
| Generated recaps, spotlights, and social drafts before publication | Internal | `generated_content` | athletics communications staff, platform maintainers | None currently expected |
| Published editorial content derived from generated coverage | Public | downstream website or CMS publication surface | athletics website visitors, communications staff | None currently expected |
| Operational ingest timestamps, future job history, and future audit metadata | Internal | `games.ingested_at`; future operational tables | platform maintainers, athletics operations | None currently expected |
| API keys, application secrets, and service credentials | Restricted | `.env` or secret-management system, not application tables | platform administrators only | Institutional security policy |

At the current scope, no FERPA, HIPAA, PCI-DSS, or GLBA data is expected to be
stored in the core event pipeline.

## Handling Rules by Classification

| Rule | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| Authentication | No | Yes | Yes | Yes |
| Authorization (RBAC) | No | Recommended | Yes | Yes |
| Encryption at rest | No | No | Recommended | Required |
| Encryption in transit | Recommended | Yes | Yes | Yes |
| Audit logging | No | Recommended for operational actions | Recommended | Required |
| Data retention policy | Yes | Yes | Yes | Yes |
| Disposal procedures | Delete or archive per business need | Delete or archive per operational policy | Secure delete or restricted archive | Rotate, revoke, and securely remove |
