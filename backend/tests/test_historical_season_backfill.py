"""Tests for bounded, observable historical WBB season backfills."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import EventSource, Game, IngestRun
from app.models.sport_program import SportProgram
from app.services.current_season_sync import (
    CurrentSeasonGameRefresh,
    CurrentSeasonSyncResult,
)
from app.services.roster_import import RosterImportResult
from app.services.season_stat_import import (
    CumulativeStatsImportResult,
    resolve_cumulative_parser_failure,
)
from app.services.sidearm_cumulative_stats import (
    CumulativeStatsParseError,
    ParsedCumulativeStats,
)

SEASON = "2024-25"
SCHEDULE_URL = "https://govandals.com/sports/womens-basketball/schedule/2024-25"
BOXSCORE_URL = (
    "https://govandals.com/sports/womens-basketball/stats/2024-25/montana/boxscore/9001"
)
CUMULATIVE_URL = "https://govandals.com/sports/womens-basketball/stats/2024-25"


async def _seed_backfill_context(
    db_session,
    *,
    with_boxscore: bool,
) -> tuple[int, Game]:
    await seed_warehouse_reference_data(db_session)
    now = datetime.now(UTC)
    run = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type="season_sync",
        source_url=SCHEDULE_URL,
        sport="womens-basketball",
        season=SEASON,
        status="succeeded",
        started_at=now,
        finished_at=now,
        run_metadata={},
    )
    game = Game(
        source_url=BOXSCORE_URL if with_boxscore else f"{SCHEDULE_URL}#game-9001",
        canonical_uid=f"sidearm:womens-basketball:{SEASON}:9001",
        source_system="sidearm",
        source_event_id="9001",
        sport="womens-basketball",
        season=SEASON,
        event_status="final",
        title="Idaho vs Montana",
        last_successful_ingest_at=now if with_boxscore else None,
    )
    game.event_sources.append(
        EventSource(
            source_type="schedule_html",
            source_url=SCHEDULE_URL,
            source_id="9001",
            primary_source=not with_boxscore,
        )
    )
    if with_boxscore:
        game.event_sources.append(
            EventSource(
                source_type="boxscore_html",
                source_url=BOXSCORE_URL,
                source_id="9001",
                primary_source=True,
            )
        )
    db_session.add_all([run, game])
    await db_session.commit()
    return run.id, game


def _sync_result(
    run_id: int,
    *,
    final_boxscores_seen: int,
    status: str = "succeeded",
    games: list[CurrentSeasonGameRefresh] | None = None,
) -> CurrentSeasonSyncResult:
    now = datetime.now(UTC)
    return CurrentSeasonSyncResult(
        run_id=run_id,
        sport_slug="womens-basketball",
        season=SEASON,
        status=status,
        correction_lookback=0,
        started_at=now,
        finished_at=now,
        roster=RosterImportResult(
            source_url=(
                "https://govandals.com/sports/womens-basketball/roster/2024-25"
            ),
            season=SEASON,
            source_snapshot_id=10,
            players_seen=12,
            players_created=12,
            identities_created=12,
            player_seasons_created=12,
            player_seasons_updated=0,
            quality_issues_created=0,
        ),
        schedule_events_seen=1,
        schedule_games_created=0,
        schedule_games_changed=0,
        schedule_games_unchanged=1,
        final_boxscores_seen=final_boxscores_seen,
        boxscores_selected=len(games or []),
        boxscores_refreshed=0,
        boxscores_skipped=final_boxscores_seen - len(games or []),
        boxscores_failed=sum(game.status == "failed" for game in games or []),
        open_identity_issues=0,
        games=games or [],
    )


def _cumulative_source() -> ParsedCumulativeStats:
    return ParsedCumulativeStats(
        sport_program_slug="womens-basketball",
        season=SEASON,
        source_system="govandals_public_html",
        identity_source_system="sidearm",
        institution="University of Idaho",
        team_slug="idaho",
        source_url=CUMULATIVE_URL,
        raw_html="<html>cumulative</html>",
    )


def _cumulative_result(
    *,
    completeness: str = "complete",
) -> CumulativeStatsImportResult:
    return CumulativeStatsImportResult(
        source_url=CUMULATIVE_URL,
        season=SEASON,
        source_snapshot_id=20,
        players_seen=12,
        players_resolved=12,
        players_unresolved=0,
        source_conflicts=0,
        facts_written=192,
        comparisons_run=192,
        facts_matched=192,
        facts_mismatched=0,
        coverage_gaps=0,
        quality_issues_created=0,
        quality_issues_resolved=0,
        coverage_completeness=completeness,
        coverage_window_ids=[30],
    )


async def test_historical_backfill_reports_complete_coverage_idempotently(
    client,
    db_session,
    monkeypatch,
) -> None:
    run_id, game = await _seed_backfill_context(db_session, with_boxscore=True)
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    db_session.add(
        DataQualityIssue(
            sport_program_id=program.id,
            game_id=game.id,
            issue_type="unresolved_identity",
            status="open",
            severity="warning",
            summary="Opponent player needs review",
            details={"season": SEASON, "institution": "Montana"},
        )
    )
    await db_session.commit()

    async def fake_sync(*args, **kwargs) -> CurrentSeasonSyncResult:
        assert kwargs == {
            "season": SEASON,
            "correction_lookback": 0,
            "boxscore_delay_seconds": 0.0,
            "parent_range_run_id": None,
        }
        return _sync_result(run_id, final_boxscores_seen=1)

    async def fake_discover(*args, **kwargs) -> ParsedCumulativeStats:
        return _cumulative_source()

    async def fake_import(*args, **kwargs) -> CumulativeStatsImportResult:
        return _cumulative_result()

    monkeypatch.setattr(
        "app.services.historical_season_backfill.sync_current_wbb_season",
        fake_sync,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.discover_cumulative_stats",
        fake_discover,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.import_cumulative_stats",
        fake_import,
    )

    first = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/backfill"
    )
    second = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/backfill"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["status"] == "succeeded"
    assert payload["game_sync"]["correction_lookback"] == 0
    assert payload["season_stats_status"] == "succeeded"
    assert payload["season_stats"]["facts_matched"] == 192
    assert payload["coverage"] == {
        "schedule_events_seen": 1,
        "final_games": 1,
        "final_games_with_boxscores": 1,
        "final_games_ingested": 1,
        "missing_boxscores": 0,
        "failed_boxscores": 0,
        "open_identity_issues": 0,
        "open_quality_issues": 0,
        "game_completeness": "complete",
        "game_coverage_window_id": payload["coverage"]["game_coverage_window_id"],
    }
    assert (
        await db_session.scalar(
            select(func.count(CoverageWindow.id)).where(
                CoverageWindow.grain == "game",
                CoverageWindow.first_season == SEASON,
                CoverageWindow.last_season == SEASON,
            )
        )
        == 1
    )


async def test_historical_backfill_persists_and_resolves_explicit_gaps(
    client,
    db_session,
    monkeypatch,
) -> None:
    run_id, game = await _seed_backfill_context(db_session, with_boxscore=False)

    async def fake_sync(*args, **kwargs) -> CurrentSeasonSyncResult:
        with_boxscore = any(
            source.source_type == "boxscore_html" for source in game.event_sources
        )
        return _sync_result(run_id, final_boxscores_seen=int(with_boxscore))

    async def failing_discover(*args, **kwargs) -> ParsedCumulativeStats:
        raise CumulativeStatsParseError(
            "Overall table is unavailable",
            source_url=CUMULATIVE_URL,
            raw_html="<html>unsupported</html>",
            http_status=200,
        )

    monkeypatch.setattr(
        "app.services.historical_season_backfill.sync_current_wbb_season",
        fake_sync,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.discover_cumulative_stats",
        failing_discover,
    )

    first = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/backfill"
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["status"] == "partial"
    assert first_payload["season_stats_status"] == "failed"
    assert "Overall table is unavailable" in first_payload["season_stats_error"]
    assert first_payload["coverage"]["missing_boxscores"] == 1
    assert first_payload["coverage"]["game_completeness"] == "partial"
    issues = list(
        await db_session.scalars(
            select(DataQualityIssue).order_by(DataQualityIssue.issue_type)
        )
    )
    assert [issue.issue_type for issue in issues] == [
        "missing_event",
        "parser_failure",
    ]
    assert all(issue.status == "open" for issue in issues)

    game.source_url = BOXSCORE_URL
    game.last_successful_ingest_at = datetime.now(UTC)
    game.event_sources.append(
        EventSource(
            source_type="boxscore_html",
            source_url=BOXSCORE_URL,
            source_id="9001",
            primary_source=True,
        )
    )
    await db_session.commit()

    async def successful_discover(*args, **kwargs) -> ParsedCumulativeStats:
        return _cumulative_source()

    async def successful_import(db, *args, **kwargs) -> CumulativeStatsImportResult:
        await resolve_cumulative_parser_failure(
            db,
            sport_program_slug="womens-basketball",
            season=SEASON,
        )
        return _cumulative_result()

    monkeypatch.setattr(
        "app.services.historical_season_backfill.discover_cumulative_stats",
        successful_discover,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.import_cumulative_stats",
        successful_import,
    )

    second = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/backfill"
    )

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["status"] == "succeeded"
    assert second_payload["coverage"]["missing_boxscores"] == 0
    assert second_payload["coverage"]["open_quality_issues"] == 0
    await db_session.refresh(issues[0])
    await db_session.refresh(issues[1])
    assert all(issue.status == "resolved" for issue in issues)


async def test_historical_backfill_records_unparseable_boxscore(
    client,
    db_session,
    monkeypatch,
) -> None:
    run_id, game = await _seed_backfill_context(db_session, with_boxscore=True)
    game.last_successful_ingest_at = None
    await db_session.commit()
    failed_game = CurrentSeasonGameRefresh(
        game_id=game.id,
        title=game.title or "Idaho vs Montana",
        source_url=BOXSCORE_URL,
        reasons=["not_yet_ingested"],
        status="failed",
        error="Unsupported historical player table",
    )

    async def fake_sync(*args, **kwargs) -> CurrentSeasonSyncResult:
        return _sync_result(
            run_id,
            final_boxscores_seen=1,
            status="partial",
            games=[failed_game],
        )

    async def fake_discover(*args, **kwargs) -> ParsedCumulativeStats:
        return _cumulative_source()

    async def fake_import(*args, **kwargs) -> CumulativeStatsImportResult:
        return _cumulative_result(completeness="partial")

    monkeypatch.setattr(
        "app.services.historical_season_backfill.sync_current_wbb_season",
        fake_sync,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.discover_cumulative_stats",
        fake_discover,
    )
    monkeypatch.setattr(
        "app.services.historical_season_backfill.import_cumulative_stats",
        fake_import,
    )

    response = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/backfill"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["coverage"]["failed_boxscores"] == 1
    assert payload["game_sync"]["games"][0]["error"] == (
        "Unsupported historical player table"
    )
    issue = await db_session.scalar(
        select(DataQualityIssue).where(DataQualityIssue.issue_type == "parser_failure")
    )
    assert issue is not None
    assert issue.status == "open"
    assert issue.game_id == game.id
    assert issue.details["error"] == "Unsupported historical player table"


async def test_historical_backfill_rejects_other_sports(client) -> None:
    response = await client.post(f"/api/v1/sources/football/seasons/{SEASON}/backfill")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Historical season backfill currently supports WBB only"
    )
