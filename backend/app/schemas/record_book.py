"""Schemas for evidence-backed Record Book leaderboards."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class LeaderboardScope(StrEnum):
    """Supported aggregation scopes for a Record Book leaderboard."""

    CAREER = "career"
    SEASON = "season"


class RecordBookMetricRead(BaseModel):
    """One aggregable player metric available to the Record Book."""

    stat_key: str
    display_label: str
    value_type: str
    unit: str | None = None
    aggregation_method: str
    comparison_direction: str
    display_format: str | None = None


class RecordBookMetricCatalogRead(BaseModel):
    """The program metric catalog that drives Record Book controls."""

    program_slug: str
    program_name: str
    metrics: list[RecordBookMetricRead]


class RecordBookCoverageRead(BaseModel):
    """Coverage boundary and limitations attached to a leaderboard result."""

    first_season: str | None = None
    last_season: str | None = None
    completeness: str
    source_systems: list[str]
    known_limitations: list[str]
    verified_at: datetime | None = None
    statement: str


class LeaderSeasonEvidenceRead(BaseModel):
    """One season-source contribution to a leaderboard total."""

    season: str
    value: Decimal
    source_snapshot_id: int | None = None
    source_url: str | None = None


class LeaderboardLeaderRead(BaseModel):
    """One ranked player with the season evidence behind the total."""

    rank: int
    player_id: int
    player_name: str
    total: Decimal
    seasons_count: int
    season_breakdown: list[LeaderSeasonEvidenceRead]


class LeaderboardRead(BaseModel):
    """A leaderboard with scope, coverage, evidence, and quality context."""

    program_slug: str
    program_name: str
    stat_key: str
    stat_label: str
    scope: LeaderboardScope
    season: str | None = None
    available_seasons: list[str]
    total_players: int
    open_quality_issue_count: int
    coverage: RecordBookCoverageRead
    leaders: list[LeaderboardLeaderRead]
