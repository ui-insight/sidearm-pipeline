"""Read, AI-rank, and review verified Achievement Suggestions."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.models.achievement import AchievementSuggestion
from app.models.coverage_window import CoverageWindow
from app.models.game import Game, SourceSnapshot
from app.models.player import Player
from app.models.stat_definition import StatDefinition
from app.schemas.achievement import (
    AchievementRankingRead,
    AchievementReviewGameRead,
    AchievementReviewQueueRead,
    AchievementSuggestionRead,
    AchievementVerdictRequest,
)
from app.services.achievement_ai import (
    AchievementAIError,
    NoVerifiedAchievementSuggestionsError,
    rank_and_phrase_achievement_suggestions,
)
from app.services.article_brief import achievement_fact_hash
from app.services.article_revalidation import detect_article_evidence_drift

router = APIRouter()
ReviewState = Literal["pending", "approved", "rejected"]


def _request_username(request: Request) -> str:
    """Return middleware identity or the configured local-development identity."""
    return getattr(
        request.state,
        "authenticated_username",
        settings.PROTOTYPE_AUTH_USERNAME,
    )


@router.get(
    "/review-queue",
    response_model=AchievementReviewQueueRead,
    summary="List the SID Achievement Suggestion review queue",
)
async def list_achievement_review_queue(
    state_filter: ReviewState = Query(default="pending", alias="state"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AchievementReviewQueueRead:
    """Return games with suggestions in one verdict state plus queue totals."""
    state_counts = dict(
        (
            row_state,
            int(count),
        )
        for row_state, count in (
            await db.execute(
                select(
                    AchievementSuggestion.state,
                    func.count(AchievementSuggestion.id),
                )
                .where(
                    AchievementSuggestion.ai_rank.is_not(None),
                    AchievementSuggestion.phrasing.is_not(None),
                )
                .group_by(AchievementSuggestion.state)
            )
        ).all()
    )
    total_games = int(
        await db.scalar(
            select(func.count(func.distinct(AchievementSuggestion.game_id))).where(
                AchievementSuggestion.state == state_filter,
                AchievementSuggestion.ai_rank.is_not(None),
                AchievementSuggestion.phrasing.is_not(None),
            )
        )
        or 0
    )
    game_ids = list(
        await db.scalars(
            select(Game.id)
            .join(
                AchievementSuggestion,
                AchievementSuggestion.game_id == Game.id,
            )
            .where(
                AchievementSuggestion.state == state_filter,
                AchievementSuggestion.ai_rank.is_not(None),
                AchievementSuggestion.phrasing.is_not(None),
            )
            .group_by(Game.id, Game.start_at, Game.game_date)
            .order_by(
                Game.start_at.desc().nulls_last(),
                Game.game_date.desc().nulls_last(),
                Game.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )
    games = {
        game.id: game
        for game in await db.scalars(select(Game).where(Game.id.in_(game_ids)))
    }
    suggestions_by_game = {
        game_id: await _suggestion_reads(
            db,
            game_id=game_id,
            state_filter=state_filter,
        )
        for game_id in game_ids
    }
    return AchievementReviewQueueRead(
        items=[
            AchievementReviewGameRead(
                game_id=game.id,
                title=game.title,
                game_date=game.game_date,
                season=game.season,
                home_team=game.home_team,
                away_team=game.away_team,
                home_score=game.home_score,
                away_score=game.away_score,
                source_url=game.source_url,
                suggestions=suggestions_by_game[game.id],
            )
            for game_id in game_ids
            if (game := games.get(game_id)) is not None
        ],
        total_games=total_games,
        pending_count=state_counts.get("pending", 0),
        approved_count=state_counts.get("approved", 0),
        rejected_count=state_counts.get("rejected", 0),
    )


@router.patch(
    "/{suggestion_id}/verdict",
    response_model=AchievementSuggestionRead,
    summary="Record a SID verdict for an Achievement Suggestion",
)
async def record_achievement_verdict(
    suggestion_id: int,
    payload: AchievementVerdictRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AchievementSuggestionRead:
    """Persist approval or rejection for editorial gating and future tuning."""
    suggestion = await db.get(AchievementSuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement Suggestion not found.",
        )
    suggestion.state = payload.state
    suggestion.reviewed_at = datetime.now(UTC)
    suggestion.reviewed_by = _request_username(request)
    source = (
        await db.get(SourceSnapshot, suggestion.source_snapshot_id)
        if suggestion.source_snapshot_id is not None
        else None
    )
    coverage = (
        await db.get(CoverageWindow, suggestion.coverage_window_id)
        if suggestion.coverage_window_id is not None
        else None
    )
    game = await db.get(Game, suggestion.game_id)
    suggestion.reviewed_fact_hash = achievement_fact_hash(
        suggestion,
        game=game,
        source=source,
        coverage=coverage,
    )
    if game is not None:
        await detect_article_evidence_drift(db, game=game)
    await db.commit()
    rows = await _suggestion_reads(db, game_id=suggestion.game_id)
    return next(row for row in rows if row.id == suggestion_id)


@router.get(
    "/games/{game_id}",
    response_model=list[AchievementSuggestionRead],
    summary="List Achievement Suggestions for a game",
)
async def list_game_achievement_suggestions(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[AchievementSuggestionRead]:
    """Return deterministic facts plus any validated AI rank and phrasing."""
    if await db.get(Game, game_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found.",
        )
    return await _suggestion_reads(db, game_id=game_id)


@router.post(
    "/games/{game_id}/rank",
    response_model=AchievementRankingRead,
    summary="AI-rank and phrase verified Achievement Suggestions",
)
async def rank_game_achievement_suggestions(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> AchievementRankingRead:
    """Rank source-backed candidates and persist only fact-preserving phrasing."""
    try:
        result = await rank_and_phrase_achievement_suggestions(db, game_id=game_id)
        await db.commit()
    except NoVerifiedAchievementSuggestionsError as exc:
        await db.rollback()
        status_code = (
            status.HTTP_404_NOT_FOUND
            if str(exc) == "Game not found."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except AchievementAIError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return AchievementRankingRead(
        game_id=game_id,
        model=result.model,
        prompt_version=result.prompt_version,
        suggestions=await _suggestion_reads(db, game_id=game_id, ai_ranked_only=True),
    )


async def _suggestion_reads(
    db: AsyncSession,
    *,
    game_id: int,
    ai_ranked_only: bool = False,
    state_filter: ReviewState | None = None,
) -> list[AchievementSuggestionRead]:
    statement = (
        select(AchievementSuggestion, Player, StatDefinition, SourceSnapshot)
        .join(Player, Player.id == AchievementSuggestion.player_id)
        .join(
            StatDefinition,
            StatDefinition.id == AchievementSuggestion.stat_definition_id,
        )
        .outerjoin(
            SourceSnapshot,
            SourceSnapshot.id == AchievementSuggestion.source_snapshot_id,
        )
        .where(AchievementSuggestion.game_id == game_id)
    )
    if state_filter is not None:
        statement = statement.where(
            AchievementSuggestion.state == state_filter,
            AchievementSuggestion.ai_rank.is_not(None),
            AchievementSuggestion.phrasing.is_not(None),
        )
    if ai_ranked_only:
        statement = statement.where(
            AchievementSuggestion.ai_rank.is_not(None),
            AchievementSuggestion.state == "pending",
        )
    rows = (
        await db.execute(
            statement.order_by(
                AchievementSuggestion.ai_rank.asc().nulls_last(),
                AchievementSuggestion.notability_score.desc(),
                AchievementSuggestion.suggestion_key,
            )
        )
    ).all()
    return [
        AchievementSuggestionRead(
            id=suggestion.id,
            game_id=suggestion.game_id,
            player_id=suggestion.player_id,
            player_name=player.display_name,
            stat_key=definition.stat_key,
            stat_label=definition.display_label,
            suggestion_key=suggestion.suggestion_key,
            achievement_type=suggestion.achievement_type,
            scope=suggestion.scope,
            computed_value=suggestion.computed_value,
            comparison_value=suggestion.comparison_value,
            rank=suggestion.rank,
            deterministic_notability_score=suggestion.notability_score,
            context=suggestion.context,
            coverage_context=suggestion.coverage_context,
            phrasing=suggestion.phrasing,
            ai_rank=suggestion.ai_rank,
            ai_model=suggestion.ai_model,
            ai_prompt_version=suggestion.ai_prompt_version,
            ai_output_hash=suggestion.ai_output_hash,
            ai_ranked_at=suggestion.ai_ranked_at,
            source_url=snapshot.source_url if snapshot is not None else None,
            reviewed_at=suggestion.reviewed_at,
            reviewed_by=suggestion.reviewed_by,
            reviewed_fact_hash=suggestion.reviewed_fact_hash,
            state=suggestion.state,
        )
        for suggestion, player, definition, snapshot in rows
    ]
