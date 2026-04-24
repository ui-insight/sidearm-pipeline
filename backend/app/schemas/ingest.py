"""Pydantic schemas for ingest job history."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngestRunRead(BaseModel):
    """Read model for one durable ingest attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int | None = None
    trigger_type: str
    source_system: str
    source_type: str
    source_url: str
    source_event_id: str | None = None
    sport: str | None = None
    season: str | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    http_status: int | None = None
    retryable: bool = False
    error_type: str | None = None
    error_message: str | None = None
    run_metadata: dict = Field(default_factory=dict)
