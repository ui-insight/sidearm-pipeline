"""Source discovery endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.game import GameSummary
from app.schemas.roster import RosterImportRead, RosterPlayerRead
from app.schemas.schedule import ScheduleEventRead
from app.services.roster_import import import_roster
from app.services.schedule_import import import_schedule_events
from app.services.sidearm_roster import discover_roster
from app.services.sidearm_schedule import discover_schedule_events

router = APIRouter()


@router.get(
    "/{sport_slug}/roster",
    response_model=list[RosterPlayerRead],
    summary="Preview roster discovery for a registered sport",
)
async def preview_roster_discovery(
    sport_slug: str,
    season: str = Query(
        description="Sidearm academic roster season, such as 2025-26.",
    ),
) -> list[RosterPlayerRead]:
    """Fetch and parse a configured Sidearm roster without persisting it."""
    try:
        roster = await discover_roster(sport_slug, season)
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
            detail=f"Failed to fetch Sidearm roster: {exc}",
        ) from exc

    return [RosterPlayerRead.model_validate(player) for player in roster.players]


@router.post(
    "/{sport_slug}/roster/import",
    response_model=RosterImportRead,
    status_code=status.HTTP_201_CREATED,
    summary="Import a discovered roster into canonical player identities",
)
async def import_roster_discovery(
    sport_slug: str,
    season: str = Query(
        description="Sidearm academic roster season, such as 2025-26.",
    ),
    db: AsyncSession = Depends(get_db),
) -> RosterImportRead:
    """Fetch a Sidearm roster and persist exact identities and memberships."""
    try:
        roster = await discover_roster(sport_slug, season)
        result = await import_roster(db, roster)
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
            detail=f"Failed to fetch Sidearm roster: {exc}",
        ) from exc

    return RosterImportRead.model_validate(result)


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
