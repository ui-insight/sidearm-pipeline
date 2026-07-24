"""Evidence-backed queries for the SID-facing Record Book."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import WBB_PROGRAM_SLUG
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import SourceSnapshot
from app.models.player import Player, PlayerSeason
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.schemas.record_book import (
    LeaderboardLeaderRead,
    LeaderboardRead,
    LeaderboardScope,
    LeaderSeasonEvidenceRead,
    RecordBookCoverageRead,
    RecordBookMetricCatalogRead,
    RecordBookMetricRead,
)

DEFAULT_PROGRAM_NAME = "Women's Basketball"
SUPPORTED_AGGREGATION_METHODS = ("sum", "maximum", "minimum", "average")
SUPPORTED_COMPARISON_DIRECTIONS = ("higher", "lower")


class RecordBookMetricNotFoundError(ValueError):
    """Raised when a metric is not eligible for Record Book aggregation."""


async def list_record_book_metrics(
    db: AsyncSession,
) -> RecordBookMetricCatalogRead:
    """List aggregable WBB player metrics from their warehouse definitions."""
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    if program is None:
        return RecordBookMetricCatalogRead(
            program_slug=WBB_PROGRAM_SLUG,
            program_name=DEFAULT_PROGRAM_NAME,
            metrics=[],
        )

    definitions = list(
        await db.scalars(
            _record_book_definitions(program.id).order_by(
                StatDefinition.display_label,
                StatDefinition.stat_key,
            )
        )
    )
    return RecordBookMetricCatalogRead(
        program_slug=program.slug,
        program_name=program.display_name,
        metrics=[
            RecordBookMetricRead(
                stat_key=definition.stat_key,
                display_label=definition.display_label,
                value_type=definition.value_type,
                unit=definition.unit,
                aggregation_method=definition.aggregation_method,
                comparison_direction=definition.comparison_direction,
                display_format=definition.display_format,
            )
            for definition in definitions
        ],
    )


def _record_book_definitions(program_id: int):
    return select(StatDefinition).where(
        StatDefinition.sport_program_id == program_id,
        StatDefinition.entity_scope == "player",
        StatDefinition.record_book_eligible.is_(True),
        StatDefinition.aggregation_method.in_(SUPPORTED_AGGREGATION_METHODS),
        StatDefinition.comparison_direction.in_(SUPPORTED_COMPARISON_DIRECTIONS),
    )


async def build_leaderboard(
    db: AsyncSession,
    *,
    stat_key: str,
    scope: LeaderboardScope,
    season: str | None,
    limit: int,
) -> LeaderboardRead:
    """Build a WBB leaderboard from authoritative cumulative season facts."""
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    if program is None:
        raise RecordBookMetricNotFoundError(
            f"Record Book metric '{stat_key}' is not available."
        )

    definition = await db.scalar(
        _record_book_definitions(program.id).where(
            StatDefinition.stat_key == stat_key,
        )
    )
    if definition is None:
        raise RecordBookMetricNotFoundError(
            f"Record Book metric '{stat_key}' is not available."
        )

    available_seasons = list(
        await db.scalars(
            select(PlayerSeason.season)
            .join(
                PlayerSeasonStat,
                PlayerSeasonStat.player_season_id == PlayerSeason.id,
            )
            .where(
                PlayerSeason.sport_program_id == program.id,
                PlayerSeasonStat.stat_definition_id == definition.id,
            )
            .distinct()
            .order_by(PlayerSeason.season.desc())
        )
    )
    selected_season = season if scope == LeaderboardScope.SEASON else None
    if scope == LeaderboardScope.SEASON and selected_season is None:
        selected_season = available_seasons[0] if available_seasons else None

    rows = await _leader_rows(
        db,
        program_id=program.id,
        definition_id=definition.id,
        aggregation_method=definition.aggregation_method,
        comparison_direction=definition.comparison_direction,
        scope=scope,
        season=selected_season,
        limit=limit,
    )
    player_ids = [row.player_id for row in rows]
    evidence = await _season_evidence(
        db,
        program_id=program.id,
        definition_id=definition.id,
        player_ids=player_ids,
        season=selected_season if scope == LeaderboardScope.SEASON else None,
    )
    leaders = _rank_leaders(rows, evidence)
    total_players = await _total_players(
        db,
        program_id=program.id,
        definition_id=definition.id,
        season=selected_season if scope == LeaderboardScope.SEASON else None,
    )
    coverage = await _coverage_summary(
        db,
        program_id=program.id,
        definition_id=definition.id,
        stat_label=definition.display_label,
        scope=scope,
        selected_season=selected_season,
        available_seasons=available_seasons,
    )
    open_quality_issue_count = await _open_quality_issue_count(
        db,
        program_id=program.id,
        definition_id=definition.id,
        selected_seasons=(
            [selected_season]
            if scope == LeaderboardScope.SEASON and selected_season is not None
            else available_seasons
        ),
    )

    return LeaderboardRead(
        program_slug=program.slug,
        program_name=program.display_name,
        stat_key=definition.stat_key,
        stat_label=definition.display_label,
        scope=scope,
        season=selected_season,
        available_seasons=available_seasons,
        total_players=total_players,
        open_quality_issue_count=open_quality_issue_count,
        coverage=coverage,
        leaders=leaders,
    )


async def _leader_rows(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    aggregation_method: str,
    comparison_direction: str,
    scope: LeaderboardScope,
    season: str | None,
    limit: int,
):
    aggregate_functions = {
        "sum": func.sum,
        "maximum": func.max,
        "minimum": func.min,
        "average": func.avg,
    }
    aggregate_value = aggregate_functions[aggregation_method](
        PlayerSeasonStat.value
    ).label("total_value")
    seasons_count = func.count(func.distinct(PlayerSeason.season)).label(
        "seasons_count"
    )
    statement = (
        select(
            Player.id.label("player_id"),
            Player.display_name.label("player_name"),
            aggregate_value,
            seasons_count,
        )
        .select_from(PlayerSeasonStat)
        .join(PlayerSeason, PlayerSeason.id == PlayerSeasonStat.player_season_id)
        .join(Player, Player.id == PlayerSeason.player_id)
        .where(
            PlayerSeason.sport_program_id == program_id,
            PlayerSeasonStat.stat_definition_id == definition_id,
        )
    )
    if scope == LeaderboardScope.SEASON:
        if season is None:
            return []
        statement = statement.where(PlayerSeason.season == season)
    statement = (
        statement.group_by(Player.id, Player.display_name)
        .order_by(
            aggregate_value.asc()
            if comparison_direction == "lower"
            else aggregate_value.desc(),
            Player.display_name,
            Player.id,
        )
        .limit(limit)
    )
    return (await db.execute(statement)).all()


async def _season_evidence(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    player_ids: list[int],
    season: str | None,
) -> dict[int, list[LeaderSeasonEvidenceRead]]:
    if not player_ids:
        return {}

    statement = (
        select(
            PlayerSeason.player_id,
            PlayerSeason.season,
            PlayerSeasonStat.value,
            PlayerSeasonStat.source_snapshot_id,
            SourceSnapshot.source_url,
        )
        .select_from(PlayerSeasonStat)
        .join(PlayerSeason, PlayerSeason.id == PlayerSeasonStat.player_season_id)
        .outerjoin(
            SourceSnapshot,
            SourceSnapshot.id == PlayerSeasonStat.source_snapshot_id,
        )
        .where(
            PlayerSeason.sport_program_id == program_id,
            PlayerSeasonStat.stat_definition_id == definition_id,
            PlayerSeason.player_id.in_(player_ids),
        )
        .order_by(PlayerSeason.season.desc())
    )
    if season is not None:
        statement = statement.where(PlayerSeason.season == season)

    grouped: dict[int, list[LeaderSeasonEvidenceRead]] = defaultdict(list)
    for row in (await db.execute(statement)).all():
        grouped[row.player_id].append(
            LeaderSeasonEvidenceRead(
                season=row.season,
                value=row.value,
                source_snapshot_id=row.source_snapshot_id,
                source_url=row.source_url,
            )
        )
    return dict(grouped)


def _rank_leaders(rows, evidence) -> list[LeaderboardLeaderRead]:
    leaders: list[LeaderboardLeaderRead] = []
    previous_total: Decimal | None = None
    previous_rank = 0
    for index, row in enumerate(rows, start=1):
        total = Decimal(row.total_value)
        rank = previous_rank if previous_total == total else index
        leaders.append(
            LeaderboardLeaderRead(
                rank=rank,
                player_id=row.player_id,
                player_name=row.player_name,
                total=total,
                seasons_count=row.seasons_count,
                season_breakdown=evidence.get(row.player_id, []),
            )
        )
        previous_total = total
        previous_rank = rank
    return leaders


async def _total_players(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    season: str | None,
) -> int:
    statement = (
        select(func.count(func.distinct(PlayerSeason.player_id)))
        .select_from(PlayerSeasonStat)
        .join(PlayerSeason, PlayerSeason.id == PlayerSeasonStat.player_season_id)
        .where(
            PlayerSeason.sport_program_id == program_id,
            PlayerSeasonStat.stat_definition_id == definition_id,
        )
    )
    if season is not None:
        statement = statement.where(PlayerSeason.season == season)
    return int(await db.scalar(statement) or 0)


async def _coverage_summary(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    stat_label: str,
    scope: LeaderboardScope,
    selected_season: str | None,
    available_seasons: list[str],
) -> RecordBookCoverageRead:
    statement = select(CoverageWindow).where(
        CoverageWindow.sport_program_id == program_id,
        CoverageWindow.stat_definition_id == definition_id,
        CoverageWindow.grain == "season",
    )
    if scope == LeaderboardScope.SEASON and selected_season is not None:
        statement = statement.where(
            CoverageWindow.first_season == selected_season,
            CoverageWindow.last_season == selected_season,
        )
    windows = list(await db.scalars(statement))

    selected_seasons = (
        [selected_season]
        if scope == LeaderboardScope.SEASON and selected_season is not None
        else available_seasons
    )
    first_season = min(selected_seasons) if selected_seasons else None
    last_season = max(selected_seasons) if selected_seasons else None
    covered_seasons = {
        window.first_season
        for window in windows
        if window.first_season is not None and window.first_season == window.last_season
    }
    if not windows:
        completeness = "unknown"
    elif set(selected_seasons).issubset(covered_seasons) and all(
        window.completeness == "complete" for window in windows
    ):
        completeness = "complete"
    else:
        completeness = "partial"

    verified_values = [window.verified_at for window in windows if window.verified_at]
    verified_at = max(verified_values) if verified_values else None
    limitations = sorted(
        {
            window.known_limitations.strip()
            for window in windows
            if window.known_limitations and window.known_limitations.strip()
        }
    )
    source_systems = sorted({window.source_system for window in windows})
    return RecordBookCoverageRead(
        first_season=first_season,
        last_season=last_season,
        completeness=completeness,
        source_systems=source_systems,
        known_limitations=limitations,
        verified_at=verified_at,
        statement=_coverage_statement(
            stat_label=stat_label,
            scope=scope,
            first_season=first_season,
            last_season=last_season,
            completeness=completeness,
        ),
    )


def _coverage_statement(
    *,
    stat_label: str,
    scope: LeaderboardScope,
    first_season: str | None,
    last_season: str | None,
    completeness: str,
) -> str:
    if first_season is None or last_season is None:
        return f"No verified {stat_label.lower()} coverage is available yet."
    season_range = (
        first_season
        if first_season == last_season
        else f"{first_season} through {last_season}"
    )
    if scope == LeaderboardScope.SEASON:
        if completeness == "complete":
            return f"Verified season source for {season_range}."
        return f"Partial season coverage for {season_range}; review known gaps."
    if completeness == "complete":
        return (
            f"Verified season sources cover {season_range}. Career totals reflect "
            "this window, not all-time history."
        )
    return (
        f"Season sources currently cover {season_range} with known gaps. Career "
        "totals reflect only this window."
    )


async def _open_quality_issue_count(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    selected_seasons: list[str],
) -> int:
    if not selected_seasons:
        return 0
    statement = (
        select(func.count(DataQualityIssue.id))
        .outerjoin(
            SourceSnapshot,
            SourceSnapshot.id == DataQualityIssue.source_snapshot_id,
        )
        .where(
            DataQualityIssue.sport_program_id == program_id,
            DataQualityIssue.status.in_(("open", "in_review")),
            DataQualityIssue.details["season"].as_string().in_(selected_seasons),
            or_(
                DataQualityIssue.stat_definition_id == definition_id,
                and_(
                    DataQualityIssue.stat_definition_id.is_(None),
                    SourceSnapshot.source_type == "cumulative_stats_html",
                ),
            ),
        )
    )
    return int(await db.scalar(statement) or 0)
