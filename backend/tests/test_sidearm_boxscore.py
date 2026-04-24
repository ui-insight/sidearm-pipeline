"""Tests for Sidearm boxscore parsing across Release 1 sports."""

from pathlib import Path

import pytest

from app.services.sidearm_scraper import parse_boxscore

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
