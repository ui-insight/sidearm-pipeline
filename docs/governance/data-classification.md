# Data Classification

All data stored or processed by Vandals Stats Pipeline must be classified before
implementation. This inventory describes the schema at migration
`0010_achievement_review_verdicts`.

## Classification levels

### Public

- Information already released for public use, such as published rosters,
  schedules, boxscores, statistics, source URLs, and evidence derived solely from
  those sources.
- Standard database storage is acceptable; integrity and provenance still matter.

### Internal

- University/project operational information or unpublished editorial work.
- Authentication is required. Least-privilege authorization and auditable
  operator actions are preferred and become required where noted below.

### Confidential

- Information that could cause material harm if disclosed, including sensitive
  staffing, strategy, or unpublished communications information.
- Role-based access and encrypted storage are required when introduced.

### Restricted

- Credentials, regulated personal data, or information protected by law or
  institutional security policy.
- Store in an approved secret manager or protected environment configuration,
  minimize collection, encrypt, restrict access, and audit use.

## As-built data inventory

| Data set | Classification | Persisted locations | Access and handling notes |
|---|---|---|---|
| Canonical game metadata, schedules, scores, venues, team labels, source URLs | Public | `games`, `event_sources`, `event_status_history` | Source-derived athletics record; internal publish status remains operational context |
| Raw public Sidearm payloads and fetch evidence | Public | `games.raw_html`, `source_snapshots` | Limit direct access to maintainers because raw payloads are unvalidated third-party content; apply retention policy |
| Legacy boxscore rows and scoring plays | Public | `team_stats`, `player_stat_groups`, `scoring_plays` | Retained for compatibility; not the governed Record Book query surface |
| Sport, team, opponent aliases, player names, public roster attributes, and bio URLs | Public | `sport_programs`, `teams`, `opponent_aliases`, `players`, `player_external_identities`, `player_seasons` | External identifiers are public-source evidence but should not be treated as global identifiers outside their namespace |
| Normalized game and season facts and metric definitions | Public | `stat_definitions`, `player_game_stats`, `team_game_stats`, `player_season_stats`, `team_season_stats` | Facts remain bounded by provenance and Coverage Windows |
| Coverage statements and source limitations | Public unless they contain internal source-contract notes | `coverage_windows` | Publish safe limitations with facts; keep confidential contract details out of free-text fields |
| Ingest execution status, retry/error detail, and run metadata | Internal | `ingest_runs` | Platform maintainers and authorized athletics operations; error text/metadata must not contain credentials |
| Data-quality issues and identity-resolution decisions | Internal | `data_quality_issues`, `player_identity_resolutions` | May contain free-text notes; do not enter medical, academic, contact, or other regulated information |
| Notability-policy weights, thresholds, and suppression rules | Internal | `notability_policies`, `notability_policy_metrics` | Editorial policy, versioned for reproducibility |
| Unapproved Achievement Suggestions, AI phrasing/provenance, reviewer label, and verdict state | Internal | `achievement_suggestions` | Authenticated SID/editorial workflow; approved wording is not automatically public until published elsewhere |
| Generated recaps, spotlights, and social drafts | Internal | `generated_content` | Unpublished editorial work; athletics communications and maintainers only |
| Shared workspace names, filters, creator label, and timestamp | Internal | `workspace_views` | Shared across authenticated users; current prototype has no per-user ownership boundary |
| Semantic questions, Record Book results, pregame briefs, and CSV exports | Classification inherited from their inputs; normally Public facts in an Internal workflow | Computed in transit; not persisted as dedicated result tables | Avoid placing confidential prompts or notes into natural-language questions; exported files leave application control |
| API keys, application secrets, passwords, and service credentials | Restricted | Environment or approved secret manager; never application tables or source control | Platform administrators only; rotate and revoke when no longer needed |

At the current scope, no FERPA, HIPAA, PCI-DSS, or GLBA data is expected in the
core warehouse. Public student-athlete roster and performance information does
not authorize collection of academic, medical, contact, financial, or other
non-public student records.

## Free-text field rule

`error_message`, ingest metadata, quality-issue details, resolution notes,
workspace names, generated drafts, and natural-language questions can accept or
derive free text. Operators must not enter secrets or regulated personal data.
If workflows begin collecting such information, stop and revise the data model,
classification, access controls, and retention policy before deployment.

## Handling rules by classification

| Rule | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| Authentication | Not required for the data itself | Required | Required | Required |
| Authorization | Not required for published facts | Least privilege; required for editorial/operational actions | Required | Required |
| Encryption at rest | Platform baseline | Platform baseline | Required | Required |
| Encryption in transit | Required for deployed services | Required | Required | Required |
| Audit logging | Integrity/provenance as applicable | Required for consequential operator/editorial actions before production | Required | Required |
| Retention and disposal | Documented policy | Documented and operationally enforced | Secure disposal | Rotate, revoke, and securely remove |

## Current control gap

The shared prototype credential does not provide individual identity, resource
ownership, RBAC, or immutable operator auditing. Internal tables must not be
treated as production-ready merely because the prototype authentication gate can
be enabled. Individual authentication, authorization, recovery, and audit
requirements remain production-release gates.
