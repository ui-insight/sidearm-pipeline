"""Player identity review-queue endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
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
    IdentityQueuePageRead,
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
    return await _serialize_identity_issues(db, issues)


@router.get(
    "/queue/page",
    response_model=IdentityQueuePageRead,
    summary="List a filtered page of player identity reviews",
)
async def page_identity_queue(
    status_filter: IssueStatus = Query(default="open", alias="status"),
    season: str | None = Query(default=None, min_length=1, max_length=16),
    institution: str | None = Query(default=None, min_length=1, max_length=255),
    game_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> IdentityQueuePageRead:
    """Return a totalled queue page with season and institution filter facets."""
    base_filters = (
        DataQualityIssue.issue_type == "unresolved_identity",
        DataQualityIssue.status == status_filter,
    )
    season_value = DataQualityIssue.details["season"].as_string()
    institution_value = DataQualityIssue.details["institution"].as_string()
    filters = list(base_filters)
    if season is not None:
        filters.append(season_value == season)
    if institution is not None:
        filters.append(institution_value == institution)
    if game_id is not None:
        filters.append(DataQualityIssue.game_id == game_id)

    total = await db.scalar(select(func.count(DataQualityIssue.id)).where(*filters))
    issues = list(
        await db.scalars(
            select(DataQualityIssue)
            .where(*filters)
            .order_by(DataQualityIssue.detected_at.desc(), DataQualityIssue.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    available_seasons = list(
        await db.scalars(
            select(season_value)
            .where(*base_filters, season_value.is_not(None))
            .distinct()
            .order_by(season_value)
        )
    )
    available_institutions = list(
        await db.scalars(
            select(institution_value)
            .where(*base_filters, institution_value.is_not(None))
            .distinct()
            .order_by(institution_value)
        )
    )

    return IdentityQueuePageRead(
        items=await _serialize_identity_issues(db, issues),
        total=total or 0,
        limit=limit,
        offset=offset,
        available_seasons=available_seasons,
        available_institutions=available_institutions,
    )


async def _serialize_identity_issues(
    db: AsyncSession,
    issues: list[DataQualityIssue],
) -> list[IdentityQueueItemRead]:
    """Attach canonical player names to queue issue records."""
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
