"""Tests for Sidearm roster parsing and redirect identity discovery."""

from pathlib import Path

import httpx
import pytest

from app.services.sidearm_roster import (
    discover_roster,
    parse_roster,
    source_player_id_from_url,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("fixture_name", "season", "expected_ids"),
    [
        (
            "womens_basketball_roster_2024_25.html",
            "2024-25",
            ["7988", None],
        ),
        (
            "womens_basketball_roster_2025_26.html",
            "2025-26",
            ["8428", "8435"],
        ),
    ],
)
def test_parse_roster_supports_sidearm_cards_and_accessible_table(
    fixture_name: str,
    season: str,
    expected_ids: list[str | None],
) -> None:
    source_url = "https://govandals.com/sports/womens-basketball/roster/" + season
    html = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")

    roster = parse_roster(
        html,
        sport_program_slug="womens-basketball",
        source_url=source_url,
    )

    assert roster.season == season
    assert roster.source_url == source_url
    assert roster.institution == "University of Idaho"
    assert roster.team_slug == "idaho"
    assert [player.source_player_id for player in roster.players] == expected_ids
    assert roster.players[0].display_name == "Sarah Brans"
    assert roster.players[0].jersey_number == "2"
    assert roster.players[0].position == "F"


async def test_discover_roster_records_authoritative_bio_redirect(
    monkeypatch,
) -> None:
    html = (FIXTURE_DIR / "womens_basketball_roster_2024_25.html").read_text(
        encoding="utf-8"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/roster/2024-25"):
            return httpx.Response(200, text=html, request=request)
        if request.url.path.endswith("/sarah-brans/7988"):
            return httpx.Response(
                302,
                headers={
                    "Location": (
                        "https://govandals.com/sports/womens-basketball/"
                        "roster/sarah-brans/8428"
                    )
                },
                request=request,
            )
        if request.url.path.endswith("/sarah-brans/8428"):
            return httpx.Response(200, request=request)
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def mock_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr("app.services.sidearm_roster.httpx.AsyncClient", mock_client)

    roster = await discover_roster("womens-basketball", "2024-25")

    sarah = roster.players[0]
    assert sarah.source_player_id == "7988"
    assert sarah.canonical_source_player_id == "8428"
    assert sarah.identity_resolution_error is None
    assert roster.players[1].source_player_id is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://govandals.com/sports/womens-basketball/roster/sarah-brans/8428",
            "8428",
        ),
        ("https://example.edu/roster/player/not-a-number", None),
    ],
)
def test_source_player_id_from_url(url: str, expected: str | None) -> None:
    assert source_player_id_from_url(url) == expected


def test_parse_roster_rejects_silent_markup_drift() -> None:
    with pytest.raises(ValueError, match="No Sidearm roster player rows"):
        parse_roster(
            "<html><title>2025-26 Women's Basketball Roster</title></html>",
            sport_program_slug="womens-basketball",
            source_url=(
                "https://govandals.com/sports/womens-basketball/roster/2025-26"
            ),
        )
