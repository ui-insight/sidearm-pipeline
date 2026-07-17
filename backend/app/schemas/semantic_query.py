"""Typed requests and evidence-backed results for curated semantic queries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PositiveInt

from app.schemas.record_book import (
    LeaderboardRead,
    LeaderboardScope,
    RecordBookMetricRead,
)


class SemanticQueryId(StrEnum):
    """Stable identifiers that an interface or NLQ layer may select."""

    TEAM_SEASON_RECORD = "team_season_record"
    STAT_LEADERS = "stat_leaders"
    PLAYER_CAREER_TOTAL = "player_career_total"
    PLAYER_GAME_SPLIT = "player_game_split"


class ConferenceScope(StrEnum):
    """Supported conference filters for game-grain queries."""

    ALL = "all"
    CONFERENCE = "conference"
    NON_CONFERENCE = "non_conference"


class VenueScope(StrEnum):
    """Supported venue filters for player game splits."""

    ALL = "all"
    HOME = "home"
    AWAY = "away"
    NEUTRAL = "neutral"


class TeamSeasonRecordQuery(BaseModel):
    """Parameters for Idaho's final-game record in one WBB season."""

    query_id: Literal["team_season_record"] = "team_season_record"
    season: str = Field(pattern=r"^\d{4}-\d{2}$")
    conference_scope: ConferenceScope = ConferenceScope.ALL


class StatLeadersQuery(BaseModel):
    """Parameters for a vetted Record Book leaderboard."""

    query_id: Literal["stat_leaders"] = "stat_leaders"
    stat_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    scope: LeaderboardScope = LeaderboardScope.CAREER
    season: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    limit: int = Field(default=10, ge=1, le=25)


class PlayerCareerTotalQuery(BaseModel):
    """Parameters for one player's total across verified season facts."""

    query_id: Literal["player_career_total"] = "player_career_total"
    player_id: PositiveInt
    stat_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")


class PlayerGameSplitQuery(BaseModel):
    """Parameters for one player's game-grain split."""

    query_id: Literal["player_game_split"] = "player_game_split"
    player_id: PositiveInt
    stat_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,127}$")
    season: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    conference_scope: ConferenceScope = ConferenceScope.ALL
    venue_scope: VenueScope = VenueScope.ALL


SemanticQueryRequest = Annotated[
    TeamSeasonRecordQuery
    | StatLeadersQuery
    | PlayerCareerTotalQuery
    | PlayerGameSplitQuery,
    Field(discriminator="query_id"),
]


class SemanticQueryDefinitionRead(BaseModel):
    """One human-authored query exposed by the semantic catalog."""

    query_id: SemanticQueryId
    display_name: str
    description: str
    question_templates: list[str]
    parameter_schema: dict


class SemanticQueryCatalogRead(BaseModel):
    """The bounded set of deterministic questions the application can answer."""

    program_slug: str
    program_name: str
    queries: list[SemanticQueryDefinitionRead]


class SemanticWorkspaceOptionsRead(BaseModel):
    """Filter options available to the first Exploratory Workspace slice."""

    program_slug: str
    program_name: str
    seasons: list[str]
    metrics: list[RecordBookMetricRead]
    leader_limits: list[int]
    default_season: str | None = None
    default_stat_key: str | None = None


class SemanticCoverageRead(BaseModel):
    """Coverage boundary attached to one semantic-query answer."""

    grain: str
    first_season: str | None = None
    last_season: str | None = None
    completeness: str
    source_systems: list[str]
    known_limitations: list[str]
    verified_at: datetime | None = None
    statement: str


class TeamSeasonRecordGameRead(BaseModel):
    """One final game supporting a team season record."""

    game_id: int
    game_date: str | None = None
    opponent: str
    venue: str | None = None
    conference_event: bool
    idaho_score: int
    opponent_score: int
    result: Literal["win", "loss", "tie"]
    source_url: str


class TeamSeasonRecordRead(BaseModel):
    """Idaho's deterministic WBB record for a selected season and scope."""

    program_slug: str
    program_name: str
    season: str
    conference_scope: ConferenceScope
    games_played: int
    wins: int
    losses: int
    ties: int
    open_quality_issue_count: int
    coverage: SemanticCoverageRead
    games: list[TeamSeasonRecordGameRead]


class SemanticSeasonEvidenceRead(BaseModel):
    """One season fact contributing to a career aggregate."""

    season: str
    value: Decimal
    source_snapshot_id: int | None = None
    source_url: str | None = None


class PlayerCareerTotalRead(BaseModel):
    """One player's aggregate across authoritative season facts."""

    program_slug: str
    program_name: str
    player_id: int
    player_name: str
    stat_key: str
    stat_label: str
    aggregation_method: str
    total: Decimal | None = None
    seasons_count: int
    open_quality_issue_count: int
    coverage: SemanticCoverageRead
    season_breakdown: list[SemanticSeasonEvidenceRead]


class SemanticGameEvidenceRead(BaseModel):
    """One game fact contributing to a player split."""

    game_id: int
    game_date: str | None = None
    season: str
    opponent: str
    venue: str | None = None
    conference_event: bool
    value: Decimal
    source_snapshot_id: int | None = None
    source_url: str | None = None


class PlayerGameSplitRead(BaseModel):
    """One player's aggregate over a vetted game-grain filter set."""

    program_slug: str
    program_name: str
    player_id: int
    player_name: str
    stat_key: str
    stat_label: str
    aggregation_method: str
    season: str | None = None
    conference_scope: ConferenceScope
    venue_scope: VenueScope
    value: Decimal | None = None
    games_count: int
    open_quality_issue_count: int
    coverage: SemanticCoverageRead
    games: list[SemanticGameEvidenceRead]


class TeamSeasonRecordQueryResult(BaseModel):
    """Typed result envelope for ``team_season_record``."""

    query_id: Literal["team_season_record"] = "team_season_record"
    result: TeamSeasonRecordRead


class StatLeadersQueryResult(BaseModel):
    """Typed result envelope for ``stat_leaders``."""

    query_id: Literal["stat_leaders"] = "stat_leaders"
    result: LeaderboardRead


class PlayerCareerTotalQueryResult(BaseModel):
    """Typed result envelope for ``player_career_total``."""

    query_id: Literal["player_career_total"] = "player_career_total"
    result: PlayerCareerTotalRead


class PlayerGameSplitQueryResult(BaseModel):
    """Typed result envelope for ``player_game_split``."""

    query_id: Literal["player_game_split"] = "player_game_split"
    result: PlayerGameSplitRead


SemanticQueryResult = Annotated[
    TeamSeasonRecordQueryResult
    | StatLeadersQueryResult
    | PlayerCareerTotalQueryResult
    | PlayerGameSplitQueryResult,
    Field(discriminator="query_id"),
]
