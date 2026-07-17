"""Human-authored SQLAlchemy queries for the curated semantic layer."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import IDAHO_TEAM_SLUG, WBB_PROGRAM_SLUG
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, SourceSnapshot
from app.models.player import Player, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.schemas.semantic_query import (
    ConferenceScope,
    PlayerCareerTotalQuery,
    PlayerCareerTotalQueryResult,
    PlayerCareerTotalRead,
    PlayerGameSplitQuery,
    PlayerGameSplitQueryResult,
    PlayerGameSplitRead,
    SemanticCoverageRead,
    SemanticGameEvidenceRead,
    SemanticQueryCatalogRead,
    SemanticQueryDefinitionRead,
    SemanticQueryId,
    SemanticQueryRequest,
    SemanticQueryResult,
    SemanticSeasonEvidenceRead,
    StatLeadersQuery,
    StatLeadersQueryResult,
    TeamSeasonRecordGameRead,
    TeamSeasonRecordQuery,
    TeamSeasonRecordQueryResult,
    TeamSeasonRecordRead,
    VenueScope,
)
from app.services.record_book import (
    DEFAULT_PROGRAM_NAME,
    SUPPORTED_AGGREGATION_METHODS,
    SUPPORTED_COMPARISON_DIRECTIONS,
    RecordBookMetricNotFoundError,
    build_leaderboard,
)


class SemanticQueryEntityNotFoundError(ValueError):
    """Raised when a typed query names an unavailable player or program."""


def get_semantic_query_catalog() -> SemanticQueryCatalogRead:
    """Return the bounded, typed set of WBB questions the service can answer."""
    return SemanticQueryCatalogRead(
        program_slug=WBB_PROGRAM_SLUG,
        program_name=DEFAULT_PROGRAM_NAME,
        queries=[
            SemanticQueryDefinitionRead(
                query_id=SemanticQueryId.TEAM_SEASON_RECORD,
                display_name="Team season record",
                description=(
                    "Count Idaho wins, losses, and ties from final WBB game facts."
                ),
                question_templates=[
                    "What was Idaho's record in {season}?",
                    "What was Idaho's conference record in {season}?",
                ],
                parameter_schema=TeamSeasonRecordQuery.model_json_schema(),
            ),
            SemanticQueryDefinitionRead(
                query_id=SemanticQueryId.STAT_LEADERS,
                display_name="Statistical leaders",
                description=(
                    "Rank players for an eligible metric at career or season scope."
                ),
                question_templates=[
                    "Who leads Idaho in {stat_key} for {season}?",
                    "Who are Idaho's career leaders in {stat_key}?",
                ],
                parameter_schema=StatLeadersQuery.model_json_schema(),
            ),
            SemanticQueryDefinitionRead(
                query_id=SemanticQueryId.PLAYER_CAREER_TOTAL,
                display_name="Player career total",
                description=(
                    "Aggregate one player's authoritative season facts for a metric."
                ),
                question_templates=[
                    "What is {player_id}'s career total for {stat_key}?",
                ],
                parameter_schema=PlayerCareerTotalQuery.model_json_schema(),
            ),
            SemanticQueryDefinitionRead(
                query_id=SemanticQueryId.PLAYER_GAME_SPLIT,
                display_name="Player game split",
                description=(
                    "Aggregate one player's game facts by season, conference, and "
                    "venue."
                ),
                question_templates=[
                    "How many {stat_key} did {player_id} have in conference games?",
                    "What was {player_id}'s {stat_key} total at home in {season}?",
                ],
                parameter_schema=PlayerGameSplitQuery.model_json_schema(),
            ),
        ],
    )


async def execute_semantic_query(
    db: AsyncSession,
    request: SemanticQueryRequest,
) -> SemanticQueryResult:
    """Execute exactly one vetted query selected by its typed request model."""
    if isinstance(request, TeamSeasonRecordQuery):
        return TeamSeasonRecordQueryResult(
            result=await _team_season_record(db, request)
        )
    if isinstance(request, StatLeadersQuery):
        return StatLeadersQueryResult(
            result=await build_leaderboard(
                db,
                stat_key=request.stat_key,
                scope=request.scope,
                season=request.season,
                limit=request.limit,
            )
        )
    if isinstance(request, PlayerCareerTotalQuery):
        return PlayerCareerTotalQueryResult(
            result=await _player_career_total(db, request)
        )
    return PlayerGameSplitQueryResult(result=await _player_game_split(db, request))


async def _program_and_idaho_team(
    db: AsyncSession,
) -> tuple[SportProgram, Team]:
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    idaho = await db.scalar(select(Team).where(Team.slug == IDAHO_TEAM_SLUG))
    if program is None or idaho is None:
        raise SemanticQueryEntityNotFoundError(
            "Women's basketball warehouse reference data is not available."
        )
    return program, idaho


async def _metric_definition(
    db: AsyncSession,
    *,
    program_id: int,
    stat_key: str,
) -> StatDefinition:
    definition = await db.scalar(
        select(StatDefinition).where(
            StatDefinition.sport_program_id == program_id,
            StatDefinition.stat_key == stat_key,
            StatDefinition.entity_scope == "player",
            StatDefinition.record_book_eligible.is_(True),
            StatDefinition.aggregation_method.in_(SUPPORTED_AGGREGATION_METHODS),
            StatDefinition.comparison_direction.in_(SUPPORTED_COMPARISON_DIRECTIONS),
        )
    )
    if definition is None:
        raise RecordBookMetricNotFoundError(
            f"Record Book metric '{stat_key}' is not available."
        )
    return definition


async def _player_in_program(
    db: AsyncSession,
    *,
    player_id: int,
    program_id: int,
) -> Player:
    player = await db.scalar(
        select(Player)
        .join(PlayerSeason, PlayerSeason.player_id == Player.id)
        .where(
            Player.id == player_id,
            PlayerSeason.sport_program_id == program_id,
        )
        .limit(1)
    )
    if player is None:
        raise SemanticQueryEntityNotFoundError(
            f"Women's basketball player '{player_id}' is not available."
        )
    return player


def _idaho_game_expressions(idaho_name: str):
    idaho_is_home = or_(
        Game.home_away_neutral == "home",
        func.lower(Game.home_team) == idaho_name.lower(),
    )
    idaho_is_away = or_(
        Game.home_away_neutral == "away",
        func.lower(Game.away_team) == idaho_name.lower(),
    )
    idaho_score = case(
        (Game.home_away_neutral == "home", Game.home_score),
        (Game.home_away_neutral == "away", Game.away_score),
        (idaho_is_home, Game.home_score),
        (idaho_is_away, Game.away_score),
        else_=None,
    )
    opponent_score = case(
        (Game.home_away_neutral == "home", Game.away_score),
        (Game.home_away_neutral == "away", Game.home_score),
        (idaho_is_home, Game.away_score),
        (idaho_is_away, Game.home_score),
        else_=None,
    )
    opponent = case(
        (Game.home_away_neutral == "home", Game.away_team),
        (Game.home_away_neutral == "away", Game.home_team),
        (idaho_is_home, Game.away_team),
        (idaho_is_away, Game.home_team),
        else_="Unknown opponent",
    )
    return idaho_score, opponent_score, opponent


def _apply_conference_scope(statement, scope: ConferenceScope):
    if scope == ConferenceScope.CONFERENCE:
        return statement.where(Game.conference_event.is_(True))
    if scope == ConferenceScope.NON_CONFERENCE:
        return statement.where(Game.conference_event.is_(False))
    return statement


async def _team_season_record(
    db: AsyncSession,
    request: TeamSeasonRecordQuery,
) -> TeamSeasonRecordRead:
    program, idaho = await _program_and_idaho_team(db)
    idaho_score, opponent_score, opponent = _idaho_game_expressions(
        idaho.canonical_name
    )
    result = case(
        (idaho_score > opponent_score, "win"),
        (idaho_score < opponent_score, "loss"),
        else_="tie",
    )
    statement = select(
        Game.id.label("game_id"),
        Game.game_date,
        opponent.label("opponent"),
        Game.home_away_neutral.label("venue"),
        Game.conference_event,
        idaho_score.label("idaho_score"),
        opponent_score.label("opponent_score"),
        result.label("result"),
        Game.source_url,
    ).where(
        Game.sport == program.slug,
        Game.season == request.season,
        Game.event_status == "final",
        Game.exhibition.is_(False),
        Game.home_score.is_not(None),
        Game.away_score.is_not(None),
        idaho_score.is_not(None),
        opponent_score.is_not(None),
    )
    statement = _apply_conference_scope(statement, request.conference_scope)
    game_facts = statement.subquery()
    counts = (
        await db.execute(
            select(
                func.count(game_facts.c.game_id).label("games_played"),
                func.sum(case((game_facts.c.result == "win", 1), else_=0)).label(
                    "wins"
                ),
                func.sum(case((game_facts.c.result == "loss", 1), else_=0)).label(
                    "losses"
                ),
                func.sum(case((game_facts.c.result == "tie", 1), else_=0)).label(
                    "ties"
                ),
            )
        )
    ).one()
    game_rows = (await db.execute(statement.order_by(Game.game_date, Game.id))).all()

    games = [
        TeamSeasonRecordGameRead(
            game_id=row.game_id,
            game_date=row.game_date,
            opponent=row.opponent or "Unknown opponent",
            venue=row.venue,
            conference_event=row.conference_event,
            idaho_score=row.idaho_score,
            opponent_score=row.opponent_score,
            result=row.result,
            source_url=row.source_url,
        )
        for row in game_rows
    ]
    quality_count = await _open_quality_issue_count(
        db,
        program_id=program.id,
        seasons=[request.season],
    )
    coverage = await _coverage_summary(
        db,
        program_id=program.id,
        definition_id=None,
        grain="game",
        selected_seasons=[request.season],
        subject="team record",
    )
    return TeamSeasonRecordRead(
        program_slug=program.slug,
        program_name=program.display_name,
        season=request.season,
        conference_scope=request.conference_scope,
        games_played=int(counts.games_played or 0),
        wins=int(counts.wins or 0),
        losses=int(counts.losses or 0),
        ties=int(counts.ties or 0),
        open_quality_issue_count=quality_count,
        coverage=coverage,
        games=games,
    )


def _aggregate_expression(method: str, column):
    functions = {
        "sum": func.sum,
        "maximum": func.max,
        "minimum": func.min,
        "average": func.avg,
    }
    return functions[method](column)


async def _player_career_total(
    db: AsyncSession,
    request: PlayerCareerTotalQuery,
) -> PlayerCareerTotalRead:
    program, _ = await _program_and_idaho_team(db)
    player = await _player_in_program(
        db,
        player_id=request.player_id,
        program_id=program.id,
    )
    definition = await _metric_definition(
        db,
        program_id=program.id,
        stat_key=request.stat_key,
    )
    rows = (
        await db.execute(
            select(
                PlayerSeason.season,
                PlayerSeasonStat.value,
                PlayerSeasonStat.source_snapshot_id,
                SourceSnapshot.source_url,
            )
            .select_from(PlayerSeasonStat)
            .join(
                PlayerSeason,
                PlayerSeason.id == PlayerSeasonStat.player_season_id,
            )
            .outerjoin(
                SourceSnapshot,
                SourceSnapshot.id == PlayerSeasonStat.source_snapshot_id,
            )
            .where(
                PlayerSeason.player_id == player.id,
                PlayerSeason.sport_program_id == program.id,
                PlayerSeasonStat.stat_definition_id == definition.id,
            )
            .order_by(PlayerSeason.season.desc())
        )
    ).all()
    aggregate = (
        await db.execute(
            select(
                _aggregate_expression(
                    definition.aggregation_method,
                    PlayerSeasonStat.value,
                ).label("total"),
                func.count(func.distinct(PlayerSeason.season)).label("seasons_count"),
            )
            .select_from(PlayerSeasonStat)
            .join(
                PlayerSeason,
                PlayerSeason.id == PlayerSeasonStat.player_season_id,
            )
            .where(
                PlayerSeason.player_id == player.id,
                PlayerSeason.sport_program_id == program.id,
                PlayerSeasonStat.stat_definition_id == definition.id,
            )
        )
    ).one()
    seasons = [row.season for row in rows]
    quality_count = await _open_quality_issue_count(
        db,
        program_id=program.id,
        seasons=seasons,
        definition_id=definition.id,
        player_id=player.id,
    )
    coverage = await _coverage_summary(
        db,
        program_id=program.id,
        definition_id=definition.id,
        grain="season",
        selected_seasons=seasons,
        subject=f"{definition.display_label.lower()} career total",
        bounded_career_claim=True,
    )
    return PlayerCareerTotalRead(
        program_slug=program.slug,
        program_name=program.display_name,
        player_id=player.id,
        player_name=player.display_name,
        stat_key=definition.stat_key,
        stat_label=definition.display_label,
        aggregation_method=definition.aggregation_method,
        total=Decimal(aggregate.total) if aggregate.total is not None else None,
        seasons_count=int(aggregate.seasons_count or 0),
        open_quality_issue_count=quality_count,
        coverage=coverage,
        season_breakdown=[
            SemanticSeasonEvidenceRead(
                season=row.season,
                value=row.value,
                source_snapshot_id=row.source_snapshot_id,
                source_url=row.source_url,
            )
            for row in rows
        ],
    )


async def _player_game_split(
    db: AsyncSession,
    request: PlayerGameSplitQuery,
) -> PlayerGameSplitRead:
    program, idaho = await _program_and_idaho_team(db)
    player = await _player_in_program(
        db,
        player_id=request.player_id,
        program_id=program.id,
    )
    definition = await _metric_definition(
        db,
        program_id=program.id,
        stat_key=request.stat_key,
    )
    _, _, opponent = _idaho_game_expressions(idaho.canonical_name)
    filters = [
        PlayerGameStat.player_id == player.id,
        PlayerGameStat.team_id == idaho.id,
        PlayerGameStat.stat_definition_id == definition.id,
        Game.sport == program.slug,
        Game.event_status == "final",
        Game.exhibition.is_(False),
    ]
    if request.season is not None:
        filters.append(Game.season == request.season)
    if request.conference_scope == ConferenceScope.CONFERENCE:
        filters.append(Game.conference_event.is_(True))
    elif request.conference_scope == ConferenceScope.NON_CONFERENCE:
        filters.append(Game.conference_event.is_(False))
    if request.venue_scope != VenueScope.ALL:
        filters.append(Game.home_away_neutral == request.venue_scope.value)

    rows = (
        await db.execute(
            select(
                Game.id.label("game_id"),
                Game.game_date,
                Game.season,
                opponent.label("opponent"),
                Game.home_away_neutral.label("venue"),
                Game.conference_event,
                PlayerGameStat.value,
                PlayerGameStat.source_snapshot_id,
                SourceSnapshot.source_url,
            )
            .select_from(PlayerGameStat)
            .join(Game, Game.id == PlayerGameStat.game_id)
            .outerjoin(
                SourceSnapshot,
                SourceSnapshot.id == PlayerGameStat.source_snapshot_id,
            )
            .where(*filters)
            .order_by(Game.game_date, Game.id)
        )
    ).all()
    aggregate = (
        await db.execute(
            select(
                _aggregate_expression(
                    definition.aggregation_method,
                    PlayerGameStat.value,
                ).label("value"),
                func.count(func.distinct(Game.id)).label("games_count"),
            )
            .select_from(PlayerGameStat)
            .join(Game, Game.id == PlayerGameStat.game_id)
            .where(*filters)
        )
    ).one()
    observed_seasons = sorted({row.season for row in rows if row.season})
    selected_seasons = (
        [request.season] if request.season is not None else observed_seasons
    )
    quality_count = await _open_quality_issue_count(
        db,
        program_id=program.id,
        seasons=selected_seasons,
        definition_id=definition.id,
        player_id=player.id,
    )
    coverage = await _coverage_summary(
        db,
        program_id=program.id,
        definition_id=definition.id,
        grain="game",
        selected_seasons=selected_seasons,
        subject=f"{definition.display_label.lower()} game split",
    )
    return PlayerGameSplitRead(
        program_slug=program.slug,
        program_name=program.display_name,
        player_id=player.id,
        player_name=player.display_name,
        stat_key=definition.stat_key,
        stat_label=definition.display_label,
        aggregation_method=definition.aggregation_method,
        season=request.season,
        conference_scope=request.conference_scope,
        venue_scope=request.venue_scope,
        value=Decimal(aggregate.value) if aggregate.value is not None else None,
        games_count=int(aggregate.games_count or 0),
        open_quality_issue_count=quality_count,
        coverage=coverage,
        games=[
            SemanticGameEvidenceRead(
                game_id=row.game_id,
                game_date=row.game_date,
                season=row.season,
                opponent=row.opponent or "Unknown opponent",
                venue=row.venue,
                conference_event=row.conference_event,
                value=row.value,
                source_snapshot_id=row.source_snapshot_id,
                source_url=row.source_url,
            )
            for row in rows
        ],
    )


async def _coverage_summary(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int | None,
    grain: str,
    selected_seasons: Sequence[str],
    subject: str,
    bounded_career_claim: bool = False,
) -> SemanticCoverageRead:
    definition_filter = (
        CoverageWindow.stat_definition_id.is_(None)
        if definition_id is None
        else or_(
            CoverageWindow.stat_definition_id == definition_id,
            CoverageWindow.stat_definition_id.is_(None),
        )
    )
    windows = list(
        await db.scalars(
            select(CoverageWindow).where(
                CoverageWindow.sport_program_id == program_id,
                CoverageWindow.grain == grain,
                definition_filter,
            )
        )
    )
    first_season = min(selected_seasons) if selected_seasons else None
    last_season = max(selected_seasons) if selected_seasons else None
    complete_seasons = {
        season
        for season in selected_seasons
        if any(
            window.completeness == "complete"
            and window.first_season is not None
            and window.last_season is not None
            and window.first_season <= season <= window.last_season
            for window in windows
        )
    }
    if not windows:
        completeness = "unknown"
    elif selected_seasons and len(complete_seasons) == len(set(selected_seasons)):
        completeness = "complete"
    else:
        completeness = "partial"
    limitations = sorted(
        {
            window.known_limitations.strip()
            for window in windows
            if window.known_limitations and window.known_limitations.strip()
        }
    )
    verified_values = [window.verified_at for window in windows if window.verified_at]
    verified_at = max(verified_values) if verified_values else None
    source_systems = sorted({window.source_system for window in windows})
    return SemanticCoverageRead(
        grain=grain,
        first_season=first_season,
        last_season=last_season,
        completeness=completeness,
        source_systems=source_systems,
        known_limitations=limitations,
        verified_at=verified_at,
        statement=_coverage_statement(
            subject=subject,
            grain=grain,
            first_season=first_season,
            last_season=last_season,
            completeness=completeness,
            bounded_career_claim=bounded_career_claim,
        ),
    )


def _coverage_statement(
    *,
    subject: str,
    grain: str,
    first_season: str | None,
    last_season: str | None,
    completeness: str,
    bounded_career_claim: bool,
) -> str:
    if first_season is None or last_season is None:
        return f"No verified coverage is available for this {subject}."
    season_range = (
        first_season
        if first_season == last_season
        else f"{first_season} through {last_season}"
    )
    if completeness == "complete":
        statement = f"Verified {grain}-grain sources cover {season_range}."
    else:
        statement = (
            f"{grain.capitalize()}-grain sources cover {season_range} with known "
            "or unverified gaps."
        )
    if bounded_career_claim:
        statement += " The career total reflects this window, not all-time history."
    return statement


async def _open_quality_issue_count(
    db: AsyncSession,
    *,
    program_id: int,
    seasons: Sequence[str],
    definition_id: int | None = None,
    player_id: int | None = None,
) -> int:
    statement = (
        select(func.count(DataQualityIssue.id))
        .outerjoin(Game, Game.id == DataQualityIssue.game_id)
        .where(
            DataQualityIssue.sport_program_id == program_id,
            DataQualityIssue.status.in_(("open", "in_review")),
        )
    )
    if seasons:
        statement = statement.where(
            or_(
                Game.season.in_(seasons),
                DataQualityIssue.details["season"].as_string().in_(seasons),
            )
        )
    if definition_id is not None:
        statement = statement.where(
            or_(
                DataQualityIssue.stat_definition_id == definition_id,
                DataQualityIssue.stat_definition_id.is_(None),
            )
        )
    if player_id is not None:
        statement = statement.where(
            or_(
                DataQualityIssue.player_id == player_id,
                DataQualityIssue.player_id.is_(None),
            )
        )
    return int(await db.scalar(statement) or 0)
