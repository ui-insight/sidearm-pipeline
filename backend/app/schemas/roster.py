"""Pydantic schemas for roster discovery and import."""

from pydantic import BaseModel, ConfigDict


class RosterPlayerRead(BaseModel):
    """One player discovered from a Sidearm roster page."""

    model_config = ConfigDict(from_attributes=True)

    display_name: str
    jersey_number: str | None = None
    class_year: str | None = None
    position: str | None = None
    bio_url: str | None = None
    source_player_id: str | None = None
    canonical_bio_url: str | None = None
    canonical_source_player_id: str | None = None
    identity_resolution_error: str | None = None


class RosterImportRead(BaseModel):
    """Summary of one persisted roster import."""

    model_config = ConfigDict(from_attributes=True)

    source_url: str
    season: str
    source_snapshot_id: int
    players_seen: int
    players_created: int
    identities_created: int
    player_seasons_created: int
    player_seasons_updated: int
    quality_issues_created: int
