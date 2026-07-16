"""Pydantic schemas for cumulative season statistics and reconciliation."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CumulativePlayerRead(BaseModel):
    """One player row from the overall cumulative-season table."""

    model_config = ConfigDict(from_attributes=True)

    display_name: str
    jersey_number: str | None = None
    source_player_id: str | None = None
    bio_url: str | None = None
    games_played: int
    games_started: int | None = None
    stats: dict[str, Decimal]
    source_fields: dict[str, str]
    source_values: dict[str, str]


class CumulativeStatsRead(BaseModel):
    """Preview of one parsed cumulative-season source."""

    model_config = ConfigDict(from_attributes=True)

    sport_program_slug: str
    season: str
    source_system: str
    identity_source_system: str
    institution: str
    team_slug: str
    source_url: str
    players: list[CumulativePlayerRead]
    http_status: int


class CumulativeStatsImportRead(BaseModel):
    """Trust and persistence outcome for one cumulative-season import."""

    model_config = ConfigDict(from_attributes=True)

    source_url: str
    season: str
    source_snapshot_id: int
    players_seen: int
    players_resolved: int
    players_unresolved: int
    source_conflicts: int
    facts_written: int
    comparisons_run: int
    facts_matched: int
    facts_mismatched: int
    coverage_gaps: int
    quality_issues_created: int
    quality_issues_resolved: int
    coverage_completeness: str
    coverage_window_ids: list[int]
