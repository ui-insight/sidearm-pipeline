"""Pydantic schemas for the unresolved-player review queue."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IdentityQueueItemRead(BaseModel):
    """One inspectable unresolved-player data-quality issue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sport_program_id: int
    game_id: int | None = None
    player_id: int | None = None
    team_id: int | None = None
    source_snapshot_id: int | None = None
    status: str
    severity: str
    summary: str
    details: dict
    detected_at: datetime
    resolved_at: datetime | None = None
    resolution_notes: str | None = None


class IdentityIssueResolveRequest(BaseModel):
    """A human decision assigning an unresolved source row to a player."""

    player_id: int = Field(gt=0)
    resolution_notes: str = Field(min_length=1, max_length=2000)


class IdentityIssueResolutionRead(BaseModel):
    """The persisted result of resolving one queue item."""

    issue_id: int
    player_id: int
    match_key: str
    status: str
