"""Player identity review-queue endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.models.data_quality_issue import DataQualityIssue
from app.schemas.identity_resolution import (
    IdentityIssueResolutionRead,
    IdentityIssueResolveRequest,
    IdentityQueueItemRead,
)
from app.services.player_identity import resolve_identity_issue

router = APIRouter()
IssueStatus = Literal["open", "in_review", "resolved", "accepted_gap"]


@router.get(
    "/queue",
    response_model=list[IdentityQueueItemRead],
    summary="List unresolved-player review items",
)
async def list_identity_queue(
    status_filter: IssueStatus = Query(default="open", alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[IdentityQueueItemRead]:
    """Return identity issues for SID review, newest first."""
    issues = await db.scalars(
        select(DataQualityIssue)
        .where(
            DataQualityIssue.issue_type == "unresolved_identity",
            DataQualityIssue.status == status_filter,
        )
        .order_by(DataQualityIssue.detected_at.desc(), DataQualityIssue.id.desc())
        .limit(limit)
    )
    return [IdentityQueueItemRead.model_validate(issue) for issue in issues.all()]


@router.post(
    "/queue/{issue_id}/resolve",
    response_model=IdentityIssueResolutionRead,
    summary="Resolve an unresolved player identity",
)
async def resolve_identity_queue_item(
    issue_id: int,
    request: IdentityIssueResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> IdentityIssueResolutionRead:
    """Persist a human player assignment and reuse it for future joins."""
    try:
        resolution = await resolve_identity_issue(
            db,
            issue_id=issue_id,
            player_id=request.player_id,
            resolution_notes=request.resolution_notes,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    await db.commit()
    return IdentityIssueResolutionRead(
        issue_id=issue_id,
        player_id=resolution.player_id,
        match_key=resolution.match_key,
        status="resolved",
    )
