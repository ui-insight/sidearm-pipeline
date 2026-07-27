"""API v1 router — register all route modules here."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import (
    achievement_suggestions,
    articles,
    auth,
    games,
    identity_resolution,
    ingest_runs,
    pregame_briefs,
    record_book,
    semantic_queries,
    sources,
    workspace_views,
)
from app.db.engine import get_db
from app.schemas.health import HealthResponse, ReadinessResponse

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    achievement_suggestions.router,
    prefix="/achievement-suggestions",
    tags=["achievement-suggestions"],
)
api_router.include_router(articles.router, prefix="/articles", tags=["articles"])
api_router.include_router(
    record_book.router,
    prefix="/record-book",
    tags=["record-book"],
)
api_router.include_router(
    semantic_queries.router,
    prefix="/semantic-queries",
    tags=["semantic-queries"],
)
api_router.include_router(
    pregame_briefs.router,
    prefix="/pregame-briefs",
    tags=["pregame-briefs"],
)
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(
    ingest_runs.router,
    prefix="/ingest-runs",
    tags=["ingest-runs"],
)
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(
    workspace_views.router,
    prefix="/workspace-views",
    tags=["workspace-views"],
)
api_router.include_router(
    identity_resolution.router,
    prefix="/identity-resolution",
    tags=["identity-resolution"],
)


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
