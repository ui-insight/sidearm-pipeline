"""Schemas for deterministic and AI-assisted Achievement Suggestions."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AchievementSuggestionRead(BaseModel):
    """One verified comparative fact prepared for SID review."""

    id: int
    game_id: int
    player_id: int
    player_name: str
    stat_key: str
    stat_label: str
    suggestion_key: str
    achievement_type: str
    scope: str
    computed_value: Decimal
    comparison_value: Decimal | None
    rank: int | None
    deterministic_notability_score: Decimal
    context: dict
    coverage_context: dict
    phrasing: str | None
    ai_rank: int | None
    ai_model: str | None
    ai_prompt_version: str | None
    ai_output_hash: str | None
    ai_ranked_at: datetime | None
    source_url: str | None
    reviewed_at: datetime | None
    reviewed_by: str | None
    reviewed_fact_hash: str | None
    state: Literal["pending", "approved", "rejected"]


class AchievementVerdictRequest(BaseModel):
    """One SID editorial decision for an Achievement Suggestion."""

    state: Literal["approved", "rejected"]


class AchievementReviewGameRead(BaseModel):
    """One game and its suggestions in the selected review state."""

    game_id: int
    title: str | None
    game_date: str | None
    season: str | None
    home_team: str | None
    away_team: str | None
    home_score: int | None
    away_score: int | None
    source_url: str
    suggestions: list[AchievementSuggestionRead]


class AchievementReviewQueueRead(BaseModel):
    """A page of games plus global verdict counts for queue navigation."""

    items: list[AchievementReviewGameRead]
    total_games: int
    pending_count: int
    approved_count: int
    rejected_count: int


class AchievementAICandidateOutput(BaseModel):
    """The only per-candidate fields the model may return."""

    model_config = ConfigDict(extra="forbid")

    suggestion_key: str = Field(min_length=1, max_length=255)
    phrasing: str = Field(min_length=20, max_length=300)


class AchievementAIOutput(BaseModel):
    """Strict structured response expected from the ranking model."""

    model_config = ConfigDict(extra="forbid")

    ranked_suggestions: list[AchievementAICandidateOutput] = Field(
        min_length=1,
        max_length=100,
    )


class AchievementRankingRead(BaseModel):
    """Validated, persisted result from one ranking request."""

    game_id: int
    model: str
    prompt_version: str
    suggestions: list[AchievementSuggestionRead]
