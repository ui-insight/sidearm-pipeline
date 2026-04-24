"""Tests for source discovery API endpoints."""

from datetime import date

from app.services.sidearm_schedule import ParsedScheduleEvent


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
