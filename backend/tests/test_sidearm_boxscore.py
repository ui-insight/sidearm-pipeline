"""Tests for Sidearm boxscore parsing across Release 1 sports."""

from pathlib import Path

import httpx
import pytest

from app.services.sidearm_scraper import (
    FetchRetryPolicy,
    SidearmFetchError,
    parse_boxscore,
    scrape_boxscore,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    (
        "fixture_name",
        "url",
        "expected_sport",
        "expected_season",
        "expected_home",
        "expected_away",
        "expected_home_score",
        "expected_away_score",
        "expected_stat",
    ),
    [
        (
            "football_boxscore_2025_uc_davis.html",
            "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467",
            "football",
            "2025",
            "Idaho",
            "UC Davis",
            14,
            28,
            "First Downs",
        ),
        (
            "mens_basketball_boxscore_2025_26_idaho_state.html",
            "https://govandals.com/sports/mens-basketball/stats/2025-26/"
            "idaho-state/boxscore/10050",
            "mens-basketball",
            "2025-26",
            "Idaho State",
            "Idaho",
            76,
            68,
            "FG %",
        ),
        (
            "womens_basketball_boxscore_2025_26_idaho_state.html",
            "https://govandals.com/sports/womens-basketball/stats/2025-26/"
            "idaho-state/boxscore/9968",
            "womens-basketball",
            "2025-26",
            "Idaho",
            "Idaho State",
            81,
            61,
            "Rebounds",
        ),
        (
            "womens_soccer_boxscore_2025_idaho_state.html",
            "https://govandals.com/sports/womens-soccer/stats/2025/"
            "idaho-state/boxscore/9126",
            "womens-soccer",
            "2025",
            "Idaho State",
            "Idaho",
            0,
            0,
            "Shots",
        ),
        (
            "womens_volleyball_boxscore_2025_idaho_state.html",
            "https://govandals.com/sports/womens-volleyball/stats/2025/"
            "idaho-state/boxscore/9105",
            "womens-volleyball",
            "2025",
            "Idaho State",
            "Idaho",
            3,
            1,
            "Kills",
        ),
    ],
)
def test_parse_release_one_sport_boxscore_fixtures(
    fixture_name: str,
    url: str,
    expected_sport: str,
    expected_season: str,
    expected_home: str,
    expected_away: str,
    expected_home_score: int,
    expected_away_score: int,
    expected_stat: str,
) -> None:
    html = (FIXTURE_DIR / fixture_name).read_text(encoding="utf-8")

    parsed = parse_boxscore(url, html)

    assert parsed.sport == expected_sport
    assert parsed.season == expected_season
    assert parsed.home_team == expected_home
    assert parsed.away_team == expected_away
    assert parsed.home_score == expected_home_score
    assert parsed.away_score == expected_away_score
    assert parsed.team_stats[0]["stat_name"] == expected_stat


async def test_scrape_boxscore_retries_transient_fetch(monkeypatch) -> None:
    attempts = 0
    url = "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"

    async def fake_fetch_boxscore(
        requested_url: str,
        timeout_seconds: float | None = None,
    ) -> str:
        nonlocal attempts
        attempts += 1
        assert requested_url == url
        assert timeout_seconds == 3.0
        if attempts == 1:
            raise httpx.ConnectTimeout("temporary timeout")
        return (FIXTURE_DIR / "football_boxscore_2025_uc_davis.html").read_text(
            encoding="utf-8"
        )

    monkeypatch.setattr(
        "app.services.sidearm_scraper.fetch_boxscore",
        fake_fetch_boxscore,
    )

    parsed = await scrape_boxscore(
        url,
        policy=FetchRetryPolicy(
            timeout_seconds=3.0,
            max_attempts=2,
            backoff_seconds=0,
        ),
    )

    assert attempts == 2
    assert parsed.fetch_attempt_count == 2
    assert parsed.fetch_max_attempts == 2
    assert parsed.fetch_retryable_failures == 1
    assert parsed.home_team == "Idaho"


async def test_scrape_boxscore_does_not_retry_terminal_status(monkeypatch) -> None:
    attempts = 0
    url = "https://govandals.com/sports/football/stats/2025/missing/boxscore/9999"

    async def fake_fetch_boxscore(
        requested_url: str,
        timeout_seconds: float | None = None,
    ) -> str:
        nonlocal attempts
        attempts += 1
        request = httpx.Request("GET", requested_url)
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError(
            "not found",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        "app.services.sidearm_scraper.fetch_boxscore",
        fake_fetch_boxscore,
    )

    with pytest.raises(SidearmFetchError) as exc_info:
        await scrape_boxscore(
            url,
            policy=FetchRetryPolicy(
                timeout_seconds=3.0,
                max_attempts=3,
                backoff_seconds=0,
            ),
        )

    assert attempts == 1
    assert exc_info.value.attempt_count == 1
    assert exc_info.value.max_attempts == 3
    assert exc_info.value.retryable is False
