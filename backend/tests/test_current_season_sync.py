"""Tests for bounded, observable current-season WBB synchronization."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, IngestRun
from app.models.sport_program import SportProgram
from app.models.team import Team
from app.services.current_season_sync import (
    _open_identity_issue_count,
    sync_current_wbb_season,
)
from app.services.sidearm_roster import ParsedRoster, ParsedRosterPlayer
from app.services.sidearm_schedule import ParsedScheduleEvent
from app.services.sidearm_scraper import ParsedBoxscore

SEASON = "2025-26"
BOXSCORE_URL = (
    "https://govandals.com/sports/womens-basketball/stats/2025-26/"
    "idaho-state/boxscore/9968"
)


def _roster() -> ParsedRoster:
    return ParsedRoster(
        sport_program_slug="womens-basketball",
        season=SEASON,
        source_system="sidearm",
        institution="University of Idaho",
        team_slug="idaho",
        source_url=("https://govandals.com/sports/womens-basketball/roster/2025-26"),
        raw_html="<html>roster</html>",
        players=[
            ParsedRosterPlayer(
                display_name="Gardner, Kyra",
                jersey_number="3",
                class_year="Sr.",
                position="G",
                bio_url="https://govandals.com/roster/kyra-gardner/8435",
                source_player_id="8435",
            )
        ],
    )


def _schedule_event() -> ParsedScheduleEvent:
    return ParsedScheduleEvent(
        sport_slug="womens-basketball",
        sport_name="Women's Basketball",
        gender="women",
        season=SEASON,
        source_system="sidearm",
        schedule_url=(
            "https://govandals.com/sports/womens-basketball/schedule/2025-26"
        ),
        source_event_id="9968",
        opponent_source_id="212",
        opponent_name="Idaho State",
        event_status="final",
        home_away_neutral="home",
        event_date=date(2025, 11, 19),
        date_text="Nov 19 (Wed)",
        time_text="6 p.m.",
        location_name="Moscow, Idaho",
        venue_name="ICCU Arena",
        conference_name=None,
        conference_event=False,
        result_status="W",
        team_score=81,
        opponent_score=68,
        source_urls={"boxscore_html": BOXSCORE_URL},
    )


def _boxscore(
    home_score: int = 81,
    *,
    away_score: int = 68,
    home_team: str = "Idaho",
    away_team: str = "Idaho State",
) -> ParsedBoxscore:
    return ParsedBoxscore(
        source_url=BOXSCORE_URL,
        title=("Women's Basketball vs Idaho State on 11/19/2025 - Box Score"),
        sport="womens-basketball",
        season=SEASON,
        game_date="11/19/2025",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        raw_html=f"<html>boxscore-{home_score}</html>",
    )


async def _configure_sync_fakes(monkeypatch, event, scrape_calls) -> None:
    async def fake_discover_roster(
        sport_slug: str,
        season: str,
    ) -> ParsedRoster:
        assert sport_slug == "womens-basketball"
        assert season == SEASON
        return _roster()

    async def fake_discover_schedule(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        assert sport_slug == "womens-basketball"
        assert season == SEASON
        return [event]

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        scrape_calls.append(url)
        if event.home_away_neutral == "away":
            return _boxscore(
                event.opponent_score or 0,
                away_score=event.team_score or 0,
                home_team=event.opponent_name or "Opponent",
                away_team="Idaho",
            )
        return _boxscore(event.team_score or 0)

    monkeypatch.setattr(
        "app.services.current_season_sync.discover_roster",
        fake_discover_roster,
    )
    monkeypatch.setattr(
        "app.services.current_season_sync.discover_schedule_events",
        fake_discover_schedule,
    )
    monkeypatch.setattr(
        "app.services.game_ingest.scrape_boxscore",
        fake_scrape_boxscore,
    )


async def test_season_sync_ingests_new_finals_then_skips_unchanged_history(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    event = _schedule_event()
    scrape_calls: list[str] = []
    await _configure_sync_fakes(monkeypatch, event, scrape_calls)

    first = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )
    second = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "succeeded"
    assert first.json()["schedule_games_created"] == 1
    assert first.json()["boxscores_refreshed"] == 1
    assert first.json()["games"][0]["reasons"] == ["not_yet_ingested"]
    assert second.status_code == 200
    assert second.json()["schedule_games_unchanged"] == 1
    assert second.json()["boxscores_selected"] == 0
    assert second.json()["boxscores_skipped"] == 1
    assert scrape_calls == [BOXSCORE_URL]
    assert await db_session.scalar(select(func.count(Game.id))) == 1
    assert await db_session.scalar(select(func.count(IngestRun.id))) == 3


async def test_open_identity_count_excludes_opponent_players(db_session) -> None:
    await seed_warehouse_reference_data(db_session)
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    team = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    game = Game(
        source_url=BOXSCORE_URL,
        canonical_uid="sidearm:womens-basketball:2025-26:identity-scope",
        sport="womens-basketball",
        season=SEASON,
        event_status="final",
    )
    db_session.add(game)
    await db_session.flush()
    db_session.add_all(
        [
            DataQualityIssue(
                sport_program_id=program.id,
                game_id=game.id,
                team_id=team.id,
                issue_type="unresolved_identity",
                status="open",
                severity="warning",
                summary="Idaho player needs review",
                details={"season": SEASON, "institution": "University of Idaho"},
            ),
            DataQualityIssue(
                sport_program_id=program.id,
                game_id=game.id,
                issue_type="unresolved_identity",
                status="open",
                severity="warning",
                summary="Opponent player needs review",
                details={"season": SEASON, "institution": "Montana"},
            ),
        ]
    )
    await db_session.commit()

    count = await _open_identity_issue_count(
        db_session,
        [game.id],
        team_id=team.id,
        team_institutions=(team.canonical_name, team.institution),
    )

    assert count == 1


async def test_boxscore_refresh_preserves_schedule_owned_away_status(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    event = _schedule_event()
    event.home_away_neutral = "away"
    scrape_calls: list[str] = []
    await _configure_sync_fakes(monkeypatch, event, scrape_calls)

    first = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )
    second = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["schedule_games_unchanged"] == 1
    assert second.json()["boxscores_selected"] == 0
    assert scrape_calls == [BOXSCORE_URL]
    game = await db_session.scalar(select(Game))
    assert game is not None
    assert game.home_away_neutral == "away"
    assert game.home_team == "Idaho State"
    assert game.away_team == "Idaho"


async def test_season_sync_refreshes_a_changed_schedule_result(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    event = _schedule_event()
    scrape_calls: list[str] = []
    await _configure_sync_fakes(monkeypatch, event, scrape_calls)

    await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )
    event.team_score = 82
    response = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    assert response.status_code == 200
    assert response.json()["schedule_games_changed"] == 1
    assert response.json()["boxscores_refreshed"] == 1
    assert response.json()["games"][0]["reasons"] == ["schedule_changed"]
    assert scrape_calls == [BOXSCORE_URL, BOXSCORE_URL]
    game = await db_session.scalar(select(Game))
    assert game is not None
    assert game.home_score == 82


async def test_season_sync_reprocesses_after_an_identity_decision(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    event = _schedule_event()
    scrape_calls: list[str] = []
    await _configure_sync_fakes(monkeypatch, event, scrape_calls)
    await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    game = await db_session.scalar(select(Game))
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    assert game is not None
    assert program is not None
    db_session.add(
        DataQualityIssue(
            sport_program_id=program.id,
            game_id=game.id,
            deduplication_key="identity:test-resolved-after-ingest",
            issue_type="unresolved_identity",
            status="resolved",
            severity="warning",
            summary="SID resolved a player after the prior ingest",
            details={},
            resolved_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    assert response.status_code == 200
    assert response.json()["boxscores_refreshed"] == 1
    assert response.json()["games"][0]["reasons"] == ["identity_decision"]
    assert scrape_calls == [BOXSCORE_URL, BOXSCORE_URL]


async def test_season_sync_rejects_an_overlapping_active_run(
    client,
    db_session,
) -> None:
    active = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type="season_sync",
        source_url=("https://govandals.com/sports/womens-basketball/schedule/2025-26"),
        sport="womens-basketball",
        season=SEASON,
        status="running",
        started_at=datetime.now(UTC),
    )
    db_session.add(active)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Season sync run {active.id} is already in progress"
    )


async def test_parent_range_resume_reclaims_its_interrupted_season_run(
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    active = IngestRun(
        trigger_type="operator_sync",
        source_system="sidearm",
        source_type="season_sync",
        source_url=("https://govandals.com/sports/womens-basketball/schedule/2025-26"),
        sport="womens-basketball",
        season=SEASON,
        status="running",
        started_at=datetime.now(UTC),
        run_metadata={"parent_range_run_id": 44},
    )
    db_session.add(active)
    await db_session.commit()
    scrape_calls: list[str] = []
    await _configure_sync_fakes(monkeypatch, _schedule_event(), scrape_calls)

    result = await sync_current_wbb_season(
        db_session,
        season=SEASON,
        correction_lookback=0,
        parent_range_run_id=44,
    )

    await db_session.refresh(active)
    resumed = await db_session.get(IngestRun, result.run_id)
    assert active.status == "failed"
    assert active.error_type == "InterruptedHistoricalRangeSeason"
    assert active.run_metadata["reclaimed_by_parent_resume"] is True
    assert resumed is not None
    assert resumed.status == "succeeded"
    assert resumed.run_metadata["parent_range_run_id"] == 44
    assert scrape_calls == [BOXSCORE_URL]


async def test_season_sync_returns_partial_evidence_when_one_boxscore_fails(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    first_event = _schedule_event()
    second_event = _schedule_event()
    second_event.source_event_id = "9969"
    second_event.opponent_name = "Montana"
    second_event.event_date = date(2025, 11, 22)
    second_url = (
        "https://govandals.com/sports/womens-basketball/stats/2025-26/"
        "montana/boxscore/9969"
    )
    second_event.source_urls = {"boxscore_html": second_url}

    async def fake_discover_roster(
        sport_slug: str,
        season: str,
    ) -> ParsedRoster:
        return _roster()

    async def fake_discover_schedule(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        return [first_event, second_event]

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        if url == second_url:
            raise ValueError("Unsupported corrected boxscore structure")
        return _boxscore()

    monkeypatch.setattr(
        "app.services.current_season_sync.discover_roster",
        fake_discover_roster,
    )
    monkeypatch.setattr(
        "app.services.current_season_sync.discover_schedule_events",
        fake_discover_schedule,
    )
    monkeypatch.setattr(
        "app.services.game_ingest.scrape_boxscore",
        fake_scrape_boxscore,
    )

    response = await client.post(
        f"/api/v1/sources/womens-basketball/seasons/{SEASON}/sync",
        params={"correction_lookback": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["boxscores_refreshed"] == 1
    assert payload["boxscores_failed"] == 1
    assert [game["status"] for game in payload["games"]] == [
        "refreshed",
        "failed",
    ]
    assert payload["games"][1]["error"] == ("Unsupported corrected boxscore structure")
    sync_run = await db_session.scalar(
        select(IngestRun).where(IngestRun.source_type == "season_sync")
    )
    assert sync_run is not None
    assert sync_run.status == "partial"
    assert sync_run.run_metadata["boxscores_failed"] == 1


async def test_season_sync_paces_selected_boxscores(
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    first_event = _schedule_event()
    second_event = _schedule_event()
    second_event.source_event_id = "9969"
    second_event.opponent_name = "Montana"
    second_event.event_date = date(2025, 11, 22)
    second_url = (
        "https://govandals.com/sports/womens-basketball/stats/2025-26/"
        "montana/boxscore/9969"
    )
    second_event.source_urls = {"boxscore_html": second_url}
    events: list[tuple[str, str | float]] = []

    async def fake_discover_roster(sport_slug: str, season: str) -> ParsedRoster:
        return _roster()

    async def fake_discover_schedule(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        return [first_event, second_event]

    async def fake_ingest_boxscore(db, url, **kwargs):
        events.append(("boxscore", url))
        return SimpleNamespace(id=len(events), title=f"Boxscore {url}")

    async def fake_sleep(seconds: float) -> None:
        events.append(("sleep", seconds))

    monkeypatch.setattr(
        "app.services.current_season_sync.discover_roster",
        fake_discover_roster,
    )
    monkeypatch.setattr(
        "app.services.current_season_sync.discover_schedule_events",
        fake_discover_schedule,
    )
    monkeypatch.setattr(
        "app.services.current_season_sync.ingest_boxscore",
        fake_ingest_boxscore,
    )
    monkeypatch.setattr(
        "app.services.current_season_sync.asyncio.sleep",
        fake_sleep,
    )

    result = await sync_current_wbb_season(
        db_session,
        season=SEASON,
        correction_lookback=0,
        boxscore_delay_seconds=0.5,
    )

    assert result.boxscores_refreshed == 2
    assert events == [
        ("boxscore", BOXSCORE_URL),
        ("sleep", 0.5),
        ("boxscore", second_url),
    ]
