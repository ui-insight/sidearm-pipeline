"""Tests for sequential, resumable historical WBB range backfills."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.game import IngestRun
from app.services.historical_range_backfill import academic_seasons_between
from app.services.historical_season_backfill import HistoricalSeasonCoverageResult


def _season_result(season: str, *, status: str = "succeeded") -> SimpleNamespace:
    now = datetime.now(UTC)
    start_year = int(season[:4])
    return SimpleNamespace(
        run_id=10_000 + start_year,
        season=season,
        status=status,
        started_at=now,
        finished_at=now,
        coverage=HistoricalSeasonCoverageResult(
            schedule_events_seen=30,
            final_games=30,
            final_games_with_boxscores=30,
            final_games_ingested=30,
            missing_boxscores=0,
            failed_boxscores=0,
            open_identity_issues=0,
            open_quality_issues=0,
            game_completeness="complete",
            game_coverage_window_id=start_year,
        ),
    )


def test_academic_seasons_between_is_inclusive_and_validated() -> None:
    assert academic_seasons_between("2021-22", "2023-24") == [
        "2021-22",
        "2022-23",
        "2023-24",
    ]
    with pytest.raises(ValueError, match="must end in 24"):
        academic_seasons_between("2023-25", "2024-25")
    with pytest.raises(ValueError, match="must not be later"):
        academic_seasons_between("2024-25", "2023-24")
    with pytest.raises(ValueError, match="limited to 10 seasons"):
        academic_seasons_between("2010-11", "2020-21")


async def test_range_backfill_runs_sequentially_and_checkpoints_each_season(
    client,
    db_session,
    monkeypatch,
) -> None:
    events: list[tuple[str, str | float]] = []

    async def fake_backfill(
        db,
        *,
        season,
        boxscore_delay_seconds,
        parent_range_run_id,
    ):
        events.append(("season", season))
        assert boxscore_delay_seconds == 0.25
        assert parent_range_run_id > 0
        return _season_result(season)

    async def fake_sleep(seconds: float) -> None:
        events.append(("sleep", seconds))

    monkeypatch.setattr(
        "app.services.historical_range_backfill.backfill_historical_wbb_season",
        fake_backfill,
    )
    monkeypatch.setattr(
        "app.services.historical_range_backfill.asyncio.sleep",
        fake_sleep,
    )

    response = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params={
            "start_season": "2022-23",
            "end_season": "2024-25",
            "boxscore_delay_seconds": 0.25,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["seasons_attempted"] == 3
    assert payload["seasons_skipped"] == 0
    assert [item["season"] for item in payload["seasons"]] == [
        "2022-23",
        "2023-24",
        "2024-25",
    ]
    assert events == [
        ("season", "2022-23"),
        ("sleep", 0.25),
        ("season", "2023-24"),
        ("sleep", 0.25),
        ("season", "2024-25"),
    ]
    run = await db_session.scalar(
        select(IngestRun).where(IngestRun.source_type == "historical_range_backfill")
    )
    assert run is not None
    assert run.status == "succeeded"
    assert run.run_metadata["season_order"] == [
        "2022-23",
        "2023-24",
        "2024-25",
    ]
    assert len(run.run_metadata["seasons"]) == 3
    assert run.run_metadata["last_checkpoint_at"]


async def test_range_backfill_continues_after_a_season_failure(
    client,
    monkeypatch,
) -> None:
    attempted: list[str] = []

    async def fake_backfill(
        db,
        *,
        season,
        boxscore_delay_seconds,
        parent_range_run_id,
    ):
        attempted.append(season)
        if season == "2023-24":
            raise RuntimeError("Unsupported historical table")
        return _season_result(season)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.historical_range_backfill.backfill_historical_wbb_season",
        fake_backfill,
    )
    monkeypatch.setattr(
        "app.services.historical_range_backfill.asyncio.sleep",
        fake_sleep,
    )

    response = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params={
            "start_season": "2022-23",
            "end_season": "2024-25",
            "boxscore_delay_seconds": 0.25,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert attempted == ["2022-23", "2023-24", "2024-25"]
    assert payload["status"] == "partial"
    assert payload["seasons_succeeded"] == 2
    assert payload["seasons_failed"] == 1
    failed = payload["seasons"][1]
    assert failed["status"] == "failed"
    assert failed["error_type"] == "RuntimeError"
    assert failed["error_message"] == "Unsupported historical table"


async def test_range_backfill_checkpoints_after_child_expires_parent_state(
    client,
    monkeypatch,
) -> None:
    async def fake_backfill(
        db,
        *,
        season,
        boxscore_delay_seconds,
        parent_range_run_id,
    ):
        db.expire_all()
        raise RuntimeError("Child transaction failed")

    monkeypatch.setattr(
        "app.services.historical_range_backfill.backfill_historical_wbb_season",
        fake_backfill,
    )

    response = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params={
            "start_season": "2023-24",
            "end_season": "2023-24",
            "boxscore_delay_seconds": 0.25,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["seasons_failed"] == 1
    assert payload["seasons"][0]["error_message"] == "Child transaction failed"


async def test_range_backfill_resume_retries_only_failed_seasons(
    client,
    db_session,
    monkeypatch,
) -> None:
    attempts: dict[str, int] = {}

    async def fake_backfill(
        db,
        *,
        season,
        boxscore_delay_seconds,
        parent_range_run_id,
    ):
        attempts[season] = attempts.get(season, 0) + 1
        if season == "2023-24" and attempts[season] == 1:
            raise RuntimeError("Temporary source failure")
        return _season_result(season)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(
        "app.services.historical_range_backfill.backfill_historical_wbb_season",
        fake_backfill,
    )
    monkeypatch.setattr(
        "app.services.historical_range_backfill.asyncio.sleep",
        fake_sleep,
    )
    params = {
        "start_season": "2022-23",
        "end_season": "2024-25",
        "boxscore_delay_seconds": 0.25,
    }

    first = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params=params,
    )
    run_id = first.json()["run_id"]
    second = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params={**params, "resume_run_id": run_id},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    payload = second.json()
    assert payload["run_id"] == run_id
    assert payload["resumed"] is True
    assert payload["status"] == "succeeded"
    assert payload["seasons_attempted"] == 1
    assert payload["seasons_skipped"] == 2
    assert attempts == {"2022-23": 1, "2023-24": 2, "2024-25": 1}
    run = await db_session.get(IngestRun, run_id)
    assert run is not None
    assert run.attempt_count == 2
    assert run.run_metadata["resume_count"] == 1
    assert run.run_metadata["seasons_failed"] == 0


async def test_range_backfill_rejects_other_sports(client) -> None:
    response = await client.post(
        "/api/v1/sources/football/historical-backfill",
        params={"start_season": "2022-23", "end_season": "2023-24"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Historical range backfill currently supports WBB only"
    )


async def test_range_backfill_rejects_an_overlapping_active_run(
    client,
    db_session,
) -> None:
    active = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type="historical_range_backfill",
        source_url=(
            "https://govandals.com/sports/womens-basketball/schedule"
            "?start=2022-23&end=2023-24"
        ),
        sport="womens-basketball",
        status="running",
        started_at=datetime.now(UTC),
        run_metadata={
            "start_season": "2022-23",
            "end_season": "2023-24",
            "seasons": [],
        },
    )
    db_session.add(active)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sources/womens-basketball/historical-backfill",
        params={"start_season": "2022-23", "end_season": "2023-24"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Historical range backfill run {active.id} is already active"
    )
