"""Source discovery endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, status

from app.schemas.schedule import ScheduleEventRead
from app.services.sidearm_schedule import discover_schedule_events

router = APIRouter()


@router.get(
    "/{sport_slug}/schedule",
    response_model=list[ScheduleEventRead],
    summary="Preview schedule discovery for a registered sport",
)
async def preview_schedule_discovery(sport_slug: str) -> list[ScheduleEventRead]:
    """Fetch and parse a configured Sidearm schedule without persisting events."""
    try:
        events = await discover_schedule_events(sport_slug)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm schedule: {exc}",
        ) from exc

    return [ScheduleEventRead.model_validate(event) for event in events]
