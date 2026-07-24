"""Bounded historical WBB backfill with explicit coverage evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, IngestRun
from app.models.sport_program import SportProgram
from app.models.team import Team
from app.services.current_season_sync import (
    CurrentSeasonSyncResult,
    sync_current_wbb_season,
)
from app.services.season_stat_import import (
    CumulativeStatsImportResult,
    import_cumulative_stats,
    record_cumulative_parser_failure,
)
from app.services.sidearm_cumulative_stats import (
    CumulativeStatsParseError,
    discover_cumulative_stats,
)
from app.services.source_registry import get_source_registry

WBB_SPORT_SLUG = "womens-basketball"
PUBLICATION_SOURCE_SYSTEM = "govandals_public_html"


@dataclass(frozen=True)
class HistoricalSeasonCoverageResult:
    """Season-level game coverage and open trust exceptions."""

    schedule_events_seen: int
    final_games: int
    final_games_with_boxscores: int
    final_games_ingested: int
    missing_boxscores: int
    failed_boxscores: int
    open_identity_issues: int
    open_quality_issues: int
    game_completeness: str
    game_coverage_window_id: int


@dataclass(frozen=True)
class HistoricalSeasonBackfillResult:
    """Observable result for one bounded historical season workflow."""

    run_id: int
    sport_slug: str
    season: str
    status: str
    started_at: datetime
    finished_at: datetime
    game_sync: CurrentSeasonSyncResult
    season_stats_status: str
    season_stats_error: str | None
    season_stats: CumulativeStatsImportResult | None
    coverage: HistoricalSeasonCoverageResult


async def backfill_historical_wbb_season(
    db: AsyncSession,
    *,
    season: str,
    boxscore_delay_seconds: float = 0.0,
    parent_range_run_id: int | None = None,
) -> HistoricalSeasonBackfillResult:
    """Backfill one WBB season, then reconcile and persist its coverage report."""
    game_sync = await sync_current_wbb_season(
        db,
        season=season,
        correction_lookback=0,
        boxscore_delay_seconds=boxscore_delay_seconds,
        parent_range_run_id=parent_range_run_id,
    )

    season_stats: CumulativeStatsImportResult | None = None
    season_stats_status = "failed"
    season_stats_error: str | None = None
    try:
        cumulative_source = await discover_cumulative_stats(WBB_SPORT_SLUG, season)
        season_stats = await import_cumulative_stats(db, cumulative_source)
        season_stats_status = "succeeded"
    except CumulativeStatsParseError as exc:
        await record_cumulative_parser_failure(
            db,
            sport_program_slug=WBB_SPORT_SLUG,
            season=season,
            source_url=exc.source_url,
            raw_html=exc.raw_html,
            http_status=exc.http_status,
            error=str(exc),
        )
        season_stats_error = str(exc)
    except httpx.HTTPError as exc:
        source_url, raw_html, http_status = _http_failure_evidence(exc, season)
        await record_cumulative_parser_failure(
            db,
            sport_program_slug=WBB_SPORT_SLUG,
            season=season,
            source_url=source_url,
            raw_html=raw_html,
            http_status=http_status,
            error=str(exc),
        )
        season_stats_error = str(exc)

    coverage = await _update_game_coverage(
        db,
        season=season,
        game_sync=game_sync,
    )
    finished_at = datetime.now(UTC)
    status = _backfill_status(
        game_sync=game_sync,
        season_stats_status=season_stats_status,
        season_stats=season_stats,
        coverage=coverage,
    )
    result = HistoricalSeasonBackfillResult(
        run_id=game_sync.run_id,
        sport_slug=WBB_SPORT_SLUG,
        season=season,
        status=status,
        started_at=game_sync.started_at,
        finished_at=finished_at,
        game_sync=game_sync,
        season_stats_status=season_stats_status,
        season_stats_error=season_stats_error,
        season_stats=season_stats,
        coverage=coverage,
    )
    await _annotate_sync_run(db, result)
    return result


async def _update_game_coverage(
    db: AsyncSession,
    *,
    season: str,
    game_sync: CurrentSeasonSyncResult,
) -> HistoricalSeasonCoverageResult:
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_SPORT_SLUG)
    )
    team = await db.scalar(select(Team).where(Team.slug == "idaho"))
    if program is None or team is None:
        raise ValueError("Women's basketball warehouse reference data is missing")

    games = list(
        await db.scalars(
            select(Game)
            .options(selectinload(Game.event_sources))
            .where(
                Game.sport == WBB_SPORT_SLUG,
                Game.season == season,
                Game.event_status == "final",
            )
            .order_by(Game.id)
        )
    )
    outcome_errors = {
        outcome.game_id: outcome.error
        for outcome in game_sync.games
        if outcome.status == "failed"
    }
    with_boxscores = 0
    ingested = 0
    for game in games:
        boxscore_url = next(
            (
                source.source_url
                for source in game.event_sources
                if source.source_type == "boxscore_html"
            ),
            None,
        )
        missing_key = _issue_key(program.id, season, "missing-boxscore", game.id)
        failure_key = _issue_key(program.id, season, "boxscore-failure", game.id)
        if boxscore_url is None:
            await _upsert_game_issue(
                db,
                program=program,
                team=team,
                game=game,
                deduplication_key=missing_key,
                issue_type="missing_event",
                summary=(
                    f"Final WBB game {game.title or game.id} has no boxscore source"
                ),
                details={
                    "season": season,
                    "game_id": game.id,
                    "canonical_uid": game.canonical_uid,
                    "schedule_source_url": game.source_url,
                },
            )
            await _resolve_issue(db, failure_key)
            continue

        with_boxscores += 1
        await _resolve_issue(db, missing_key)
        if game.last_successful_ingest_at is None:
            await _upsert_game_issue(
                db,
                program=program,
                team=team,
                game=game,
                deduplication_key=failure_key,
                issue_type="parser_failure",
                summary=(
                    f"Historical boxscore ingest failed for {game.title or game.id}"
                ),
                details={
                    "season": season,
                    "game_id": game.id,
                    "canonical_uid": game.canonical_uid,
                    "boxscore_url": boxscore_url,
                    "error": outcome_errors.get(game.id)
                    or "No successful boxscore ingest is recorded",
                },
            )
            continue

        ingested += 1
        await _resolve_issue(db, failure_key)

    missing_boxscores = len(games) - with_boxscores
    failed_boxscores = with_boxscores - ingested
    completeness = (
        "unknown"
        if not games
        else (
            "complete"
            if missing_boxscores == 0
            and failed_boxscores == 0
            and game_sync.open_identity_issues == 0
            else "partial"
        )
    )
    window = await _upsert_game_coverage_window(
        db,
        program=program,
        season=season,
        completeness=completeness,
        missing_boxscores=missing_boxscores,
        failed_boxscores=failed_boxscores,
        open_identity_issues=game_sync.open_identity_issues,
    )
    open_quality_issues = await _season_open_quality_issue_count(
        db,
        program_id=program.id,
        season=season,
        game_ids={game.id for game in games},
        team_id=team.id,
        team_institutions=(team.canonical_name, team.institution),
    )
    await db.commit()
    return HistoricalSeasonCoverageResult(
        schedule_events_seen=game_sync.schedule_events_seen,
        final_games=len(games),
        final_games_with_boxscores=with_boxscores,
        final_games_ingested=ingested,
        missing_boxscores=missing_boxscores,
        failed_boxscores=failed_boxscores,
        open_identity_issues=game_sync.open_identity_issues,
        open_quality_issues=open_quality_issues,
        game_completeness=completeness,
        game_coverage_window_id=window.id,
    )


async def _upsert_game_coverage_window(
    db: AsyncSession,
    *,
    program: SportProgram,
    season: str,
    completeness: str,
    missing_boxscores: int,
    failed_boxscores: int,
    open_identity_issues: int,
) -> CoverageWindow:
    window = await db.scalar(
        select(CoverageWindow).where(
            CoverageWindow.sport_program_id == program.id,
            CoverageWindow.stat_definition_id.is_(None),
            CoverageWindow.grain == "game",
            CoverageWindow.source_system == PUBLICATION_SOURCE_SYSTEM,
            CoverageWindow.first_season == season,
            CoverageWindow.last_season == season,
        )
    )
    if window is None:
        window = CoverageWindow(
            sport_program_id=program.id,
            stat_definition_id=None,
            grain="game",
            source_system=PUBLICATION_SOURCE_SYSTEM,
            first_season=season,
            last_season=season,
            completeness=completeness,
        )
        db.add(window)
    window.completeness = completeness
    window.known_limitations = (
        "Public GoVandals HTML fallback; authoritative feed/API confirmation is "
        f"pending. Missing boxscores: {missing_boxscores}; failed boxscores: "
        f"{failed_boxscores}; open identity issues: {open_identity_issues}."
    )
    window.verified_at = datetime.now(UTC) if completeness == "complete" else None
    await db.flush()
    return window


async def _upsert_game_issue(
    db: AsyncSession,
    *,
    program: SportProgram,
    team: Team,
    game: Game,
    deduplication_key: str,
    issue_type: str,
    summary: str,
    details: dict,
) -> None:
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    if issue is None:
        db.add(
            DataQualityIssue(
                sport_program_id=program.id,
                team_id=team.id,
                game_id=game.id,
                deduplication_key=deduplication_key,
                issue_type=issue_type,
                status="open",
                severity="error" if issue_type == "parser_failure" else "warning",
                summary=summary,
                details=details,
            )
        )
        return
    issue.status = "open"
    issue.resolved_at = None
    issue.resolution_notes = None
    issue.summary = summary
    issue.details = details


async def _resolve_issue(db: AsyncSession, deduplication_key: str) -> None:
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    if issue is None or issue.status == "resolved":
        return
    issue.status = "resolved"
    issue.resolved_at = datetime.now(UTC)
    issue.resolution_notes = "Resolved by a successful historical season rerun"


async def _season_open_quality_issue_count(
    db: AsyncSession,
    *,
    program_id: int,
    season: str,
    game_ids: set[int],
    team_id: int,
    team_institutions: tuple[str | None, ...],
) -> int:
    institution = DataQualityIssue.details["institution"].as_string()
    season_value = DataQualityIssue.details["season"].as_string()
    institution_names = [name for name in team_institutions if name]
    return int(
        await db.scalar(
            select(func.count(DataQualityIssue.id)).where(
                DataQualityIssue.sport_program_id == program_id,
                DataQualityIssue.status.in_(("open", "in_review")),
                or_(
                    DataQualityIssue.game_id.in_(game_ids),
                    season_value == season,
                ),
                or_(
                    DataQualityIssue.issue_type != "unresolved_identity",
                    DataQualityIssue.team_id == team_id,
                    institution.in_(institution_names),
                    and_(
                        DataQualityIssue.team_id.is_(None),
                        institution.is_(None),
                    ),
                ),
            )
        )
        or 0
    )


async def _annotate_sync_run(
    db: AsyncSession,
    result: HistoricalSeasonBackfillResult,
) -> None:
    run = await db.get(IngestRun, result.run_id)
    if run is None:
        return
    run.status = result.status
    run.finished_at = result.finished_at
    run.duration_ms = max(
        0,
        int((result.finished_at - result.started_at).total_seconds() * 1000),
    )
    run.run_metadata = {
        **run.run_metadata,
        "historical_backfill": {
            "season_stats_status": result.season_stats_status,
            "season_stats_error": result.season_stats_error,
            "final_games": result.coverage.final_games,
            "final_games_with_boxscores": (result.coverage.final_games_with_boxscores),
            "final_games_ingested": result.coverage.final_games_ingested,
            "missing_boxscores": result.coverage.missing_boxscores,
            "failed_boxscores": result.coverage.failed_boxscores,
            "open_identity_issues": result.coverage.open_identity_issues,
            "open_quality_issues": result.coverage.open_quality_issues,
            "game_completeness": result.coverage.game_completeness,
            "game_coverage_window_id": result.coverage.game_coverage_window_id,
        },
    }
    await db.commit()


def _backfill_status(
    *,
    game_sync: CurrentSeasonSyncResult,
    season_stats_status: str,
    season_stats: CumulativeStatsImportResult | None,
    coverage: HistoricalSeasonCoverageResult,
) -> str:
    if (
        game_sync.status == "succeeded"
        and coverage.game_completeness == "complete"
        and coverage.open_quality_issues == 0
        and season_stats_status == "succeeded"
        and season_stats is not None
        and season_stats.coverage_completeness == "complete"
        and season_stats.facts_mismatched == 0
    ):
        return "succeeded"
    return "partial"


def _issue_key(
    program_id: int,
    season: str,
    issue_kind: str,
    game_id: int,
) -> str:
    return f"backfill:{program_id}:{season}:{issue_kind}:{game_id}"


def _http_failure_evidence(
    exc: httpx.HTTPError,
    season: str,
) -> tuple[str, str, int]:
    registry = get_source_registry()
    sport = registry.require_sport(WBB_SPORT_SLUG)
    template = sport.source_patterns.cumulative_stats_url
    assert template is not None
    source_url = urljoin(
        str(registry.base_url),
        template.format(season=season).lstrip("/"),
    )
    raw_html = ""
    http_status = 0
    if isinstance(exc, httpx.HTTPStatusError):
        source_url = str(exc.request.url)
        raw_html = exc.response.text
        http_status = exc.response.status_code
    elif isinstance(exc, httpx.RequestError):
        source_url = str(exc.request.url)
    return source_url, raw_html, http_status
