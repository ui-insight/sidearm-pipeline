"""Historical, evidence-backed pregame briefing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.pregame_brief import PregameBriefRead
from app.services.pregame_brief import (
    PregameBriefNotFoundError,
    build_pregame_brief,
)

router = APIRouter()


@router.get("/historical", response_model=PregameBriefRead)
async def read_historical_pregame_brief(
    season: str = Query(pattern=r"^\d{4}-\d{2}$"),
    opponent: str = Query(min_length=1, max_length=255),
    game_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> PregameBriefRead:
    """Return a briefing frozen immediately before one completed matchup."""
    try:
        return await build_pregame_brief(
            db, season=season, opponent=opponent, game_date=game_date
        )
    except PregameBriefNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
