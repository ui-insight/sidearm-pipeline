"""Tests for Sidearm schedule parsing."""

from datetime import date
from pathlib import Path

import pytest

from app.services.sidearm_schedule import discover_schedule_events, parse_schedule
from app.services.source_registry import get_source_registry

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_schedule_extracts_final_and_upcoming_events() -> None:
    registry = get_source_registry()
    sport = registry.require_sport("football")
    html = (FIXTURE_DIR / "football_schedule_2025.html").read_text(encoding="utf-8")

    events = parse_schedule(
        html,
        sport=sport,
        schedule_url="https://govandals.com/sports/football/schedule/2025",
    )

    assert len(events) == 3

    opener = events[0]
    assert opener.source_event_id == "8460"
    assert opener.opponent_source_id == "107"
    assert opener.opponent_name == "Washington State"
    assert opener.home_away_neutral == "away"
    assert opener.event_status == "final"
    assert opener.event_date == date(2025, 8, 30)
    assert opener.date_text == "Aug 30 (Sat)"
    assert opener.time_text == "7 p.m."
    assert opener.location_name == "Pullman, Wash."
    assert opener.venue_name is None
    assert opener.result_status == "L"
    assert opener.team_score == 10
    assert opener.opponent_score == 13
    assert opener.boxscore_url == (
        "https://govandals.com/sports/football/stats/2025/"
        "washington-state/boxscore/8460"
    )
    assert opener.source_urls["recap_html"].endswith("season-opener.aspx")

    uc_davis = events[1]
    assert uc_davis.source_event_id == "8467"
    assert uc_davis.opponent_name == "UC Davis"
    assert uc_davis.home_away_neutral == "home"
    assert uc_davis.location_name == "Moscow, Idaho"
    assert uc_davis.venue_name == "P1FCU Kibbie Dome"
    assert uc_davis.conference_name == "Big Sky"
    assert uc_davis.conference_event is True
    assert uc_davis.team_score == 14
    assert uc_davis.opponent_score == 28
    assert "gamefile" in uc_davis.source_urls

    upcoming = events[2]
    assert upcoming.source_event_id == "10652"
    assert upcoming.event_status == "scheduled"
    assert upcoming.team_score is None
    assert upcoming.source_urls["live_stats"] == (
        "https://govandals.com/sidearmstats/football/summary"
    )


async def test_discover_schedule_events_uses_registry_and_fetcher(monkeypatch) -> None:
    html = (FIXTURE_DIR / "football_schedule_2025.html").read_text(encoding="utf-8")
    seen_urls: list[str] = []

    async def fake_fetch_schedule(url: str) -> str:
        seen_urls.append(url)
        return html

    monkeypatch.setattr(
        "app.services.sidearm_schedule.fetch_schedule",
        fake_fetch_schedule,
    )

    events = await discover_schedule_events("football")

    assert seen_urls == ["https://govandals.com/sports/football/schedule"]
    assert [event.source_event_id for event in events] == ["8460", "8467", "10652"]


async def test_discover_schedule_events_can_target_season(monkeypatch) -> None:
    html = (FIXTURE_DIR / "football_schedule_2025.html").read_text(encoding="utf-8")
    seen_urls: list[str] = []

    async def fake_fetch_schedule(url: str) -> str:
        seen_urls.append(url)
        return html

    monkeypatch.setattr(
        "app.services.sidearm_schedule.fetch_schedule",
        fake_fetch_schedule,
    )

    events = await discover_schedule_events("football", season="2025")

    assert seen_urls == ["https://govandals.com/sports/football/schedule/2025"]
    assert events[0].season == "2025"


async def test_discover_schedule_events_can_target_academic_year(
    monkeypatch,
) -> None:
    html = (FIXTURE_DIR / "mens_basketball_schedule_2025_26.html").read_text(
        encoding="utf-8"
    )
    seen_urls: list[str] = []

    async def fake_fetch_schedule(url: str) -> str:
        seen_urls.append(url)
        return html

    monkeypatch.setattr(
        "app.services.sidearm_schedule.fetch_schedule",
        fake_fetch_schedule,
    )

    events = await discover_schedule_events("mens-basketball", season="2025-26")

    assert seen_urls == [
        "https://govandals.com/sports/mens-basketball/schedule/2025-26"
    ]
    assert events[0].season == "2025-26"
    assert events[0].event_date == date(2025, 11, 3)
    assert events[1].event_date == date(2026, 1, 15)


@pytest.mark.parametrize(
    (
        "sport_slug",
        "fixture_name",
        "schedule_url",
        "expected_event_id",
        "expected_season",
        "expected_date",
        "expected_result",
        "expected_score",
        "expected_boxscore_url",
    ),
    [
        (
            "mens-basketball",
            "mens_basketball_schedule_2025_26.html",
            "https://govandals.com/sports/mens-basketball/schedule/2025-26",
            "10050",
            "2025-26",
            date(2026, 1, 15),
            "L",
            (68, 76),
            "https://govandals.com/sports/mens-basketball/stats/2025-26/"
            "idaho-state/boxscore/10050",
        ),
        (
            "womens-basketball",
            "womens_basketball_schedule_2025_26.html",
            "https://govandals.com/sports/womens-basketball/schedule/2025-26",
            "9968",
            "2025-26",
            date(2026, 1, 15),
            "W",
            (81, 61),
            "https://govandals.com/sports/womens-basketball/stats/2025-26/"
            "idaho-state/boxscore/9968",
        ),
        (
            "womens-soccer",
            "womens_soccer_schedule_2025.html",
            "https://govandals.com/sports/womens-soccer/schedule/2025",
            "9126",
            "2025",
            date(2025, 9, 25),
            "T",
            (0, 0),
            "https://govandals.com/sports/womens-soccer/stats/2025/"
            "idaho-state/boxscore/9126",
        ),
        (
            "womens-volleyball",
            "womens_volleyball_schedule_2025.html",
            "https://govandals.com/sports/womens-volleyball/schedule/2025",
            "9105",
            "2025",
            date(2025, 10, 9),
            "L",
            (1, 3),
            "https://govandals.com/sports/womens-volleyball/stats/2025/"
            "idaho-state/boxscore/9105",
        ),
    ],
)
def test_parse_release_one_sport_schedule_fixtures(
    sport_slug: str,
    fixture_name: str,
    schedule_url: str,
    expected_event_id: str,
    expected_season: str,
    expected_date: date,
    expected_result: str,
    expected_score: tuple[int, int],
    expected_boxscore_url: str,
) -> None:
    registry = get_source_registry()
    sport = registry.require_sport(sport_slug)
    html = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")

    events = parse_schedule(html, sport=sport, schedule_url=schedule_url)
    event = next(
        parsed for parsed in events if parsed.source_event_id == expected_event_id
    )

    assert event.season == expected_season
    assert event.opponent_name == "Idaho State"
    assert event.event_status == "final"
    assert event.event_date == expected_date
    assert event.conference_name == "Big Sky"
    assert event.conference_event is True
    assert event.result_status == expected_result
    assert (event.team_score, event.opponent_score) == expected_score
    assert event.boxscore_url == expected_boxscore_url


async def test_discover_schedule_events_rejects_invalid_season() -> None:
    with pytest.raises(ValueError, match="Season must be a four-digit year"):
        await discover_schedule_events("football", season="latest")


async def test_discover_schedule_events_rejects_unregistered_sport() -> None:
    with pytest.raises(KeyError, match="No source registry entry"):
        await discover_schedule_events("baseball")
