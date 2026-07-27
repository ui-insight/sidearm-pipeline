"""Pydantic contracts for Article Brief creation and evidence reads."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ArticleType = Literal["game_recap", "player_spotlight", "achievement_story"]
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


class ArticleBriefRead(BaseModel):
    """A complete SID-facing Article Brief and its evidence audit data."""

    id: int
    status: Literal["brief"]
    article_type: ArticleType
    angle: str
    audience: str
    constraints: str | None
    created_by: str
    created_at: datetime
    game: ArticleGameEvidenceRead
    evidence_bundle: EvidenceBundleRead
