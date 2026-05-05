"""Tests for the background scheduler ingest cycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services.scheduler import run_ingest_cycle
from app.services.sidearm_schedule import ParsedScheduleEvent


def _make_event(
    *,
    event_status: str = "final",
    boxscore_url: str | None = "https://govandals.com/sports/football/stats/2025/opp/boxscore/1",
    sport_slug: str = "football",
) -> ParsedScheduleEvent:
    """Build a minimal ParsedScheduleEvent for testing."""
    source_urls: dict[str, str] = {}
    if boxscore_url:
        source_urls["boxscore_html"] = boxscore_url

    return ParsedScheduleEvent(
        sport_slug=sport_slug,
        sport_name="Football",
        gender=None,
        season="2025",
        source_system="sidearm",
        schedule_url="https://govandals.com/sports/football/schedule/2025",
        source_event_id="1",
        opponent_source_id=None,
        opponent_name="Opponent",
        event_status=event_status,
        home_away_neutral="home",
        event_date=date(2025, 9, 6),
        date_text="Sep 6",
        time_text="3:00 PM",
        location_name="Moscow, ID",
        venue_name="Kibbie Dome",
        conference_name=None,
        conference_event=False,
        result_status="W" if event_status == "final" else None,
        team_score=35 if event_status == "final" else None,
        opponent_score=14 if event_status == "final" else None,
        source_urls=source_urls,
    )


@pytest.mark.asyncio
async def test_run_ingest_cycle_ingests_finals(test_session_factory):
    """Scheduler calls ingest for every final event that has a boxscore URL."""
    events = [_make_event(event_status="final")]

    with (
        patch(
            "app.services.scheduler.discover_schedule_events",
            new=AsyncMock(return_value=events),
        ),
        patch(
            "app.services.scheduler.ingest_boxscore_url",
            new=AsyncMock(),
        ) as mock_ingest,
    ):
        await run_ingest_cycle(test_session_factory)

    # One Release-1 sport provides one final event → one ingest call
    assert mock_ingest.call_count >= 1
    called_urls = {call.args[0] for call in mock_ingest.call_args_list}
    assert events[0].boxscore_url in called_urls

    # All calls must use trigger_type="scheduled"
    for call in mock_ingest.call_args_list:
        assert call.kwargs.get("trigger_type") == "scheduled"


@pytest.mark.asyncio
async def test_run_ingest_cycle_skips_non_finals(test_session_factory):
    """Scheduler does not ingest events that are not yet finalized."""
    events = [
        _make_event(event_status="scheduled"),
        _make_event(event_status="postponed"),
    ]

    with (
        patch(
            "app.services.scheduler.discover_schedule_events",
            new=AsyncMock(return_value=events),
        ),
        patch(
            "app.services.scheduler.ingest_boxscore_url",
            new=AsyncMock(),
        ) as mock_ingest,
    ):
        await run_ingest_cycle(test_session_factory)

    assert mock_ingest.call_count == 0


@pytest.mark.asyncio
async def test_run_ingest_cycle_skips_no_boxscore_url(test_session_factory):
    """Scheduler skips final events that have no boxscore URL yet."""
    events = [_make_event(event_status="final", boxscore_url=None)]

    with (
        patch(
            "app.services.scheduler.discover_schedule_events",
            new=AsyncMock(return_value=events),
        ),
        patch(
            "app.services.scheduler.ingest_boxscore_url",
            new=AsyncMock(),
        ) as mock_ingest,
    ):
        await run_ingest_cycle(test_session_factory)

    assert mock_ingest.call_count == 0


@pytest.mark.asyncio
async def test_run_ingest_cycle_continues_on_discovery_error(test_session_factory):
    """A schedule discovery failure does not abort the rest of the cycle."""
    with (
        patch(
            "app.services.scheduler.discover_schedule_events",
            new=AsyncMock(side_effect=Exception("network error")),
        ),
        patch(
            "app.services.scheduler.ingest_boxscore_url",
            new=AsyncMock(),
        ) as mock_ingest,
    ):
        # Should not raise even though discovery always fails
        await run_ingest_cycle(test_session_factory)

    assert mock_ingest.call_count == 0


@pytest.mark.asyncio
async def test_run_ingest_cycle_continues_on_ingest_error(test_session_factory):
    """A single ingest failure does not abort ingestion of remaining games."""
    football_events = [
        _make_event(
            event_status="final",
            boxscore_url="https://govandals.com/sports/football/stats/2025/a/boxscore/1",
        ),
        _make_event(
            event_status="final",
            boxscore_url="https://govandals.com/sports/football/stats/2025/b/boxscore/2",
        ),
    ]

    call_count = 0

    async def flaky_ingest(url, db, *, trigger_type):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("fetch failed")

    async def discovery_by_sport(sport_slug, season=None):
        # Only return events for football; all other sports return empty schedule
        if sport_slug == "football":
            return football_events
        return []

    with (
        patch(
            "app.services.scheduler.discover_schedule_events",
            new=discovery_by_sport,
        ),
        patch(
            "app.services.scheduler.ingest_boxscore_url",
            new=flaky_ingest,
        ),
    ):
        await run_ingest_cycle(test_session_factory)

    # Both football events were attempted; second succeeded even after first failed
    assert call_count == 2
