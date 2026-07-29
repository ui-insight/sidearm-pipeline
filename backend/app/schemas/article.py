"""Pydantic contracts for Article Brief creation and evidence reads."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ArticleType = Literal["game_recap", "player_spotlight", "achievement_story"]
ArticleStatus = Literal[
    "brief",
    "generating",
    "in_edit",
    "ready",
    "needs_revalidation",
    "archived",
]
GenerationJobState = Literal["queued", "running", "succeeded", "failed"]
TrimmedAngle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
TrimmedAudience = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
TrimmedConstraints = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]
EditorInstructions = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]
OverrideReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=1000),
]
IdempotencyKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=255),
]


class ArticleBriefCreate(BaseModel):
    """The SID's intent and approved suggestions for one new Article."""

    model_config = ConfigDict(extra="forbid")

    suggestion_ids: list[int] = Field(min_length=1, max_length=25)
    article_type: ArticleType
    angle: TrimmedAngle
    audience: TrimmedAudience = "Vandal fans"
    constraints: TrimmedConstraints | None = None
    idempotency_key: IdempotencyKey

    @field_validator("suggestion_ids")
    @classmethod
    def validate_suggestion_ids(cls, values: list[int]) -> list[int]:
        """Require positive, unique suggestion identifiers."""
        if any(value <= 0 for value in values):
            raise ValueError("suggestion IDs must be positive")
        if len(values) != len(set(values)):
            raise ValueError("suggestion IDs must be unique")
        return values


class ArticleGameEvidenceRead(BaseModel):
    """The frozen game identity and result for an Article."""

    id: int
    canonical_uid: str
    sport: str | None
    season: str | None
    game_date: str | None
    title: str | None
    home_team: str | None
    away_team: str | None
    home_score: int | None
    away_score: int | None
    source_url: str


class EvidenceSourceRead(BaseModel):
    """The immutable source snapshot supporting an evidence item."""

    snapshot_id: int
    source_system: str
    source_type: str
    source_url: str
    content_hash: str
    fetched_at: datetime


class EvidenceCoverageWindowRead(BaseModel):
    """The exact Coverage Window governing a comparative claim."""

    id: int
    grain: str
    first_season: str | None
    last_season: str | None
    completeness: Literal["complete", "partial"]
    known_limitations: str | None
    claim_scope: str


class EvidenceVerdictRead(BaseModel):
    """The human approval frozen with one evidence item."""

    state: Literal["approved"]
    reviewed_at: datetime
    reviewed_by: str


class ArticleEvidenceSuggestionRead(BaseModel):
    """One approved comparative fact in the Evidence Bundle."""

    evidence_item_id: str
    id: int
    suggestion_key: str
    player_id: int
    player_name: str
    stat_definition_id: int
    notability_policy_id: int
    notability_policy_version: int
    stat_key: str
    stat_label: str
    achievement_type: str
    scope: str
    computed_value: Decimal
    comparison_value: Decimal | None
    rank: int | None
    phrasing: str | None
    context: dict
    source: EvidenceSourceRead
    coverage_window: EvidenceCoverageWindowRead
    verdict: EvidenceVerdictRead
    fact_hash: str


class EvidenceBundleRead(BaseModel):
    """The immutable evidence boundary attached to an Article Brief."""

    id: int
    version: int
    schema_version: str
    content_hash: str
    created_by: str
    created_at: datetime
    suggestions: list[ArticleEvidenceSuggestionRead]


class ArticleDraftBlock(BaseModel):
    """One writer-produced block with explicit supporting evidence IDs."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["lead", "body", "closing"]
    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=5000),
    ]
    evidence_ids: list[str] = Field(min_length=1, max_length=25)

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        """Require unique, non-empty evidence references."""
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("evidence IDs must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("evidence IDs must be unique")
        return normalized


class ArticleDraftOutput(BaseModel):
    """Strict structured payload returned by the evidence-bound writer."""

    model_config = ConfigDict(extra="forbid")

    headline: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    headline_evidence_ids: list[str] = Field(min_length=1, max_length=25)
    blocks: list[ArticleDraftBlock] = Field(min_length=1, max_length=20)

    @field_validator("headline_evidence_ids")
    @classmethod
    def validate_headline_evidence_ids(cls, values: list[str]) -> list[str]:
        """Require unique evidence references for the headline."""
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("headline evidence IDs must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("headline evidence IDs must be unique")
        return normalized


class ArticleValidationFindingRead(BaseModel):
    """One deterministic fact or Style Guide validation result."""

    code: str
    severity: Literal["error", "warning"]
    message: str
    block_index: int | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ArticleVersionRead(BaseModel):
    """One immutable Article draft checkpoint."""

    id: int
    article_id: int
    version: int
    origin: Literal["ai", "human"]
    parent_version_id: int | None
    headline: str
    headline_evidence_ids: list[str]
    body: str
    blocks: list[ArticleDraftBlock]
    evidence_bundle_id: int
    evidence_hash: str
    style_guide_version_id: int
    style_snapshot: dict
    style_hash: str
    prompt_version: str | None
    editor_instructions: str | None
    provider: str | None
    model: str | None
    output_hash: str | None
    validation_results: list[ArticleValidationFindingRead]
    author: str | None
    created_at: datetime
    warning_overrides: list["ArticleWarningOverrideRead"] = Field(default_factory=list)


class ArticleVersionCreate(BaseModel):
    """One append-only human edit based on the latest Article Version."""

    model_config = ConfigDict(extra="forbid")

    base_version_id: int = Field(gt=0)
    headline: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    headline_evidence_ids: list[str] = Field(min_length=1, max_length=25)
    blocks: list[ArticleDraftBlock] = Field(min_length=1, max_length=20)


class ArticleWarningOverrideCreate(BaseModel):
    """A human reason for accepting one nonblocking validation warning."""

    model_config = ConfigDict(extra="forbid")

    finding_code: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]
    reason: OverrideReason


class ArticleWarningOverrideRead(BaseModel):
    """Audit data for one warning acknowledgement."""

    id: int
    article_version_id: int
    finding_code: str
    reason: str
    overridden_by: str
    created_at: datetime


class ArticleReadyCreate(BaseModel):
    """An explicit human readiness decision for one immutable version."""

    model_config = ConfigDict(extra="forbid")

    warning_overrides: list[ArticleWarningOverrideCreate] = Field(
        default_factory=list,
        max_length=50,
    )


class ArticleReadinessDecisionRead(BaseModel):
    """One append-only ready or reopen audit event."""

    id: int
    article_id: int
    article_version_id: int
    action: Literal["ready", "reopened"]
    actor: str
    reason: str | None
    created_at: datetime


class ArticleEvidenceChangeRead(BaseModel):
    """One material difference between frozen and current Article evidence."""

    change_type: Literal[
        "game_changed",
        "suggestion_removed",
        "fact_changed",
        "coverage_changed",
        "source_changed",
        "approval_changed",
    ]
    suggestion_key: str | None = None
    label: str
    previous_value: Any = None
    current_value: Any = None


class ArticleEvidenceRevalidationRead(BaseModel):
    """An append-only source-drift detection and its resolution state."""

    id: int
    article_id: int
    previous_evidence_bundle_id: int
    refreshed_evidence_bundle_id: int | None
    change_hash: str
    changes: list[ArticleEvidenceChangeRead]
    detected_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None


class ArticleReadyRead(BaseModel):
    """The resulting Article state after a readiness decision."""

    article_id: int
    status: ArticleStatus
    ready_version: ArticleVersionRead
    decision: ArticleReadinessDecisionRead


class ArticleGenerationJobCreate(BaseModel):
    """An idempotent human request for an evidence-bound Article Draft."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: IdempotencyKey
    base_version_id: int | None = Field(default=None, gt=0)
    editor_instructions: EditorInstructions | None = None


class ArticleGenerationJobRead(BaseModel):
    """Durable status and audit metadata for a writer job."""

    id: int
    article_id: int
    state: GenerationJobState
    requested_by: str
    attempt_count: int
    evidence_bundle_id: int
    style_guide_version_id: int
    base_version_id: int | None
    style_snapshot: dict
    style_hash: str
    provider: str
    model: str
    prompt_version: str
    editor_instructions: str | None
    input_hash: str
    output_hash: str | None
    validation_results: list[ArticleValidationFindingRead]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    article_version: ArticleVersionRead | None = None


class ArticleBriefRead(BaseModel):
    """A complete SID-facing Article Brief and its evidence audit data."""

    id: int
    status: ArticleStatus
    article_type: ArticleType
    angle: str
    audience: str
    constraints: str | None
    created_by: str
    created_at: datetime
    game: ArticleGameEvidenceRead
    evidence_bundle: EvidenceBundleRead
    latest_generation_job: ArticleGenerationJobRead | None = None
    latest_version: ArticleVersionRead | None = None
    ready_version: ArticleVersionRead | None = None
    versions: list[ArticleVersionRead] = Field(default_factory=list)
    readiness_history: list[ArticleReadinessDecisionRead] = Field(default_factory=list)
    active_revalidation: ArticleEvidenceRevalidationRead | None = None
    revalidation_history: list[ArticleEvidenceRevalidationRead] = Field(
        default_factory=list
    )


class ArticleQueueItemRead(BaseModel):
    """One Article row for the SID editorial queue."""

    id: int
    status: ArticleStatus
    article_type: ArticleType
    angle: str
    owner: str
    created_at: datetime
    game_date: str | None
    game_title: str | None
    latest_version: ArticleVersionRead | None = None
    ready_version: ArticleVersionRead | None = None
    active_revalidation: ArticleEvidenceRevalidationRead | None = None


class ArticleQueueRead(BaseModel):
    """The current SID Article work queue."""

    items: list[ArticleQueueItemRead]
    total: int
