"""Create and read evidence-bound editorial Article Briefs."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.schemas.article import (
    ArticleBriefCreate,
    ArticleBriefRead,
    ArticleGenerationJobCreate,
    ArticleGenerationJobRead,
)
from app.services.article_brief import (
    ArticleBriefConflictError,
    ArticleBriefNotFoundError,
    create_article_brief,
    read_article_brief,
)
from app.services.article_generation import (
    ArticleGenerationConflictError,
    ArticleGenerationNotFoundError,
    read_article_generation_job,
    request_article_generation,
)

router = APIRouter()


def _request_username(request: Request) -> str:
    """Return middleware identity or the configured local-development identity."""
    return getattr(
        request.state,
        "authenticated_username",
        settings.PROTOTYPE_AUTH_USERNAME,
    )


@router.post(
    "",
    response_model=ArticleBriefRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an Article Brief from approved Achievement Suggestions",
)
async def post_article_brief(
    payload: ArticleBriefCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ArticleBriefRead:
    """Freeze approved single-game facts into a new evidence-bound Article Brief."""
    try:
        brief = await create_article_brief(
            db,
            payload,
            created_by=_request_username(request),
        )
        await db.commit()
        return brief
    except ArticleBriefNotFoundError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ArticleBriefConflictError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{article_id}",
    response_model=ArticleBriefRead,
    summary="Read an Article Brief and its frozen Evidence Bundle",
)
async def get_article_brief(
    article_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArticleBriefRead:
    """Return the Article Brief, source suggestions, and audit metadata."""
    try:
        return await read_article_brief(db, article_id)
    except ArticleBriefNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ArticleBriefConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/{article_id}/generation-jobs",
    response_model=ArticleGenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an evidence-bound Article Draft generation job",
)
async def post_article_generation_job(
    article_id: int,
    payload: ArticleGenerationJobCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ArticleGenerationJobRead:
    """Queue a durable writer job without changing the frozen Article Brief."""
    try:
        job = await request_article_generation(
            db,
            article_id,
            payload,
            requested_by=_request_username(request),
        )
        await db.commit()
        return job
    except ArticleGenerationNotFoundError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ArticleGenerationConflictError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{article_id}/generation-jobs/{job_id}",
    response_model=ArticleGenerationJobRead,
    summary="Read an Article Draft generation job",
)
async def get_article_generation_job(
    article_id: int,
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArticleGenerationJobRead:
    """Return durable writer status, failures, validation, and resulting version."""
    try:
        return await read_article_generation_job(db, article_id, job_id)
    except ArticleGenerationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
