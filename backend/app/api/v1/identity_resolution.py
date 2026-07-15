"""Player identity review-queue endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.models.data_quality_issue import DataQualityIssue
from app.models.player import Player
from app.schemas.identity_resolution import (
    IdentityCandidateRead,
    IdentityIssueCreatePlayerRequest,
    IdentityIssueResolutionRead,
    IdentityIssueResolveRequest,
    IdentityQueueItemRead,
)
from app.services.player_identity import (
    create_player_for_identity_issue,
    resolve_identity_issue,
)

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
    issues = list(
        await db.scalars(
            select(DataQualityIssue)
            .where(
                DataQualityIssue.issue_type == "unresolved_identity",
                DataQualityIssue.status == status_filter,
            )
            .order_by(DataQualityIssue.detected_at.desc(), DataQualityIssue.id.desc())
            .limit(limit)
        )
    )
    player_ids = {
        player_id
        for issue in issues
        for player_id in [issue.player_id, *_candidate_player_ids(issue.details)]
        if player_id is not None
    }
    players = {
        player.id: player
        for player in await db.scalars(select(Player).where(Player.id.in_(player_ids)))
    }

    return [
        IdentityQueueItemRead.model_validate(issue).model_copy(
            update={
                "candidate_players": [
                    IdentityCandidateRead(
                        id=player_id,
                        display_name=players[player_id].display_name,
                    )
                    for player_id in _candidate_player_ids(issue.details)
                    if player_id in players
                ],
                "resolved_player_name": (
                    players[issue.player_id].display_name
                    if issue.player_id in players
                    else None
                ),
            }
        )
        for issue in issues
    ]


def _candidate_player_ids(details: dict) -> list[int]:
    values = details.get("candidate_player_ids", [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, int)]


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


@router.post(
    "/queue/{issue_id}/create-player",
    response_model=IdentityIssueResolutionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a canonical player and resolve an unmatched identity",
)
async def create_player_from_identity_queue_item(
    issue_id: int,
    request: IdentityIssueCreatePlayerRequest,
    db: AsyncSession = Depends(get_db),
) -> IdentityIssueResolutionRead:
    """Create a canonical player from source evidence and persist the decision."""
    try:
        resolution = await create_player_for_identity_issue(
            db,
            issue_id=issue_id,
            display_name=request.display_name,
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
