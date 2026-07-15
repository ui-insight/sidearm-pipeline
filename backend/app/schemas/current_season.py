"""Schemas for bounded current-season warehouse synchronization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.roster import RosterImportRead


class CurrentSeasonGameRefreshRead(BaseModel):
    """One selected final game and the reason it was refreshed."""

    model_config = ConfigDict(from_attributes=True)

    game_id: int
    title: str
    source_url: str
    reasons: list[str]
    status: str
    error: str | None = None


class CurrentSeasonSyncRead(BaseModel):
    """Operator-readable result of one bounded WBB season synchronization."""

    model_config = ConfigDict(from_attributes=True)

    run_id: int
    sport_slug: str
    season: str
    status: str
    correction_lookback: int
    started_at: datetime
    finished_at: datetime
    roster: RosterImportRead
    schedule_events_seen: int
    schedule_games_created: int
    schedule_games_changed: int
    schedule_games_unchanged: int
    final_boxscores_seen: int
    boxscores_selected: int
    boxscores_refreshed: int
    boxscores_skipped: int
    boxscores_failed: int
    open_identity_issues: int
    games: list[CurrentSeasonGameRefreshRead]
