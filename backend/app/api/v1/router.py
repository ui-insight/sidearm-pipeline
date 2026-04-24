"""API v1 router — register all route modules here."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import games, ingest_runs, sources
from app.db.engine import get_db
from app.schemas.health import HealthResponse, ReadinessResponse

api_router = APIRouter()
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(
    ingest_runs.router,
    prefix="/ingest-runs",
    tags=["ingest-runs"],
)
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])


@api_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@api_router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> ReadinessResponse:
    """Readiness check endpoint that verifies database connectivity."""
    try:
        await db.scalar(select(1))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return ReadinessResponse(status="ready")
