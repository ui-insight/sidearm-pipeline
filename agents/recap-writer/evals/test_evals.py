"""Pytest entry point for local recap-writer eval runs.

Run with:
    cd agents/recap-writer/evals
    pytest test_evals.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval_metrics import (
    check_headline_length,
    check_score_present,
    check_social_length,
    check_stats_cited,
    check_teams_mentioned,
    check_word_count,
    composite_score,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixtures() -> list[tuple[str, dict]]:
    """Load all JSON fixtures from the fixtures directory."""
    fixtures = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        with path.open() as f:
            data = json.load(f)
        fixtures.append((path.name, data))
    return fixtures


@pytest.mark.parametrize("fixture_name,fixture", load_fixtures())
def test_score_present_with_fixture(fixture_name: str, fixture: dict) -> None:
    game_data = fixture["game_data"]
    coverage = fixture["coverage"]
    result = check_score_present(
        recap=coverage["recap"],
        home_score=game_data.get("home_score"),
        away_score=game_data.get("away_score"),
    )
    expected = fixture.get("expected_pass", {}).get("score_present")
    if expected is not None:
        assert result.passed == expected, (
            f"[{fixture_name}] score_present expected={expected} got={result.passed}. "
            f"detail={result.detail}"
        )


@pytest.mark.parametrize("fixture_name,fixture", load_fixtures())
def test_word_count_in_range(fixture_name: str, fixture: dict) -> None:
    coverage = fixture["coverage"]
    result = check_word_count(recap=coverage["recap"])
    expected = fixture.get("expected_pass", {}).get("word_count")
    if expected is not None:
        assert result.passed == expected, (
            f"[{fixture_name}] word_count expected={expected} got={result.passed}. "
            f"detail={result.detail}"
        )


@pytest.mark.parametrize("fixture_name,fixture", load_fixtures())
def test_all_deterministic_checks_pass(fixture_name: str, fixture: dict) -> None:
    game_data = fixture["game_data"]
    coverage = fixture["coverage"]
    expected_pass = fixture.get("expected_pass", {})

    checks = [
        check_score_present(
            coverage["recap"],
            game_data.get("home_score"),
            game_data.get("away_score"),
        ),
        check_teams_mentioned(
            coverage["recap"],
            game_data.get("home_team"),
            game_data.get("away_team"),
        ),
        check_word_count(coverage["recap"]),
        check_headline_length(coverage["headline"]),
        check_social_length(coverage["social_post"]),
        check_stats_cited(coverage["recap"], game_data.get("team_stats", [])),
    ]

    for result in checks:
        expected = expected_pass.get(result.metric)
        if expected is not None:
            assert result.passed == expected, (
                f"[{fixture_name}] {result.metric} expected={expected} "
                f"got={result.passed}. detail={result.detail}"
            )

    score = composite_score(checks)
    assert 0.0 <= score <= 1.0
