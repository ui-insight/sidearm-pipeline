"""Tests for Sidearm cumulative-season statistics parsing."""

from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.services.sidearm_cumulative_stats import (
    discover_cumulative_stats,
    parse_cumulative_stats,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SOURCE_URL = "https://govandals.com/sports/womens-basketball/stats/2025-26"


def test_parse_cumulative_stats_preserves_atomic_totals_and_identity() -> None:
    html = (FIXTURE_DIR / "womens_basketball_cumulative_2025_26.html").read_text(
        encoding="utf-8"
    )

    season_stats = parse_cumulative_stats(
        html,
        sport_program_slug="womens-basketball",
        source_url=SOURCE_URL,
    )

    assert season_stats.season == "2025-26"
    assert season_stats.source_system == "govandals_public_html"
    assert season_stats.identity_source_system == "sidearm"
    assert len(season_stats.players) == 4
    hope = season_stats.players[0]
    assert hope.display_name == "Hassmann, Hope"
    assert hope.jersey_number == "04"
    assert hope.source_player_id == "8430"
    assert hope.bio_url == (
        "https://govandals.com/sports/womens-basketball/roster/hope-hassmann/8430"
    )
    assert hope.games_played == 35
    assert hope.stats["minutes_played"] == Decimal("1042")
    assert hope.stats["field_goals_made"] == Decimal("168")
    assert hope.stats["field_goals_attempted"] == Decimal("426")
    assert hope.stats["three_point_field_goals_made"] == Decimal("47")
    assert hope.stats["free_throws_made"] == Decimal("113")
    assert hope.stats["total_rebounds"] == Decimal("127")
    assert hope.stats["points"] == Decimal("496")
    assert "field_goal_percentage" not in hope.stats
    assert hope.source_fields["free_throws_made"] == "FT"
    assert [player.source_player_id for player in season_stats.players[-2:]] == [
        "8437",
        "8437",
    ]


async def test_discover_cumulative_stats_uses_registered_source(
    monkeypatch,
) -> None:
    html = (FIXTURE_DIR / "womens_basketball_cumulative_2025_26.html").read_text(
        encoding="utf-8"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sports/womens-basketball/stats/2025-26"
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.sidearm_cumulative_stats.httpx.AsyncClient", mock_client
    )

    season_stats = await discover_cumulative_stats("womens-basketball", "2025-26")

    assert season_stats.source_url == SOURCE_URL
    assert season_stats.http_status == 200
    assert season_stats.players[1].source_player_id == "8435"


def test_parse_cumulative_stats_rejects_silent_markup_drift() -> None:
    with pytest.raises(ValueError, match="Overall Individual Statistics"):
        parse_cumulative_stats(
            "<html><title>2025-26 Women's Basketball Stats</title></html>",
            sport_program_slug="womens-basketball",
            source_url=SOURCE_URL,
        )
