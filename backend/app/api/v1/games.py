"""Game ingestion and retrieval endpoints."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.engine import get_db
from app.models.content import GeneratedContent
from app.models.game import Game
from app.schemas.content import GeneratedContentRead
from app.schemas.game import GameDetail, GameSummary, IngestRequest
from app.services.content_generator import generate_coverage
from app.services.ingest import ingest_boxscore_url
from app.config import settings

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
    return GameDetail.model_validate(game)


@router.get(
    "",
    response_model=list[GameSummary],
    summary="List ingested games",
)
async def list_games(db: AsyncSession = Depends(get_db)) -> list[GameSummary]:
    """Return every ingested game, newest first."""
    result = await db.scalars(select(Game).order_by(Game.ingested_at.desc()))
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
    response_model=GeneratedContentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI coverage (recap + spotlight + social) for a game",
)
async def generate_game_content(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GeneratedContentRead:
    """Call the content generator and persist the result."""
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    try:
        coverage = await generate_coverage(game)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    record = GeneratedContent(
        game_id=game.id,
        headline=coverage.headline,
        recap=coverage.recap,
        spotlight_player=coverage.spotlight_player,
        spotlight_body=coverage.spotlight_body,
        social_post=coverage.social_post,
        model=settings.CONTENT_MODEL,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return GeneratedContentRead.model_validate(record)


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
        )
    )
    return await db.scalar(stmt)
