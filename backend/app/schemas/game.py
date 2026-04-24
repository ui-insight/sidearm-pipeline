"""Pydantic schemas for games and boxscore data."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class IngestRequest(BaseModel):
    """Request body for ingesting a Sidearm boxscore URL."""

    url: HttpUrl = Field(..., description="Sidearm boxscore page URL")


class TeamStatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stat_name: str
    home_value: str | None = None
    away_value: str | None = None
    sort_order: int = 0


class PlayerStatGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    team: str | None = None
    columns: list[str]
    rows: list[list[str]]


class ScoringPlayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period: str | None = None
    clock: str | None = None
    team: str | None = None
    description: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    sort_order: int = 0


class GameSummary(BaseModel):
    """Lightweight listing view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    canonical_uid: str
    source_system: str = "sidearm"
    source_event_id: str | None = None
    sport: str | None = None
    sport_name: str | None = None
    gender: str | None = None
    season: str | None = None
    game_date: str | None = None
    event_shape: str = "team_contest"
    event_status: str = "unknown"
    publish_status: str = "draft"
    home_team: str | None = None
    away_team: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    location_name: str | None = None
    venue_name: str | None = None
    home_away_neutral: str | None = None
    conference_event: bool = False
    exhibition: bool = False
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_successful_ingest_at: datetime | None = None
    ingested_at: datetime


class EventSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    source_url: str
    source_id: str | None = None
    primary_source: bool = False
    discovered_at: datetime
    last_fetched_at: datetime | None = None


class SourceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parser_version: str
    content_hash: str
    http_status: int | None = None
    fetched_at: datetime


class EventStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_status: str | None = None
    to_status: str
    reason: str | None = None
    changed_at: datetime


class GameDetail(GameSummary):
    """Full boxscore view."""

    team_stats: list[TeamStatRead] = []
    player_stats: list[PlayerStatGroupRead] = []
    scoring_plays: list[ScoringPlayRead] = []
    event_sources: list[EventSourceRead] = []
    source_snapshots: list[SourceSnapshotRead] = []
    status_history: list[EventStatusHistoryRead] = []
    generated_content: list["GeneratedContentRead"] = []  # noqa: F821


# Imported after GameDetail to avoid circular import at module load time.
from app.schemas.content import GeneratedContentRead  # noqa: E402

GameDetail.model_rebuild()
