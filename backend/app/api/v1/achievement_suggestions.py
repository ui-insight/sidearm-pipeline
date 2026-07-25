"""Read and AI-rank verified Achievement Suggestions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.models.achievement import AchievementSuggestion
from app.models.game import Game
from app.models.player import Player
from app.models.stat_definition import StatDefinition
from app.schemas.achievement import AchievementRankingRead, AchievementSuggestionRead
from app.services.achievement_ai import (
    AchievementAIError,
    NoVerifiedAchievementSuggestionsError,
    rank_and_phrase_achievement_suggestions,
)

router = APIRouter()


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
) -> list[AchievementSuggestionRead]:
    statement = (
        select(AchievementSuggestion, Player, StatDefinition)
        .join(Player, Player.id == AchievementSuggestion.player_id)
        .join(
            StatDefinition,
            StatDefinition.id == AchievementSuggestion.stat_definition_id,
        )
        .where(AchievementSuggestion.game_id == game_id)
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
            state=suggestion.state,
        )
        for suggestion, player, definition in rows
    ]
