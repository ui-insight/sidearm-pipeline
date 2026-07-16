"""Record Book leaderboard endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.record_book import LeaderboardScope, PointsLeaderboardRead
from app.services.record_book import build_points_leaderboard

router = APIRouter()


@router.get(
    "/leaders/points",
    response_model=PointsLeaderboardRead,
    summary="List women's basketball points leaders",
)
async def list_points_leaders(
    scope: LeaderboardScope = Query(default=LeaderboardScope.CAREER),
    season: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    limit: int = Query(default=10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> PointsLeaderboardRead:
    """Return career or season points leaders with source and coverage evidence."""
    return await build_points_leaderboard(
        db,
        scope=scope,
        season=season,
        limit=limit,
    )
