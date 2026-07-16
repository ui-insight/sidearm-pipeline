"""Schemas for sequential, resumable historical WBB range backfills."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.historical_backfill import HistoricalSeasonCoverageRead


class HistoricalRangeSeasonRead(BaseModel):
    """Outcome for one season checkpoint in a historical range."""

    model_config = ConfigDict(from_attributes=True)

    season: str
    status: str
    season_run_id: int | None
    started_at: datetime
    finished_at: datetime
    coverage: HistoricalSeasonCoverageRead | None
    error_type: str | None
    error_message: str | None


class HistoricalRangeBackfillRead(BaseModel):
    """Operator-readable result for a historical WBB range backfill."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    sport_slug: str
    start_season: str
    end_season: str
    status: str
    boxscore_delay_seconds: float
    resumed: bool
    started_at: datetime
    finished_at: datetime
    seasons_total: int
    seasons_attempted: int
    seasons_skipped: int
    seasons_succeeded: int
    seasons_partial: int
    seasons_failed: int
    seasons: list[HistoricalRangeSeasonRead]
