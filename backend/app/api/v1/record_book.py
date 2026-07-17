"""Record Book metric catalog and leaderboard endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.record_book import (
    LeaderboardRead,
    LeaderboardScope,
    RecordBookMetricCatalogRead,
)
from app.services.record_book import (
    RecordBookMetricNotFoundError,
    build_leaderboard,
    list_record_book_metrics,
)

router = APIRouter()


@router.get(
    "/metrics",
    response_model=RecordBookMetricCatalogRead,
    summary="List women's basketball Record Book metrics",
)
async def list_metrics(
    db: AsyncSession = Depends(get_db),
) -> RecordBookMetricCatalogRead:
    """Return the eligible metric catalog defined for the WBB program."""
    return await list_record_book_metrics(db)


@router.get(
    "/leaders/{stat_key}",
    response_model=LeaderboardRead,
    summary="List women's basketball statistical leaders",
)
async def list_leaders(
    stat_key: str = Path(pattern=r"^[a-z][a-z0-9_]{0,127}$"),
    scope: LeaderboardScope = Query(default=LeaderboardScope.CAREER),
    season: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    limit: int = Query(default=10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> LeaderboardRead:
    """Return career or season leaders with source and coverage evidence."""
    try:
        return await build_leaderboard(
            db,
            stat_key=stat_key,
            scope=scope,
            season=season,
            limit=limit,
        )
    except RecordBookMetricNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
