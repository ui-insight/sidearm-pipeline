"""Tests for source discovery API endpoints."""

from datetime import date

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.game import EventSource, Game
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.services.sidearm_roster import ParsedRoster, ParsedRosterPlayer
from app.services.sidearm_schedule import ParsedScheduleEvent
from app.services.sidearm_scraper import ParsedBoxscore


def _discovered_roster() -> ParsedRoster:
    return ParsedRoster(
        sport_program_slug="womens-basketball",
        season="2025-26",
        source_system="sidearm",
        institution="University of Idaho",
        team_slug="idaho",
        source_url=("https://govandals.com/sports/womens-basketball/roster/2025-26"),
        raw_html="<html>roster</html>",
        players=[
            ParsedRosterPlayer(
                display_name="Sarah Brans",
                jersey_number="2",
                class_year="Sr.",
                position="F",
                bio_url=(
                    "https://govandals.com/sports/womens-basketball/roster/"
                    "sarah-brans/8428"
                ),
                source_player_id="8428",
                canonical_bio_url=(
                    "https://govandals.com/sports/womens-basketball/roster/"
                    "sarah-brans/8428"
                ),
            )
        ],
    )


async def test_preview_roster_discovery_returns_namespaced_identity_fields(
    client,
    monkeypatch,
) -> None:
    async def fake_discover_roster(
        sport_slug: str,
        season: str,
    ) -> ParsedRoster:
        assert sport_slug == "womens-basketball"
        assert season == "2025-26"
        return _discovered_roster()

    monkeypatch.setattr(
        "app.api.v1.sources.discover_roster",
        fake_discover_roster,
    )

    response = await client.get(
        "/api/v1/sources/womens-basketball/roster?season=2025-26"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "display_name": "Sarah Brans",
            "jersey_number": "2",
            "class_year": "Sr.",
            "position": "F",
            "bio_url": (
                "https://govandals.com/sports/womens-basketball/roster/sarah-brans/8428"
            ),
            "source_player_id": "8428",
            "canonical_bio_url": (
                "https://govandals.com/sports/womens-basketball/roster/sarah-brans/8428"
            ),
            "canonical_source_player_id": "8428",
            "identity_resolution_error": None,
        }
    ]


async def test_import_roster_discovery_persists_canonical_identity(
    client,
    db_session,
    monkeypatch,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()

    async def fake_discover_roster(
        sport_slug: str,
        season: str,
    ) -> ParsedRoster:
        return _discovered_roster()

    monkeypatch.setattr(
        "app.api.v1.sources.discover_roster",
        fake_discover_roster,
    )

    response = await client.post(
        "/api/v1/sources/womens-basketball/roster/import?season=2025-26"
    )

    assert response.status_code == 201
    assert response.json() == {
        "source_url": ("https://govandals.com/sports/womens-basketball/roster/2025-26"),
        "season": "2025-26",
        "source_snapshot_id": 1,
        "players_seen": 1,
        "players_created": 1,
        "identities_created": 1,
        "player_seasons_created": 1,
        "player_seasons_updated": 0,
        "quality_issues_created": 0,
    }
    assert await db_session.scalar(select(func.count(Player.id))) == 1
    assert await db_session.scalar(select(func.count(PlayerExternalIdentity.id))) == 1
    assert await db_session.scalar(select(func.count(PlayerSeason.id))) == 1


async def test_preview_schedule_discovery_returns_events(client, monkeypatch) -> None:
    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        assert sport_slug == "football"
        assert season is None
        return [
            ParsedScheduleEvent(
                sport_slug="football",
                sport_name="Football",
                gender=None,
                season="2025",
                source_system="sidearm",
                schedule_url="https://govandals.com/sports/football/schedule",
                source_event_id="8467",
                opponent_source_id="174",
                opponent_name="UC Davis",
                event_status="final",
                home_away_neutral="home",
                event_date=date(2025, 11, 8),
                date_text="Nov 8 (Sat)",
                time_text="4 p.m.",
                location_name="Moscow, Idaho",
                venue_name="P1FCU Kibbie Dome",
                conference_name="Big Sky",
                conference_event=True,
                result_status="L",
                team_score=14,
                opponent_score=28,
                source_urls={
                    "boxscore_html": "https://govandals.com/sports/football/"
                    "stats/2025/uc-davis/boxscore/8467"
                },
            )
        ]

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    response = await client.get("/api/v1/sources/football/schedule")

    assert response.status_code == 200
    assert response.json() == [
        {
            "sport_slug": "football",
            "sport_name": "Football",
            "gender": None,
            "season": "2025",
            "source_system": "sidearm",
            "schedule_url": "https://govandals.com/sports/football/schedule",
            "source_event_id": "8467",
            "opponent_source_id": "174",
            "opponent_name": "UC Davis",
            "event_status": "final",
            "home_away_neutral": "home",
            "event_date": "2025-11-08",
            "date_text": "Nov 8 (Sat)",
            "time_text": "4 p.m.",
            "location_name": "Moscow, Idaho",
            "venue_name": "P1FCU Kibbie Dome",
            "conference_name": "Big Sky",
            "conference_event": True,
            "result_status": "L",
            "team_score": 14,
            "opponent_score": 28,
            "source_urls": {
                "boxscore_html": "https://govandals.com/sports/football/"
                "stats/2025/uc-davis/boxscore/8467"
            },
            "boxscore_url": "https://govandals.com/sports/football/stats/"
            "2025/uc-davis/boxscore/8467",
        }
    ]


async def test_preview_schedule_discovery_accepts_season(client, monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        seen["sport_slug"] = sport_slug
        seen["season"] = season
        return []

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    response = await client.get("/api/v1/sources/football/schedule?season=2025")

    assert response.status_code == 200
    assert response.json() == []
    assert seen == {"sport_slug": "football", "season": "2025"}


async def test_preview_schedule_discovery_rejects_invalid_season(
    client,
    monkeypatch,
) -> None:
    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        raise ValueError(
            "Season must be a four-digit year or academic year like 2025-26"
        )

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    response = await client.get("/api/v1/sources/football/schedule?season=latest")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Season must be a four-digit year or academic year like 2025-26"
    )


async def test_preview_schedule_discovery_rejects_unknown_sport(
    client,
    monkeypatch,
) -> None:
    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        raise KeyError(f"No source registry entry for sport '{sport_slug}'")

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    response = await client.get("/api/v1/sources/baseball/schedule")

    assert response.status_code == 404
    assert "No source registry entry" in response.json()["detail"]


async def test_import_schedule_discovery_persists_canonical_games(
    client,
    db_session,
    monkeypatch,
) -> None:
    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        assert sport_slug == "football"
        assert season == "2025"
        return [
            ParsedScheduleEvent(
                sport_slug="football",
                sport_name="Football",
                gender=None,
                season="2025",
                source_system="sidearm",
                schedule_url="https://govandals.com/sports/football/schedule/2025",
                source_event_id="8467",
                opponent_source_id="174",
                opponent_name="UC Davis",
                event_status="final",
                home_away_neutral="home",
                event_date=date(2025, 11, 8),
                date_text="Nov 8 (Sat)",
                time_text="4 p.m.",
                location_name="Moscow, Idaho",
                venue_name="P1FCU Kibbie Dome",
                conference_name="Big Sky",
                conference_event=True,
                result_status="L",
                team_score=14,
                opponent_score=28,
                source_urls={
                    "boxscore_html": "https://govandals.com/sports/football/"
                    "stats/2025/uc-davis/boxscore/8467",
                    "live_stats": "https://govandals.com/sidearmstats/football/summary",
                },
            ),
            ParsedScheduleEvent(
                sport_slug="football",
                sport_name="Football",
                gender=None,
                season="2025",
                source_system="sidearm",
                schedule_url="https://govandals.com/sports/football/schedule/2025",
                source_event_id="10652",
                opponent_source_id="220",
                opponent_name="Montana",
                event_status="scheduled",
                home_away_neutral="away",
                event_date=date(2025, 11, 15),
                date_text="Nov 15 (Sat)",
                time_text="1 p.m.",
                location_name="Missoula, Mont.",
                venue_name="Washington-Grizzly Stadium",
                conference_name="Big Sky",
                conference_event=True,
                result_status=None,
                team_score=None,
                opponent_score=None,
                source_urls={
                    "live_stats": "https://govandals.com/sidearmstats/football/summary"
                },
            ),
        ]

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    response = await client.post("/api/v1/sources/football/schedule/import?season=2025")

    assert response.status_code == 201
    payload = response.json()
    assert [game["canonical_uid"] for game in payload] == [
        "sidearm:football:2025:8467",
        "sidearm:football:2025:10652",
    ]
    assert payload[0]["source_url"].endswith("/boxscore/8467")
    assert payload[0]["home_team"] == "Idaho"
    assert payload[0]["away_team"] == "UC Davis"
    assert payload[0]["home_score"] == 14
    assert payload[0]["away_score"] == 28
    assert payload[1]["source_url"].endswith("#game-10652")
    assert payload[1]["home_team"] == "Montana"
    assert payload[1]["away_team"] == "Idaho"
    assert payload[1]["event_status"] == "scheduled"

    game_count = await db_session.scalar(select(func.count()).select_from(Game))
    assert game_count == 2

    source_rows = (
        await db_session.scalars(
            select(EventSource)
            .join(Game)
            .where(Game.canonical_uid == "sidearm:football:2025:8467")
            .order_by(EventSource.source_type)
        )
    ).all()
    assert [row.source_type for row in source_rows] == [
        "boxscore_html",
        "live_stats",
        "schedule_html",
    ]
    assert any(
        row.primary_source for row in source_rows if row.source_type == "boxscore_html"
    )


async def test_import_schedule_discovery_is_idempotent(
    client,
    db_session,
    monkeypatch,
) -> None:
    events = [
        ParsedScheduleEvent(
            sport_slug="football",
            sport_name="Football",
            gender=None,
            season="2025",
            source_system="sidearm",
            schedule_url="https://govandals.com/sports/football/schedule/2025",
            source_event_id="8467",
            opponent_source_id="174",
            opponent_name="UC Davis",
            event_status="scheduled",
            home_away_neutral="home",
            event_date=date(2025, 11, 8),
            date_text="Nov 8 (Sat)",
            time_text="4 p.m.",
            location_name="Moscow, Idaho",
            venue_name="P1FCU Kibbie Dome",
            conference_name="Big Sky",
            conference_event=True,
            result_status=None,
            team_score=None,
            opponent_score=None,
            source_urls={},
        )
    ]

    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        return events

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )

    first_response = await client.post("/api/v1/sources/football/schedule/import")
    events[0].event_status = "final"
    events[0].team_score = 31
    events[0].opponent_score = 28
    second_response = await client.post("/api/v1/sources/football/schedule/import")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()[0]["id"] == first_response.json()[0]["id"]
    assert second_response.json()[0]["event_status"] == "final"
    assert second_response.json()[0]["home_score"] == 31

    game_count = await db_session.scalar(select(func.count()).select_from(Game))
    assert game_count == 1


async def test_schedule_imported_game_is_refreshed_by_boxscore_ingest(
    client,
    db_session,
    monkeypatch,
) -> None:
    boxscore_url = (
        "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
    )

    async def fake_discover_schedule_events(
        sport_slug: str,
        season: str | None = None,
    ) -> list[ParsedScheduleEvent]:
        return [
            ParsedScheduleEvent(
                sport_slug="football",
                sport_name="Football",
                gender=None,
                season="2025",
                source_system="sidearm",
                schedule_url="https://govandals.com/sports/football/schedule/2025",
                source_event_id="8467",
                opponent_source_id="174",
                opponent_name="UC Davis",
                event_status="scheduled",
                home_away_neutral="home",
                event_date=date(2025, 11, 8),
                date_text="Nov 8 (Sat)",
                time_text="4 p.m.",
                location_name="Moscow, Idaho",
                venue_name="P1FCU Kibbie Dome",
                conference_name="Big Sky",
                conference_event=True,
                result_status=None,
                team_score=None,
                opponent_score=None,
                source_urls={"boxscore_html": boxscore_url},
            )
        ]

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        return ParsedBoxscore(
            source_url=url,
            title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
            sport="football",
            season="2025",
            game_date="11/8/2025",
            home_team="Idaho",
            away_team="UC Davis",
            home_score=31,
            away_score=28,
            raw_html="<html>boxscore</html>",
        )

    monkeypatch.setattr(
        "app.api.v1.sources.discover_schedule_events",
        fake_discover_schedule_events,
    )
    monkeypatch.setattr("app.api.v1.games.scrape_boxscore", fake_scrape_boxscore)

    import_response = await client.post("/api/v1/sources/football/schedule/import")
    imported_game_id = import_response.json()[0]["id"]
    ingest_response = await client.post("/api/v1/games", json={"url": boxscore_url})

    assert ingest_response.status_code == 201
    payload = ingest_response.json()
    assert payload["id"] == imported_game_id
    assert payload["event_status"] == "final"
    assert payload["home_score"] == 31

    game_count = await db_session.scalar(select(func.count()).select_from(Game))
    assert game_count == 1
