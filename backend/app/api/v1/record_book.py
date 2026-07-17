"""Record Book leaderboard endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.record_book import LeaderboardRead, LeaderboardScope, LeaderboardStat
from app.services.record_book import build_leaderboard

router = APIRouter()


@router.get(
    "/leaders/{stat_key}",
    response_model=LeaderboardRead,
    summary="List women's basketball statistical leaders",
)
async def list_leaders(
    stat_key: LeaderboardStat,
    scope: LeaderboardScope = Query(default=LeaderboardScope.CAREER),
    season: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    limit: int = Query(default=10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardRead:
    """Return career or season leaders with source and coverage evidence."""
    return await build_leaderboard(
        db,
        stat_key=stat_key,
        scope=scope,
        season=season,
        limit=limit,
    )
