"""Build historical pregame briefs without leaking post-tipoff information."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.player import Player, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.schemas.pregame_brief import (
    BriefGameRead,
    BriefLeaderGroupRead,
    BriefPlayerLeaderRead,
    BriefRecordRead,
    BriefTargetGameRead,
    PregameBriefRead,
    PreviousMatchupPlayerRead,
    PreviousMatchupTeamRead,
)
from app.services.sidearm_scraper import parse_boxscore

IDAHO_NAME = "Idaho"
WBB_SLUG = "womens-basketball"
LEADER_METRICS = (
    ("points", "Scoring", "Points created across every game before the cutoff."),
    ("assists", "Playmaking", "Made baskets directly created for teammates."),
    ("total_rebounds", "Rebounding", "Possessions finished or extended on the glass."),
    (
        "defensive_rebounds",
        "Defensive glass",
        "Opponent possessions ended with a rebound.",
    ),
    ("steals", "Ball pressure", "Live-ball takeaways recorded in the box score."),
    ("blocks", "Rim protection", "Opponent attempts turned away at the basket."),
)


class PregameBriefNotFoundError(ValueError):
    """Raised when the requested historical matchup is unavailable."""


@dataclass(frozen=True)
class _PlayerFact:
    player_id: int
    player_name: str
    jersey_number: str | None
    position: str | None
    class_year: str | None
    bio_url: str | None
    stat_key: str
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


def _leader_groups(facts: list[_PlayerFact]) -> list[BriefLeaderGroupRead]:
    by_metric_and_player: dict[tuple[str, int], list[_PlayerFact]] = defaultdict(list)
    for fact in facts:
        by_metric_and_player[(fact.stat_key, fact.player_id)].append(fact)

    groups = []
    for stat_key, label, context in LEADER_METRICS:
        leaders = []
        for (candidate_key, _), player_facts in by_metric_and_player.items():
            if candidate_key != stat_key:
                continue
            total = sum((fact.value for fact in player_facts), Decimal(0))
            player = player_facts[0]
            leaders.append(
                BriefPlayerLeaderRead(
                    player_id=player.player_id,
                    player_name=player.player_name,
                    team_name=IDAHO_NAME,
                    jersey_number=player.jersey_number,
                    position=player.position,
                    class_year=player.class_year,
                    bio_url=player.bio_url,
                    games_played=len(player_facts),
                    total=total,
                    per_game=(total / len(player_facts)).quantize(Decimal("0.1")),
                    evidence=[_game_read(fact.game) for fact in player_facts],
                )
            )
        leaders.sort(key=lambda leader: (-leader.total, leader.player_name))
        groups.append(
            BriefLeaderGroupRead(
                stat_key=stat_key,
                label=label,
                context=context,
                leaders=leaders[:3],
            )
        )
    return groups


def _integer_stat(stats: object, key: str) -> int:
    if not isinstance(stats, dict):
        return 0
    value = stats.get(key, 0)
    return value if isinstance(value, int) else 0


def _previous_matchup_teams(game: Game | None) -> list[PreviousMatchupTeamRead]:
    if game is None or not game.raw_html:
        return []
    parsed = parse_boxscore(game.source_url, game.raw_html)
    rows_by_team: dict[str, list[PreviousMatchupPlayerRead]] = defaultdict(list)
    for row in parsed.player_stat_rows:
        team_name = str(row.get("team") or "Unknown team")
        stats = row.get("stats")
        player = PreviousMatchupPlayerRead(
            team_name=team_name,
            player_name=str(row.get("player_name") or "Unknown player"),
            jersey_number=(
                str(row["jersey_number"]) if row.get("jersey_number") else None
            ),
            starter=bool(row.get("starter")),
            minutes=_integer_stat(stats, "minutes_played"),
            points=_integer_stat(stats, "points"),
            rebounds=_integer_stat(stats, "total_rebounds"),
            assists=_integer_stat(stats, "assists"),
            steals=_integer_stat(stats, "steals"),
            blocks=_integer_stat(stats, "blocks"),
        )
        if player.minutes > 0:
            rows_by_team[team_name].append(player)

    teams = []
    for team_name, players in rows_by_team.items():
        players.sort(
            key=lambda player: (
                -(player.points + player.rebounds + player.assists),
                -player.points,
                -player.minutes,
                player.player_name,
            )
        )
        teams.append(
            PreviousMatchupTeamRead(team_name=team_name, standouts=players[:3])
        )
    teams.sort(key=lambda team: team.team_name != IDAHO_NAME)
    return teams


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

    rows = (
        await db.execute(
            select(PlayerGameStat, Player, PlayerSeason, StatDefinition, Game)
            .join(Player, Player.id == PlayerGameStat.player_id)
            .join(Game, Game.id == PlayerGameStat.game_id)
            .join(Team, Team.id == PlayerGameStat.team_id)
            .join(
                StatDefinition,
                StatDefinition.id == PlayerGameStat.stat_definition_id,
            )
            .join(
                PlayerSeason,
                and_(
                    PlayerSeason.player_id == Player.id,
                    PlayerSeason.season == season,
                    PlayerSeason.sport_program_id == StatDefinition.sport_program_id,
                ),
            )
            .where(
                Team.is_idaho.is_(True),
                StatDefinition.stat_key.in_(metric[0] for metric in LEADER_METRICS),
                Game.sport == WBB_SLUG,
                Game.season == season,
                Game.event_status == "final",
                Game.exhibition.is_(False),
                Game.game_date < game_date,
            )
            .order_by(Game.game_date, Game.id)
        )
    ).all()
    facts = [
        _PlayerFact(
            player_id=player.id,
            player_name=player.display_name,
            jersey_number=roster.jersey_number,
            position=roster.position,
            class_year=roster.class_year,
            bio_url=roster.bio_url,
            stat_key=definition.stat_key,
            value=stat.value,
            game=game,
        )
        for stat, player, roster, definition, game in rows
    ]

    prior_games = [game for game in eligible_games if _opponent(game) == opponent]
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
        prior_meetings=[_game_read(game) for game in prior_games[::-1]],
        vandal_leader_groups=_leader_groups(facts),
        previous_matchup_teams=_previous_matchup_teams(
            prior_games[-1] if prior_games else None
        ),
        evidence_game_count=len(games),
        methodology=(
            f"Uses only final {season} games dated through {cutoff_date}; the target "
            "result is returned separately for an intentional post-brief reveal."
        ),
    )
