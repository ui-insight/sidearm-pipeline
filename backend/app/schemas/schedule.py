"""Pydantic schemas for discovered schedule events."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ScheduleEventRead(BaseModel):
    """Read model for a Sidearm schedule event discovered from a schedule page."""

    model_config = ConfigDict(from_attributes=True)

    sport_slug: str
    sport_name: str
    gender: str | None = None
    season: str | None = None
    source_system: str
    schedule_url: str
    source_event_id: str | None = None
    opponent_source_id: str | None = None
    opponent_name: str | None = None
    event_status: str
    home_away_neutral: str | None = None
    event_date: date | None = None
    date_text: str | None = None
    time_text: str | None = None
    location_name: str | None = None
    venue_name: str | None = None
    conference_name: str | None = None
    conference_event: bool = False
    result_status: str | None = None
    team_score: int | None = None
    opponent_score: int | None = None
    source_urls: dict[str, str] = {}
    boxscore_url: str | None = None
