"""Tests for game validation and publish workflow."""

import types

from sqlalchemy import select

from app.models.game import Game
from app.models.publish_event import PublishEvent
from app.services.validation import all_passed, validate_game


# ---------------------------------------------------------------------------
# Unit tests for validate_game()
# ---------------------------------------------------------------------------


def _make_game(**kwargs) -> types.SimpleNamespace:
    """Return a SimpleNamespace that mimics the Game attributes accessed by validate_game."""
    defaults = {
        "sport": "football",
        "season": "2025",
        "game_date": "11/8/2025",
        "home_team": "Idaho",
        "away_team": "UC Davis",
        "title": "Football vs UC Davis",
        "event_status": "final",
        "home_score": 31,
        "away_score": 28,
        "publish_status": "draft",
        "team_stats": ["row"],  # non-empty list
        "scoring_plays": ["play"],  # non-empty list
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_validate_game_final_all_fields_passes():
    game = _make_game()
    checks = validate_game(game)
    assert all_passed(checks)


def test_validate_game_missing_score_fails():
    game = _make_game(home_score=None, away_score=None)
    checks = validate_game(game)
    rules = {c.rule: c for c in checks}
    assert "has_score" in rules
    assert not rules["has_score"].passed
    assert not all_passed(checks)


def test_validate_game_scheduled_skips_score_check():
    game = _make_game(
        event_status="scheduled",
        home_score=None,
        away_score=None,
        team_stats=[],
        scoring_plays=[],
    )
    checks = validate_game(game)
    rules = {c.rule for c in checks}
    # Score-related checks should not be present for non-final events
    assert "has_score" not in rules
    assert "has_team_stats" not in rules
    assert "scoring_plays_present" not in rules
    # The always-required checks should all pass
    assert all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# Integration tests via HTTP endpoints
# ---------------------------------------------------------------------------


async def _create_game(client, monkeypatch, **overrides):
    """Ingest a fake game and return (game_id, payload)."""
    from app.services.sidearm_scraper import ParsedBoxscore

    defaults = dict(
        source_url="https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467",
        title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
        sport="football",
        season="2025",
        game_date="11/8/2025",
        home_team="Idaho",
        away_team="UC Davis",
        home_score=31,
        away_score=28,
        team_stats=[{"stat_name": "First Downs", "home_value": "22", "away_value": "18", "sort_order": 0}],
        scoring_plays=[{"period": "4", "clock": "00:00", "team": "IDA", "description": "FG", "home_score": 31, "away_score": 28, "sort_order": 0}],
        player_stats=[],
        raw_html="<html></html>",
    )
    defaults.update(overrides)

    parsed = ParsedBoxscore(**defaults)

    async def fake_scrape(url: str) -> ParsedBoxscore:
        parsed.source_url = url
        return parsed

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={"url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"},
    )
    assert resp.status_code == 201
    return resp.json()["id"], resp.json()


async def test_validate_endpoint_sets_validated(client, db_session, monkeypatch):
    game_id, _ = await _create_game(client, monkeypatch)

    resp = await client.post(f"/api/v1/games/{game_id}/validate")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["passed"] is True
    assert payload["publish_status"] == "validated"
    assert payload["game_id"] == game_id
    assert isinstance(payload["checks"], list)
    assert len(payload["checks"]) > 0

    game = await db_session.get(Game, game_id)
    assert game is not None
    assert game.publish_status == "validated"
    assert game.last_validated_at is not None


async def test_validate_endpoint_sets_errored(client, db_session, monkeypatch):
    # Create a game without team_stats; since home_score/away_score are present,
    # event_status will be "final", and has_team_stats will fail.
    game_id, _ = await _create_game(
        client,
        monkeypatch,
        team_stats=[],
        scoring_plays=[],
    )

    resp = await client.post(f"/api/v1/games/{game_id}/validate")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["passed"] is False
    assert payload["publish_status"] == "errored"

    game = await db_session.get(Game, game_id)
    assert game is not None
    assert game.publish_status == "errored"


async def test_publish_endpoint_requires_validated_status(client, db_session, monkeypatch):
    game_id, _ = await _create_game(client, monkeypatch)
    # game is in draft state — should 409
    resp = await client.post(f"/api/v1/games/{game_id}/publish")
    assert resp.status_code == 409


async def test_publish_endpoint_succeeds_after_validate(client, db_session, monkeypatch):
    game_id, _ = await _create_game(client, monkeypatch)

    validate_resp = await client.post(f"/api/v1/games/{game_id}/validate")
    assert validate_resp.status_code == 200
    assert validate_resp.json()["passed"] is True

    publish_resp = await client.post(f"/api/v1/games/{game_id}/publish")
    assert publish_resp.status_code == 200
    payload = publish_resp.json()
    assert payload["publish_status"] == "published"
    assert payload["id"] == game_id


async def test_publish_event_created_on_transition(client, db_session, monkeypatch):
    game_id, _ = await _create_game(client, monkeypatch)

    await client.post(f"/api/v1/games/{game_id}/validate")
    await client.post(f"/api/v1/games/{game_id}/publish")

    await db_session.refresh(await db_session.get(Game, game_id))
    events = (
        await db_session.scalars(
            select(PublishEvent)
            .where(PublishEvent.game_id == game_id)
            .order_by(PublishEvent.changed_at)
        )
    ).all()

    assert len(events) == 2
    assert events[0].from_status == "draft"
    assert events[0].to_status == "validated"
    assert events[0].trigger == "api"
    assert events[1].from_status == "validated"
    assert events[1].to_status == "published"
    assert events[1].trigger == "api"
