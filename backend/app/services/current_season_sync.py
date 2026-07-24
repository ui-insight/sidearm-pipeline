"""Bounded, observable synchronization for the current WBB season."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, IngestRun
from app.models.team import Team
from app.services.game_ingest import ingest_boxscore
from app.services.roster_import import RosterImportResult, import_roster
from app.services.schedule_import import import_schedule_events
from app.services.sidearm_roster import discover_roster
from app.services.sidearm_schedule import ParsedScheduleEvent, discover_schedule_events

WBB_SPORT_SLUG = "womens-basketball"
ACTIVE_RUN_WINDOW = timedelta(minutes=30)


class SeasonSyncAlreadyRunning(RuntimeError):
    """Raised when a non-stale sync already owns the season workflow."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        super().__init__(f"Season sync run {run_id} is already in progress")


class SeasonSyncFailed(RuntimeError):
    """Raised when roster or schedule discovery prevents a season sync."""


@dataclass(frozen=True)
class CurrentSeasonGameRefresh:
    """Outcome for one boxscore selected by the bounded refresh plan."""

    game_id: int
    title: str
    source_url: str
    reasons: list[str]
    status: str
    error: str | None = None


@dataclass(frozen=True)
class CurrentSeasonSyncResult:
    """Counts and evidence returned to the newsroom operator."""

    run_id: int
    sport_slug: str
    season: str
    status: str
    correction_lookback: int
    started_at: datetime
    finished_at: datetime
    roster: RosterImportResult
    schedule_events_seen: int
    schedule_games_created: int
    schedule_games_changed: int
    schedule_games_unchanged: int
    final_boxscores_seen: int
    boxscores_selected: int
    boxscores_refreshed: int
    boxscores_skipped: int
    boxscores_failed: int
    open_identity_issues: int
    games: list[CurrentSeasonGameRefresh]


@dataclass(frozen=True)
class _ExistingGameState:
    game_id: int
    fingerprint: tuple[object, ...]
    last_successful_ingest_at: datetime | None


async def sync_current_wbb_season(
    db: AsyncSession,
    *,
    season: str,
    correction_lookback: int = 2,
    boxscore_delay_seconds: float = 0.0,
    parent_range_run_id: int | None = None,
) -> CurrentSeasonSyncResult:
    """Synchronize one WBB season without refetching every historical boxscore."""
    _validate_inputs(season, correction_lookback, boxscore_delay_seconds)
    started_at = datetime.now(UTC)
    await _claim_sync_run(
        db,
        season=season,
        started_at=started_at,
        parent_range_run_id=parent_range_run_id,
    )
    sync_run = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type="season_sync",
        source_url=(
            f"https://govandals.com/sports/womens-basketball/schedule/{season}"
        ),
        sport=WBB_SPORT_SLUG,
        season=season,
        status="running",
        started_at=started_at,
        run_metadata={
            "season": season,
            "correction_lookback": correction_lookback,
            "boxscore_delay_seconds": boxscore_delay_seconds,
            "parent_range_run_id": parent_range_run_id,
        },
    )
    db.add(sync_run)
    await db.commit()
    run_id = sync_run.id

    try:
        roster = await discover_roster(WBB_SPORT_SLUG, season)
        roster_result = await import_roster(db, roster)
        events = await discover_schedule_events(WBB_SPORT_SLUG, season=season)
        existing = await _existing_game_states(db, season)
        games = await import_schedule_events(db, events)
        season_game_ids = [game.id for game in games]
    except Exception as exc:
        await db.rollback()
        await _finish_fatal_sync(db, run_id=run_id, started_at=started_at, exc=exc)
        raise SeasonSyncFailed(str(exc)) from exc

    created, changed, unchanged = _schedule_change_counts(events, games, existing)
    eligible = [
        (event, game)
        for event, game in zip(events, games, strict=True)
        if event.event_status == "final" and event.boxscore_url
    ]
    recent_game_ids = {
        game.id
        for _, game in sorted(
            eligible,
            key=lambda pair: pair[0].event_date or date.min,
            reverse=True,
        )[:correction_lookback]
    }
    resolved_after_ingest = await _resolved_identity_games(db, games)

    selected: list[tuple[ParsedScheduleEvent, Game, list[str]]] = []
    for event, game in eligible:
        reasons = _refresh_reasons(
            event=event,
            game=game,
            existing=existing,
            recent_game_ids=recent_game_ids,
            resolved_after_ingest=resolved_after_ingest,
        )
        if reasons:
            selected.append((event, game, reasons))

    outcomes: list[CurrentSeasonGameRefresh] = []
    for index, (event, game, reasons) in enumerate(selected):
        if index > 0 and boxscore_delay_seconds > 0:
            await asyncio.sleep(boxscore_delay_seconds)
        assert event.boxscore_url is not None
        game_id = game.id
        game_title = game.title or "Untitled game"
        try:
            refreshed_game = await ingest_boxscore(
                db,
                event.boxscore_url,
                trigger_type="season_sync",
                preserve_schedule_metadata=True,
            )
            outcomes.append(
                CurrentSeasonGameRefresh(
                    game_id=refreshed_game.id,
                    title=refreshed_game.title or game_title,
                    source_url=event.boxscore_url,
                    reasons=reasons,
                    status="refreshed",
                )
            )
        except Exception as exc:
            await db.rollback()
            outcomes.append(
                CurrentSeasonGameRefresh(
                    game_id=game_id,
                    title=game_title,
                    source_url=event.boxscore_url,
                    reasons=reasons,
                    status="failed",
                    error=str(exc),
                )
            )

    refreshed = sum(outcome.status == "refreshed" for outcome in outcomes)
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    skipped = len(eligible) - len(selected)
    idaho = await db.scalar(select(Team).where(Team.slug == "idaho"))
    if idaho is None:
        raise ValueError("Idaho team reference data is missing")
    open_identity_issues = await _open_identity_issue_count(
        db,
        season_game_ids,
        team_id=idaho.id,
        team_institutions=(idaho.canonical_name, idaho.institution),
    )
    finished_at = datetime.now(UTC)
    status = "succeeded" if failed == 0 else "partial"
    result = CurrentSeasonSyncResult(
        run_id=run_id,
        sport_slug=WBB_SPORT_SLUG,
        season=season,
        status=status,
        correction_lookback=correction_lookback,
        started_at=started_at,
        finished_at=finished_at,
        roster=roster_result,
        schedule_events_seen=len(events),
        schedule_games_created=created,
        schedule_games_changed=changed,
        schedule_games_unchanged=unchanged,
        final_boxscores_seen=len(eligible),
        boxscores_selected=len(selected),
        boxscores_refreshed=refreshed,
        boxscores_skipped=skipped,
        boxscores_failed=failed,
        open_identity_issues=open_identity_issues,
        games=outcomes,
    )
    await _finish_sync_run(db, result)
    return result


def _validate_inputs(
    season: str,
    correction_lookback: int,
    boxscore_delay_seconds: float,
) -> None:
    if not re.fullmatch(r"20\d{2}-\d{2}", season):
        raise ValueError("WBB season must be an academic year like 2025-26")
    if correction_lookback < 0 or correction_lookback > 5:
        raise ValueError("Correction lookback must be between 0 and 5 games")
    if boxscore_delay_seconds < 0 or boxscore_delay_seconds > 10:
        raise ValueError("Boxscore delay must be between 0 and 10 seconds")


async def _claim_sync_run(
    db: AsyncSession,
    *,
    season: str,
    started_at: datetime,
    parent_range_run_id: int | None,
) -> None:
    running = await db.scalar(
        select(IngestRun)
        .where(
            IngestRun.source_type == "season_sync",
            IngestRun.sport == WBB_SPORT_SLUG,
            IngestRun.season == season,
            IngestRun.status == "running",
        )
        .order_by(IngestRun.started_at.desc())
    )
    if running is None:
        return
    if (
        parent_range_run_id is not None
        and running.run_metadata.get("parent_range_run_id") == parent_range_run_id
    ):
        running.status = "failed"
        running.finished_at = started_at
        running.error_type = "InterruptedHistoricalRangeSeason"
        running.error_message = "Reclaimed by an explicit resume of its parent range"
        running.run_metadata = {
            **running.run_metadata,
            "reclaimed_by_parent_resume": True,
        }
        await db.commit()
        return
    if _as_utc(running.started_at) >= started_at - ACTIVE_RUN_WINDOW:
        raise SeasonSyncAlreadyRunning(running.id)
    running.status = "failed"
    running.finished_at = started_at
    running.error_type = "StaleSeasonSync"
    running.error_message = "The prior season sync exceeded the active run window"
    running.run_metadata = {**running.run_metadata, "stale_run_recovered": True}
    await db.commit()


async def _existing_game_states(
    db: AsyncSession,
    season: str,
) -> dict[str, _ExistingGameState]:
    games = list(
        await db.scalars(
            select(Game).where(
                Game.sport == WBB_SPORT_SLUG,
                Game.season == season,
            )
        )
    )
    return {
        _game_key(game.source_event_id, game.source_url): _ExistingGameState(
            game_id=game.id,
            fingerprint=_game_fingerprint(game),
            last_successful_ingest_at=game.last_successful_ingest_at,
        )
        for game in games
    }


def _schedule_change_counts(
    events: list[ParsedScheduleEvent],
    games: list[Game],
    existing: dict[str, _ExistingGameState],
) -> tuple[int, int, int]:
    created = 0
    changed = 0
    unchanged = 0
    for event, game in zip(events, games, strict=True):
        state = existing.get(_event_key(event))
        if state is None:
            created += 1
        elif state.fingerprint != _game_fingerprint(game):
            changed += 1
        else:
            unchanged += 1
    return created, changed, unchanged


def _refresh_reasons(
    *,
    event: ParsedScheduleEvent,
    game: Game,
    existing: dict[str, _ExistingGameState],
    recent_game_ids: set[int],
    resolved_after_ingest: set[int],
) -> list[str]:
    state = existing.get(_event_key(event))
    reasons: list[str] = []
    if state is None or state.last_successful_ingest_at is None:
        reasons.append("not_yet_ingested")
    elif state.fingerprint != _game_fingerprint(game):
        reasons.append("schedule_changed")
    if game.id in resolved_after_ingest:
        reasons.append("identity_decision")
    if game.id in recent_game_ids:
        reasons.append("correction_lookback")
    return reasons


async def _resolved_identity_games(
    db: AsyncSession,
    games: list[Game],
) -> set[int]:
    by_id = {game.id: game for game in games}
    if not by_id:
        return set()
    issues = list(
        await db.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.game_id.in_(by_id),
                DataQualityIssue.issue_type == "unresolved_identity",
                DataQualityIssue.status == "resolved",
                DataQualityIssue.resolved_at.is_not(None),
            )
        )
    )
    return {
        issue.game_id
        for issue in issues
        if issue.game_id is not None
        and (
            by_id[issue.game_id].last_successful_ingest_at is None
            or _as_utc(issue.resolved_at)
            > _as_utc(by_id[issue.game_id].last_successful_ingest_at)
        )
    }


async def _open_identity_issue_count(
    db: AsyncSession,
    game_ids: list[int],
    *,
    team_id: int,
    team_institutions: tuple[str | None, ...],
) -> int:
    if not game_ids:
        return 0
    institution = DataQualityIssue.details["institution"].as_string()
    institution_names = [name for name in team_institutions if name]
    return int(
        await db.scalar(
            select(func.count(DataQualityIssue.id)).where(
                DataQualityIssue.game_id.in_(game_ids),
                DataQualityIssue.issue_type == "unresolved_identity",
                DataQualityIssue.status == "open",
                or_(
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


async def _finish_sync_run(
    db: AsyncSession,
    result: CurrentSeasonSyncResult,
) -> None:
    run = await db.get(IngestRun, result.run_id)
    assert run is not None
    run.status = result.status
    run.finished_at = result.finished_at
    run.duration_ms = _duration_ms(result.started_at, result.finished_at)
    run.run_metadata = {
        "season": result.season,
        "correction_lookback": result.correction_lookback,
        "boxscore_delay_seconds": run.run_metadata.get(
            "boxscore_delay_seconds",
            0.0,
        ),
        "parent_range_run_id": run.run_metadata.get("parent_range_run_id"),
        "schedule_events_seen": result.schedule_events_seen,
        "schedule_games_created": result.schedule_games_created,
        "schedule_games_changed": result.schedule_games_changed,
        "schedule_games_unchanged": result.schedule_games_unchanged,
        "final_boxscores_seen": result.final_boxscores_seen,
        "boxscores_selected": result.boxscores_selected,
        "boxscores_refreshed": result.boxscores_refreshed,
        "boxscores_skipped": result.boxscores_skipped,
        "boxscores_failed": result.boxscores_failed,
        "open_identity_issues": result.open_identity_issues,
        "games": [
            {
                "game_id": game.game_id,
                "source_url": game.source_url,
                "reasons": game.reasons,
                "status": game.status,
                "error": game.error,
            }
            for game in result.games
        ],
    }
    await db.commit()


async def _finish_fatal_sync(
    db: AsyncSession,
    *,
    run_id: int,
    started_at: datetime,
    exc: Exception,
) -> None:
    run = await db.get(IngestRun, run_id)
    assert run is not None
    finished_at = datetime.now(UTC)
    run.status = "failed"
    run.finished_at = finished_at
    run.duration_ms = _duration_ms(started_at, finished_at)
    run.error_type = type(exc).__name__
    run.error_message = str(exc)
    run.run_metadata = {**run.run_metadata, "failure_phase": "season_discovery"}
    await db.commit()


def _event_key(event: ParsedScheduleEvent) -> str:
    return _game_key(event.source_event_id, event.boxscore_url or event.schedule_url)


def _game_key(source_event_id: str | None, source_url: str) -> str:
    return source_event_id or source_url


def _game_fingerprint(game: Game) -> tuple[object, ...]:
    return (
        game.source_url,
        game.event_status,
        game.home_team,
        game.away_team,
        game.home_score,
        game.away_score,
        game.location_name,
        game.venue_name,
        game.home_away_neutral,
        game.conference_event,
    )


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(0, int((finished_at - started_at).total_seconds() * 1000))
