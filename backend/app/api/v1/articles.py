"""Create and read evidence-bound editorial Article Briefs."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.schemas.article import ArticleBriefCreate, ArticleBriefRead
from app.services.article_brief import (
    ArticleBriefConflictError,
    ArticleBriefNotFoundError,
    create_article_brief,
    read_article_brief,
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
