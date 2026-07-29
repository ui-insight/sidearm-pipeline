"""Authorized workflows for immutable, scoped athletics Style Guides."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_style_steward
from app.db.engine import get_db
from app.schemas.style_guide import (
    ResolvedStyleGuideRead,
    StyleGuideActivationCreate,
    StyleGuideCreate,
    StyleGuidePreviewCreate,
    StyleGuideRetirementCreate,
    StyleGuideSuccessorCreate,
    StyleGuideVersionRead,
)
from app.services.article_style import (
    StyleGuideConflictError,
    StyleGuideNotFoundError,
    activate_style_guide,
    create_style_guide,
    create_style_guide_successor,
    list_style_guides,
    preview_resolved_style,
    read_style_guide,
    retire_style_guide,
)

router = APIRouter()


def _not_found(exc: StyleGuideNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: StyleGuideConflictError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "",
    response_model=list[StyleGuideVersionRead],
    summary="List immutable athletics Style Guide versions",
)
async def get_style_guides(
    _actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> list[StyleGuideVersionRead]:
    """Return every guide lineage and lifecycle version for stewardship review."""
    return await list_style_guides(db)


@router.get(
    "/{version_id}",
    response_model=StyleGuideVersionRead,
    summary="Read one immutable athletics Style Guide version",
)
async def get_style_guide(
    version_id: int,
    _actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> StyleGuideVersionRead:
    """Return immutable content, scope, author, and lifecycle audit metadata."""
    try:
        return await read_style_guide(db, version_id)
    except StyleGuideNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "",
    response_model=StyleGuideVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scoped athletics Style Guide draft",
)
async def post_style_guide(
    payload: StyleGuideCreate,
    actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> StyleGuideVersionRead:
    """Create version 1 with validated immutable content in a new lineage."""
    try:
        guide = await create_style_guide(db, payload, author=actor)
        await db.commit()
        return guide
    except StyleGuideConflictError as exc:
        await db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/preview",
    response_model=ResolvedStyleGuideRead,
    summary="Preview deterministic Style Guide resolution",
)
async def post_style_guide_preview(
    payload: StyleGuidePreviewCreate,
    _actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> ResolvedStyleGuideRead:
    """Resolve shared, sport, article-type, and optional channel precedence."""
    try:
        return await preview_resolved_style(db, payload)
    except StyleGuideNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/{version_id}/successors",
    response_model=StyleGuideVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an immutable Style Guide successor draft",
)
async def post_style_guide_successor(
    version_id: int,
    payload: StyleGuideSuccessorCreate,
    actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> StyleGuideVersionRead:
    """Copy reviewed content into a new version without editing the predecessor."""
    try:
        guide = await create_style_guide_successor(
            db,
            version_id,
            payload,
            author=actor,
        )
        await db.commit()
        return guide
    except StyleGuideNotFoundError as exc:
        await db.rollback()
        raise _not_found(exc) from exc
    except StyleGuideConflictError as exc:
        await db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/{version_id}/activate",
    response_model=StyleGuideVersionRead,
    summary="Validate and activate a Style Guide version",
)
async def post_style_guide_activation(
    version_id: int,
    payload: StyleGuideActivationCreate,
    actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> StyleGuideVersionRead:
    """Reject conflicts, activate the draft, and retire its active predecessor."""
    try:
        guide = await activate_style_guide(db, version_id, payload, actor=actor)
        await db.commit()
        return guide
    except StyleGuideNotFoundError as exc:
        await db.rollback()
        raise _not_found(exc) from exc
    except StyleGuideConflictError as exc:
        await db.rollback()
        raise _conflict(exc) from exc


@router.post(
    "/{version_id}/retire",
    response_model=StyleGuideVersionRead,
    summary="Retire an active Style Guide version",
)
async def post_style_guide_retirement(
    version_id: int,
    _payload: StyleGuideRetirementCreate,
    actor: str = Depends(require_style_steward),
    db: AsyncSession = Depends(get_db),
) -> StyleGuideVersionRead:
    """Retire one active version while preserving every historical snapshot."""
    try:
        guide = await retire_style_guide(db, version_id, actor=actor)
        await db.commit()
        return guide
    except StyleGuideNotFoundError as exc:
        await db.rollback()
        raise _not_found(exc) from exc
    except StyleGuideConflictError as exc:
        await db.rollback()
        raise _conflict(exc) from exc
