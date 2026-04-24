"""Pydantic schemas for generated content."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GeneratedContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int
    recap: str
    spotlight_player: str | None = None
    spotlight_body: str
    social_post: str
    headline: str | None = None
    model: str | None = None
    generated_at: datetime


class GeneratedCoverage(BaseModel):
    """Schema the LLM must return via structured output."""

    headline: str = Field(
        ...,
        description=(
            "A punchy news headline under 90 characters. Should read like a sports "
            "desk headline, not a tweet."
        ),
    )
    recap: str = Field(
        ...,
        description=(
            "A 2-3 paragraph game recap (250-350 words) in AP sports-news style. "
            "Lead with the final score and the key narrative, then support with "
            "specific stats and plays. No hashtags, no emoji. Write in third "
            "person, past tense."
        ),
    )
    spotlight_player: str = Field(
        ...,
        description=(
            "The single standout player from the boxscore, written 'Last, First' "
            "exactly as they appear in the stats tables."
        ),
    )
    spotlight_body: str = Field(
        ...,
        description=(
            "A 2-3 sentence feature blurb on the spotlight player citing concrete "
            "stat-line numbers. First-person not allowed."
        ),
    )
    social_post: str = Field(
        ...,
        description=(
            "A single social post under 280 characters including final score, "
            "a stat nugget, and at most one hashtag. No emoji unless tasteful."
        ),
    )
