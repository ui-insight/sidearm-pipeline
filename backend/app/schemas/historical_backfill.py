"""Schemas for bounded historical WBB season backfills."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.current_season import CurrentSeasonSyncRead
from app.schemas.season_stats import CumulativeStatsImportRead


class HistoricalSeasonCoverageRead(BaseModel):
    """Coverage evidence for one historical WBB season."""

    model_config = ConfigDict(from_attributes=True)

    schedule_events_seen: int
    final_games: int
    final_games_with_boxscores: int
    final_games_ingested: int
    missing_boxscores: int
    failed_boxscores: int
    open_identity_issues: int
    open_quality_issues: int
    game_completeness: str
    game_coverage_window_id: int


class HistoricalSeasonBackfillRead(BaseModel):
    """Operator-readable outcome for one bounded historical season backfill."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    sport_slug: str
    season: str
    status: str
    started_at: datetime
    finished_at: datetime
    game_sync: CurrentSeasonSyncRead
    season_stats_status: str
    season_stats_error: str | None
    season_stats: CumulativeStatsImportRead | None
    coverage: HistoricalSeasonCoverageRead
