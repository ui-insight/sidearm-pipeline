"""Game ingestion and retrieval endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.recap_writer import run_recap_writer
from app.db.engine import get_db
from app.models.game import Game
from app.models.publish_event import PublishEvent
from app.schemas.agent import AgentRunRead
from app.schemas.game import GameDetail, GameSummary, IngestRequest, ValidationResult
from app.services.ingest import ingest_boxscore_url
from app.services.validation import all_passed, validate_game

router = APIRouter()


@router.post(
    "",
    response_model=GameDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a Sidearm boxscore URL",
)
async def ingest_game(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Fetch a Sidearm boxscore page, parse it, and store the structured data.

    If the same canonical event has already been ingested, the existing record
    is updated in place and a new source snapshot is retained.
    """
    try:
        game = await ingest_boxscore_url(str(payload.url), db, trigger_type="manual")
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm page: {exc}",
        ) from exc
    game = await _load_game(db, game.id)
    return GameDetail.model_validate(game)


@router.get(
    "",
    response_model=list[GameSummary],
    summary="List ingested games",
)
async def list_games(
    publish_status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[GameSummary]:
    """Return ingested games, newest first. Optionally filter by publish_status."""
    stmt = select(Game).order_by(Game.ingested_at.desc())
    if publish_status is not None:
        stmt = stmt.where(Game.publish_status == publish_status)
    result = await db.scalars(stmt)
    return [GameSummary.model_validate(row) for row in result.all()]


@router.get(
    "/{game_id}",
    response_model=GameDetail,
    summary="Get a single game with full boxscore",
)
async def get_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Return one game plus its team stats, player stats, and scoring plays."""
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )
    return GameDetail.model_validate(game)


@router.post(
    "/{game_id}/ingest",
    response_model=GameDetail,
    summary="Re-ingest a game from its stored boxscore source URL",
)
async def reingest_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Re-run ingestion for an existing game using its stored source URL.

    Useful when a scheduled ingest failed, when Sidearm data was corrected,
    or when an operator needs to force a fresh snapshot. Records a new
    ``IngestRun`` with ``trigger_type="manual_rerun"``.
    """
    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    try:
        game = await ingest_boxscore_url(
            game.source_url, db, trigger_type="manual_rerun"
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm page: {exc}",
        ) from exc

    game = await _load_game(db, game.id)
    return GameDetail.model_validate(game)


@router.post(
    "/{game_id}/validate",
    response_model=ValidationResult,
    summary="Validate a game for publication readiness",
)
async def validate_game_endpoint(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> ValidationResult:
    """Run sport-specific validation rules against a game.

    Sets publish_status to "validated" when all checks pass, or "errored" when
    any check fails. Records a PublishEvent audit entry for the transition.
    """
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    checks = validate_game(game)
    passed = all_passed(checks)
    new_status = "validated" if passed else "errored"
    now = datetime.now(tz=UTC)
    checks_payload = [
        {"rule": c.rule, "passed": c.passed, "detail": c.detail} for c in checks
    ]

    event = PublishEvent(
        game_id=game.id,
        from_status=game.publish_status,
        to_status=new_status,
        trigger="api",
        detail={"checks": checks_payload},
    )
    db.add(event)

    game.publish_status = new_status
    game.last_validated_at = now
    game.validation_detail = {"checks": checks_payload}

    await db.commit()

    return ValidationResult(
        game_id=game.id,
        passed=passed,
        publish_status=new_status,
        checks=checks,
        validated_at=now,
    )


@router.post(
    "/{game_id}/publish",
    response_model=GameDetail,
    summary="Publish a validated game",
)
async def publish_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Transition a validated game to published status.

    Requires publish_status == "validated". Re-runs validation as a safety check
    before setting the status to "published". Returns 409 if the game is not
    validated or if the safety check fails.
    """
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    if game.publish_status != "validated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Game must be in 'validated' status to publish; "
                f"current status is '{game.publish_status}'"
            ),
        )

    checks = validate_game(game)
    if not all_passed(checks):
        now = datetime.now(tz=UTC)
        checks_payload = [
            {"rule": c.rule, "passed": c.passed, "detail": c.detail} for c in checks
        ]
        event = PublishEvent(
            game_id=game.id,
            from_status=game.publish_status,
            to_status="errored",
            trigger="api",
            detail={"reason": "safety_check_failed", "checks": checks_payload},
        )
        db.add(event)
        game.publish_status = "errored"
        game.last_validated_at = now
        game.validation_detail = {"checks": checks_payload}
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validation safety check failed; game moved to 'errored'",
        )

    event = PublishEvent(
        game_id=game.id,
        from_status="validated",
        to_status="published",
        trigger="api",
        detail={},
    )
    db.add(event)
    game.publish_status = "published"
    await db.commit()

    game = await _load_game(db, game_id)
    return GameDetail.model_validate(game)


@router.delete(
    "/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an ingested game",
)
async def delete_game(game_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a game and all associated records."""
    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )
    await db.delete(game)
    await db.commit()


@router.post(
    "/{game_id}/generate",
    response_model=AgentRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI coverage (recap + spotlight + social) for a game",
)
async def generate_game_content(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    """Run the recap-writer agent for a game and return the AgentRun.

    **Breaking change from previous API**: this endpoint now returns
    ``AgentRunRead`` instead of ``GeneratedContentRead``. The content is not
    persisted until a human approves it via
    ``POST /api/v1/agent-runs/{id}/verdict``.

    This is the Tier-1 (human-gated) pattern per ADR-003.
    """
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    try:
        agent_run = await run_recap_writer(game, db, trigger="manual")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    from app.models.agent import AgentRun as AgentRunModel

    stmt = (
        select(AgentRunModel)
        .where(AgentRunModel.id == agent_run.id)
        .options(
            selectinload(AgentRunModel.steps),
            selectinload(AgentRunModel.evaluations),
        )
    )
    loaded_run = await db.scalar(stmt)
    return AgentRunRead.model_validate(loaded_run)


async def _load_game(db: AsyncSession, game_id: int) -> Game | None:
    stmt = (
        select(Game)
        .where(Game.id == game_id)
        .options(
            selectinload(Game.team_stats),
            selectinload(Game.player_stats),
            selectinload(Game.scoring_plays),
            selectinload(Game.event_sources),
            selectinload(Game.source_snapshots),
            selectinload(Game.status_history),
            selectinload(Game.generated_content),
            selectinload(Game.agent_runs),
            selectinload(Game.publish_events),
        )
    )
    return await db.scalar(stmt)
