"""Pydantic schemas for the unresolved-player review queue."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CanonicalPlayerName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ResolutionNotes = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
]


class IdentityCandidateRead(BaseModel):
    """One canonical player candidate attached to a review item."""

    id: int
    display_name: str


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
    candidate_players: list[IdentityCandidateRead] = []
    resolved_player_name: str | None = None


class IdentityIssueResolveRequest(BaseModel):
    """A human decision assigning an unresolved source row to a player."""

    player_id: int = Field(gt=0)
    resolution_notes: ResolutionNotes


class IdentityIssueCreatePlayerRequest(BaseModel):
    """A human decision creating a player for an unmatched source row."""

    display_name: CanonicalPlayerName
    resolution_notes: ResolutionNotes


class IdentityIssueResolutionRead(BaseModel):
    """The persisted result of resolving one queue item."""

    issue_id: int
    player_id: int
    match_key: str
    status: str
