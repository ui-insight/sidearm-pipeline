"""Sequential, resumable historical WBB backfill orchestration."""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import IngestRun
from app.services.historical_season_backfill import (
    HistoricalSeasonCoverageResult,
    backfill_historical_wbb_season,
)

WBB_SPORT_SLUG = "womens-basketball"
RANGE_SOURCE_TYPE = "historical_range_backfill"
MAX_RANGE_SEASONS = 10
ACTIVE_RANGE_WINDOW = timedelta(hours=12)


class HistoricalRangeAlreadyRunning(RuntimeError):
    """Raised when another active historical range run owns the workflow."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        super().__init__(f"Historical range backfill run {run_id} is already active")


@dataclass(frozen=True)
class HistoricalRangeSeasonResult:
    """Durable outcome for one season in a historical range."""

    season: str
    status: str
    season_run_id: int | None
    started_at: datetime
    finished_at: datetime
    coverage: HistoricalSeasonCoverageResult | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class HistoricalRangeBackfillResult:
    """Operator-readable outcome for one sequential historical range run."""

    run_id: int
    sport_slug: str
    start_season: str
    end_season: str
    status: str
    boxscore_delay_seconds: float
    resumed: bool
    started_at: datetime
    finished_at: datetime
    seasons_total: int
    seasons_attempted: int
    seasons_skipped: int
    seasons_succeeded: int
    seasons_partial: int
    seasons_failed: int
    seasons: list[HistoricalRangeSeasonResult]


def academic_seasons_between(start_season: str, end_season: str) -> list[str]:
    """Return an inclusive, ascending list of valid academic season labels."""
    start_year = _academic_start_year(start_season)
    end_year = _academic_start_year(end_season)
    if start_year > end_year:
        raise ValueError("Start season must not be later than end season")
    count = end_year - start_year + 1
    if count > MAX_RANGE_SEASONS:
        raise ValueError(
            f"Historical range backfills are limited to {MAX_RANGE_SEASONS} seasons"
        )
    return [
        f"{year:04d}-{(year + 1) % 100:02d}" for year in range(start_year, end_year + 1)
    ]


async def backfill_historical_wbb_range(
    db: AsyncSession,
    *,
    start_season: str,
    end_season: str,
    boxscore_delay_seconds: float = 1.0,
    resume_run_id: int | None = None,
) -> HistoricalRangeBackfillResult:
    """Backfill an inclusive WBB season range with durable season checkpoints."""
    seasons = academic_seasons_between(start_season, end_season)
    _validate_delay(boxscore_delay_seconds)
    resumed = resume_run_id is not None
    if resume_run_id is None:
        run = await _create_range_run(
            db,
            start_season=start_season,
            end_season=end_season,
            seasons=seasons,
            boxscore_delay_seconds=boxscore_delay_seconds,
        )
    else:
        run = await _resume_range_run(
            db,
            run_id=resume_run_id,
            start_season=start_season,
            end_season=end_season,
            boxscore_delay_seconds=boxscore_delay_seconds,
        )

    outcomes = _stored_outcomes(run)
    seasons_attempted = 0
    for season in seasons:
        prior = outcomes.get(season)
        if prior is not None and prior.status in {"succeeded", "partial"}:
            continue
        if seasons_attempted > 0 and boxscore_delay_seconds > 0:
            await asyncio.sleep(boxscore_delay_seconds)
        seasons_attempted += 1
        attempted_at = datetime.now(UTC)
        try:
            season_result = await backfill_historical_wbb_season(
                db,
                season=season,
                boxscore_delay_seconds=boxscore_delay_seconds,
                parent_range_run_id=run.id,
            )
            outcome = HistoricalRangeSeasonResult(
                season=season,
                status=season_result.status,
                season_run_id=season_result.run_id,
                started_at=season_result.started_at,
                finished_at=season_result.finished_at,
                coverage=season_result.coverage,
            )
        except Exception as exc:
            await db.rollback()
            outcome = HistoricalRangeSeasonResult(
                season=season,
                status="failed",
                season_run_id=None,
                started_at=attempted_at,
                finished_at=datetime.now(UTC),
                coverage=None,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        outcomes[season] = outcome
        await _checkpoint_range_run(
            db,
            run_id=run.id,
            season_order=seasons,
            outcomes=outcomes,
        )

    ordered_outcomes = [outcomes[season] for season in seasons]
    finished_at = datetime.now(UTC)
    status = _range_status(ordered_outcomes)
    succeeded = sum(outcome.status == "succeeded" for outcome in ordered_outcomes)
    partial = sum(outcome.status == "partial" for outcome in ordered_outcomes)
    failed = sum(outcome.status == "failed" for outcome in ordered_outcomes)
    seasons_skipped = len(seasons) - seasons_attempted
    await _finish_range_run(
        db,
        run_id=run.id,
        status=status,
        finished_at=finished_at,
        season_order=seasons,
        outcomes=outcomes,
        seasons_succeeded=succeeded,
        seasons_partial=partial,
        seasons_failed=failed,
    )
    return HistoricalRangeBackfillResult(
        run_id=run.id,
        sport_slug=WBB_SPORT_SLUG,
        start_season=start_season,
        end_season=end_season,
        status=status,
        boxscore_delay_seconds=boxscore_delay_seconds,
        resumed=resumed,
        started_at=_as_utc(run.started_at),
        finished_at=finished_at,
        seasons_total=len(seasons),
        seasons_attempted=seasons_attempted,
        seasons_skipped=seasons_skipped,
        seasons_succeeded=succeeded,
        seasons_partial=partial,
        seasons_failed=failed,
        seasons=ordered_outcomes,
    )


def _academic_start_year(season: str) -> int:
    match = re.fullmatch(r"(20\d{2})-(\d{2})", season)
    if match is None:
        raise ValueError("WBB season must be an academic year like 2025-26")
    start_year = int(match.group(1))
    expected_suffix = (start_year + 1) % 100
    if int(match.group(2)) != expected_suffix:
        raise ValueError(f"Academic season {season} must end in {expected_suffix:02d}")
    return start_year


def _validate_delay(boxscore_delay_seconds: float) -> None:
    if boxscore_delay_seconds < 0 or boxscore_delay_seconds > 10:
        raise ValueError("Boxscore delay must be between 0 and 10 seconds")


async def _create_range_run(
    db: AsyncSession,
    *,
    start_season: str,
    end_season: str,
    seasons: list[str],
    boxscore_delay_seconds: float,
) -> IngestRun:
    started_at = datetime.now(UTC)
    await _claim_range_workflow(db, started_at=started_at)
    run = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type=RANGE_SOURCE_TYPE,
        source_url=(
            "https://govandals.com/sports/womens-basketball/schedule"
            f"?start={start_season}&end={end_season}"
        ),
        sport=WBB_SPORT_SLUG,
        season=None,
        status="running",
        started_at=started_at,
        run_metadata={
            "start_season": start_season,
            "end_season": end_season,
            "season_order": seasons,
            "boxscore_delay_seconds": boxscore_delay_seconds,
            "resume_count": 0,
            "seasons": [],
        },
    )
    db.add(run)
    await db.commit()
    return run


async def _claim_range_workflow(
    db: AsyncSession,
    *,
    started_at: datetime,
    allowed_run_id: int | None = None,
) -> None:
    query = select(IngestRun).where(
        IngestRun.source_type == RANGE_SOURCE_TYPE,
        IngestRun.sport == WBB_SPORT_SLUG,
        IngestRun.status == "running",
    )
    if allowed_run_id is not None:
        query = query.where(IngestRun.id != allowed_run_id)
    running = await db.scalar(query.order_by(IngestRun.started_at.desc()))
    if running is None:
        return
    if _as_utc(running.started_at) >= started_at - ACTIVE_RANGE_WINDOW:
        raise HistoricalRangeAlreadyRunning(running.id)
    running.status = "failed"
    running.finished_at = started_at
    running.error_type = "StaleHistoricalRangeBackfill"
    running.error_message = "The prior range backfill exceeded its active window"
    running.run_metadata = {
        **running.run_metadata,
        "stale_run_recovered": True,
    }
    await db.commit()


async def _resume_range_run(
    db: AsyncSession,
    *,
    run_id: int,
    start_season: str,
    end_season: str,
    boxscore_delay_seconds: float,
) -> IngestRun:
    run = await db.get(IngestRun, run_id)
    if run is None:
        raise LookupError(f"Historical range backfill run {run_id} was not found")
    if run.source_type != RANGE_SOURCE_TYPE or run.sport != WBB_SPORT_SLUG:
        raise ValueError(f"Ingest run {run_id} is not a WBB historical range backfill")
    metadata = run.run_metadata
    if (
        metadata.get("start_season") != start_season
        or metadata.get("end_season") != end_season
    ):
        raise ValueError("Resume range must match the original start and end seasons")
    await _claim_range_workflow(
        db,
        started_at=datetime.now(UTC),
        allowed_run_id=run_id,
    )
    run.status = "running"
    run.finished_at = None
    run.duration_ms = None
    run.error_type = None
    run.error_message = None
    run.attempt_count = (run.attempt_count or 1) + 1
    run.run_metadata = {
        **metadata,
        "boxscore_delay_seconds": boxscore_delay_seconds,
        "resume_count": int(metadata.get("resume_count", 0)) + 1,
        "last_resumed_at": datetime.now(UTC).isoformat(),
    }
    await db.commit()
    return run


def _stored_outcomes(run: IngestRun) -> dict[str, HistoricalRangeSeasonResult]:
    outcomes: dict[str, HistoricalRangeSeasonResult] = {}
    for stored in run.run_metadata.get("seasons", []):
        coverage_data = stored.get("coverage")
        coverage = (
            HistoricalSeasonCoverageResult(**coverage_data)
            if coverage_data is not None
            else None
        )
        outcome = HistoricalRangeSeasonResult(
            season=stored["season"],
            status=stored["status"],
            season_run_id=stored.get("season_run_id"),
            started_at=datetime.fromisoformat(stored["started_at"]),
            finished_at=datetime.fromisoformat(stored["finished_at"]),
            coverage=coverage,
            error_type=stored.get("error_type"),
            error_message=stored.get("error_message"),
        )
        outcomes[outcome.season] = outcome
    return outcomes


async def _checkpoint_range_run(
    db: AsyncSession,
    *,
    run_id: int,
    season_order: list[str],
    outcomes: dict[str, HistoricalRangeSeasonResult],
) -> None:
    run = await db.get(IngestRun, run_id)
    assert run is not None
    run.run_metadata = {
        **run.run_metadata,
        "seasons": [
            _serialize_outcome(outcomes[season])
            for season in season_order
            if season in outcomes
        ],
        "last_checkpoint_at": datetime.now(UTC).isoformat(),
    }
    await db.commit()


async def _finish_range_run(
    db: AsyncSession,
    *,
    run_id: int,
    status: str,
    finished_at: datetime,
    season_order: list[str],
    outcomes: dict[str, HistoricalRangeSeasonResult],
    seasons_succeeded: int,
    seasons_partial: int,
    seasons_failed: int,
) -> None:
    run = await db.get(IngestRun, run_id)
    assert run is not None
    run.status = status
    run.finished_at = finished_at
    run.duration_ms = max(
        0,
        int((finished_at - _as_utc(run.started_at)).total_seconds() * 1000),
    )
    run.error_type = "SeasonBackfillFailures" if seasons_failed else None
    run.error_message = (
        f"{seasons_failed} season backfill(s) failed" if seasons_failed else None
    )
    run.run_metadata = {
        **run.run_metadata,
        "seasons": [_serialize_outcome(outcomes[season]) for season in season_order],
        "seasons_succeeded": seasons_succeeded,
        "seasons_partial": seasons_partial,
        "seasons_failed": seasons_failed,
        "finished_at": finished_at.isoformat(),
    }
    await db.commit()


def _serialize_outcome(outcome: HistoricalRangeSeasonResult) -> dict:
    return {
        "season": outcome.season,
        "status": outcome.status,
        "season_run_id": outcome.season_run_id,
        "started_at": outcome.started_at.isoformat(),
        "finished_at": outcome.finished_at.isoformat(),
        "coverage": asdict(outcome.coverage) if outcome.coverage is not None else None,
        "error_type": outcome.error_type,
        "error_message": outcome.error_message,
    }


def _range_status(outcomes: list[HistoricalRangeSeasonResult]) -> str:
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    if failed == len(outcomes):
        return "failed"
    if failed or any(outcome.status == "partial" for outcome in outcomes):
        return "partial"
    return "succeeded"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
