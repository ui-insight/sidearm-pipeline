"""Build historical pregame briefs without leaking post-tipoff information."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.player import Player
from app.models.player_game_stat import PlayerGameStat
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.schemas.pregame_brief import (
    BriefGameRead,
    BriefPlayerLeaderRead,
    BriefRecordRead,
    BriefTargetGameRead,
    PregameBriefRead,
)

IDAHO_NAME = "Idaho"
WBB_SLUG = "womens-basketball"


class PregameBriefNotFoundError(ValueError):
    """Raised when the requested historical matchup is unavailable."""


@dataclass(frozen=True)
class _PlayerPoint:
    player_id: int
    player_name: str
    value: Decimal
    game: Game


def _opponent(game: Game) -> str:
    if game.home_team == IDAHO_NAME:
        return game.away_team or "Unknown"
    return game.home_team or "Unknown"


def _score(game: Game) -> tuple[int, int]:
    if game.home_score is None or game.away_score is None:
        raise PregameBriefNotFoundError(
            "The selected matchup does not have a final score."
        )
    if game.home_team == IDAHO_NAME:
        return game.home_score, game.away_score
    return game.away_score, game.home_score


def _result(idaho_score: int, opponent_score: int) -> str:
    if idaho_score > opponent_score:
        return "win"
    if idaho_score < opponent_score:
        return "loss"
    return "tie"


def _game_read(game: Game) -> BriefGameRead:
    idaho_score, opponent_score = _score(game)
    return BriefGameRead(
        game_id=game.id,
        game_date=game.game_date or "",
        opponent=_opponent(game),
        venue=game.home_away_neutral or "unknown",
        idaho_score=idaho_score,
        opponent_score=opponent_score,
        result=_result(idaho_score, opponent_score),
        source_url=game.source_url,
    )


async def build_pregame_brief(
    db: AsyncSession,
    *,
    season: str,
    opponent: str,
    game_date: str,
) -> PregameBriefRead:
    """Build a brief using only final Idaho games before the target date."""
    target = await db.scalar(
        select(Game).where(
            Game.sport == WBB_SLUG,
            Game.season == season,
            Game.game_date == game_date,
            Game.event_status == "final",
            ((Game.home_team == IDAHO_NAME) & (Game.away_team == opponent))
            | ((Game.away_team == IDAHO_NAME) & (Game.home_team == opponent)),
        )
    )
    if target is None:
        raise PregameBriefNotFoundError(
            f"No final Idaho game against {opponent} was found on {game_date}."
        )

    eligible_games = list(
        await db.scalars(
            select(Game)
            .where(
                Game.sport == WBB_SLUG,
                Game.season == season,
                Game.event_status == "final",
                Game.exhibition.is_(False),
                Game.game_date < game_date,
                (Game.home_team == IDAHO_NAME) | (Game.away_team == IDAHO_NAME),
            )
            .order_by(Game.game_date, Game.id)
        )
    )
    games = [_game_read(game) for game in eligible_games]
    wins = sum(game.result == "win" for game in games)
    losses = sum(game.result == "loss" for game in games)
    ties = sum(game.result == "tie" for game in games)

    point_rows = (
        await db.execute(
            select(PlayerGameStat, Player, Game)
            .join(Player, Player.id == PlayerGameStat.player_id)
            .join(Game, Game.id == PlayerGameStat.game_id)
            .join(Team, Team.id == PlayerGameStat.team_id)
            .join(
                StatDefinition,
                StatDefinition.id == PlayerGameStat.stat_definition_id,
            )
            .where(
                Team.is_idaho.is_(True),
                StatDefinition.stat_key == "points",
                Game.sport == WBB_SLUG,
                Game.season == season,
                Game.event_status == "final",
                Game.exhibition.is_(False),
                Game.game_date < game_date,
            )
            .order_by(Game.game_date, Game.id)
        )
    ).all()
    points_by_player: dict[int, list[_PlayerPoint]] = defaultdict(list)
    for stat, player, game in point_rows:
        points_by_player[player.id].append(
            _PlayerPoint(player.id, player.display_name, stat.value, game)
        )

    leaders = []
    for player_points in points_by_player.values():
        total = sum((point.value for point in player_points), Decimal(0))
        leaders.append(
            BriefPlayerLeaderRead(
                player_id=player_points[0].player_id,
                player_name=player_points[0].player_name,
                games_played=len(player_points),
                total_points=total,
                points_per_game=(total / len(player_points)).quantize(Decimal("0.1")),
                evidence=[_game_read(point.game) for point in player_points],
            )
        )
    leaders.sort(key=lambda leader: (-leader.total_points, leader.player_name))

    target_idaho_score, target_opponent_score = _score(target)
    cutoff_date = (date.fromisoformat(game_date) - timedelta(days=1)).isoformat()
    return PregameBriefRead(
        program_name="Women's Basketball",
        season=season,
        as_of_date=cutoff_date,
        target_game=BriefTargetGameRead(
            game_id=target.id,
            game_date=game_date,
            opponent=opponent,
            venue=target.home_away_neutral or "unknown",
            source_url=target.source_url,
            idaho_score=target_idaho_score,
            opponent_score=target_opponent_score,
            result=_result(target_idaho_score, target_opponent_score),
        ),
        season_record=BriefRecordRead(
            games_played=len(games), wins=wins, losses=losses, ties=ties
        ),
        recent_form=games[-5:][::-1],
        prior_meetings=[game for game in games if game.opponent == opponent][::-1],
        scoring_leaders=leaders[:3],
        evidence_game_count=len(games),
        methodology=(
            f"Uses only final {season} games dated through {cutoff_date}; the target "
            "result is returned separately for an intentional post-brief reveal."
        ),
    )
