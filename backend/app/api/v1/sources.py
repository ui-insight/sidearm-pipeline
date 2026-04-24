"""Source discovery endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.game import GameSummary
from app.schemas.schedule import ScheduleEventRead
from app.services.schedule_import import import_schedule_events
from app.services.sidearm_schedule import discover_schedule_events

router = APIRouter()


@router.get(
    "/{sport_slug}/schedule",
    response_model=list[ScheduleEventRead],
    summary="Preview schedule discovery for a registered sport",
)
async def preview_schedule_discovery(
    sport_slug: str,
    season: str | None = Query(
        default=None,
        description="Optional four-digit Sidearm schedule season, such as 2025.",
    ),
) -> list[ScheduleEventRead]:
    """Fetch and parse a configured Sidearm schedule without persisting events."""
    try:
        events = await discover_schedule_events(sport_slug, season=season)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm schedule: {exc}",
        ) from exc

    return [ScheduleEventRead.model_validate(event) for event in events]


@router.post(
    "/{sport_slug}/schedule/import",
    response_model=list[GameSummary],
    status_code=status.HTTP_201_CREATED,
    summary="Import discovered schedule events for a registered sport",
)
async def import_schedule_discovery(
    sport_slug: str,
    season: str | None = Query(
        default=None,
        description="Optional four-digit Sidearm schedule season, such as 2025.",
    ),
    db: AsyncSession = Depends(get_db),
) -> list[GameSummary]:
    """Fetch, parse, and persist a configured Sidearm schedule."""
    try:
        events = await discover_schedule_events(sport_slug, season=season)
        games = await import_schedule_events(db, events)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm schedule: {exc}",
        ) from exc

    return [GameSummary.model_validate(game) for game in games]
