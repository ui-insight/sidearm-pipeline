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


async def test_discover_schedule_events_rejects_unregistered_sport() -> None:
    with pytest.raises(KeyError, match="No source registry entry"):
        await discover_schedule_events("baseball")
