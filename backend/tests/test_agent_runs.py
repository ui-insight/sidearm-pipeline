"""Tests for agent run provenance, verdict, and evaluation endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.agent import AgentRun, AgentRunEvaluation, AgentRunStep
from app.models.content import GeneratedContent
from app.models.game import Game
from app.services.sidearm_scraper import ParsedBoxscore


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fake_boxscore(url: str) -> ParsedBoxscore:
    return ParsedBoxscore(
        source_url=url,
        title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
        sport="football",
        season="2025",
        game_date="11/8/2025",
        home_team="Idaho",
        away_team="UC Davis",
        home_score=31,
        away_score=28,
        team_stats=[
            {
                "stat_name": "First Downs",
                "home_value": "22",
                "away_value": "18",
                "sort_order": 0,
            }
        ],
        scoring_plays=[],
        player_stats=[],
        raw_html="<html></html>",
    )


def _fake_agent_run(db_session, game_id: int, status: str = "succeeded") -> AgentRun:
    """Insert a minimal AgentRun into the test DB."""
    run = AgentRun(
        agent_name="recap-writer",
        model="claude-opus-4-6",
        prompt_version="abcd1234",
        game_id=game_id,
        trigger="manual",
        input_payload={
            "home_team": "Idaho",
            "away_team": "UC Davis",
            "home_score": 31,
            "away_score": 28,
            "team_stats": [],
        },
        output_payload={
            "headline": "Idaho Edges UC Davis 31-28",
            "recap": "Idaho won a close game. " * 20,
            "spotlight_player": "Jordan Smith",
            "spotlight_body": "Smith had a great game.",
            "social_post": "Idaho defeats UC Davis 31-28! #VandalNation",
        },
        status=status,
        run_metadata={},
    )
    return run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_generate_creates_agent_run_not_generated_content(
    client,
    db_session,
    monkeypatch,
):
    """POST /games/{id}/generate should return AgentRunRead, not GeneratedContent."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    # Ingest a game first
    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    # Mock the recap writer so we don't need a real API key
    fake_run = AgentRun(
        agent_name="recap-writer",
        model="claude-opus-4-6",
        prompt_version="abcd1234",
        game_id=game_id,
        trigger="manual",
        input_payload={"home_team": "Idaho", "away_team": "UC Davis"},
        output_payload={
            "headline": "Idaho Wins",
            "recap": "Idaho won the game. " * 20,
            "spotlight_player": "Smith",
            "spotlight_body": "Great game.",
            "social_post": "Idaho wins! #VandalNation",
        },
        status="succeeded",
        run_metadata={},
    )
    db_session.add(fake_run)
    await db_session.flush()

    async def fake_run_recap_writer(game, db, trigger="manual"):
        return fake_run

    monkeypatch.setattr(
        "app.api.v1.games.run_recap_writer", fake_run_recap_writer
    )

    gen_resp = await client.post(f"/api/v1/games/{game_id}/generate")
    assert gen_resp.status_code == 201
    payload = gen_resp.json()

    # Should return AgentRunRead fields
    assert "agent_name" in payload
    assert payload["agent_name"] == "recap-writer"
    assert "steps" in payload
    assert "evaluations" in payload

    # GeneratedContent should NOT exist yet
    from sqlalchemy import select

    count = await db_session.scalar(
        select(GeneratedContent).where(GeneratedContent.game_id == game_id)
    )
    assert count is None


async def test_approve_verdict_creates_generated_content(
    client,
    db_session,
    monkeypatch,
):
    """POST /agent-runs/{id}/verdict approved should create GeneratedContent."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    run = _fake_agent_run(db_session, game_id)
    db_session.add(run)
    await db_session.flush()
    run_id = run.id

    verdict_resp = await client.post(
        f"/api/v1/agent-runs/{run_id}/verdict",
        json={"verdict": "approved"},
    )
    assert verdict_resp.status_code == 200
    payload = verdict_resp.json()

    # Should return GeneratedContentRead fields
    assert payload["headline"] == "Idaho Edges UC Davis 31-28"
    assert payload["game_id"] == game_id

    # GeneratedContent row should exist
    from sqlalchemy import select

    row = await db_session.scalar(
        select(GeneratedContent).where(GeneratedContent.game_id == game_id)
    )
    assert row is not None
    assert row.headline == "Idaho Edges UC Davis 31-28"


async def test_reject_verdict_does_not_create_generated_content(
    client,
    db_session,
    monkeypatch,
):
    """POST /agent-runs/{id}/verdict rejected should NOT create GeneratedContent."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    game_id = resp.json()["id"]

    run = _fake_agent_run(db_session, game_id)
    db_session.add(run)
    await db_session.flush()
    run_id = run.id

    verdict_resp = await client.post(
        f"/api/v1/agent-runs/{run_id}/verdict",
        json={"verdict": "rejected"},
    )
    assert verdict_resp.status_code == 200
    payload = verdict_resp.json()
    assert payload["human_verdict"] == "rejected"

    # No GeneratedContent should exist
    from sqlalchemy import select

    row = await db_session.scalar(
        select(GeneratedContent).where(GeneratedContent.game_id == game_id)
    )
    assert row is None


async def test_duplicate_verdict_returns_409(
    client,
    db_session,
    monkeypatch,
):
    """Submitting a second verdict on the same run should return 409."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    game_id = resp.json()["id"]

    run = _fake_agent_run(db_session, game_id)
    db_session.add(run)
    await db_session.flush()
    run_id = run.id

    await client.post(
        f"/api/v1/agent-runs/{run_id}/verdict",
        json={"verdict": "rejected"},
    )

    second = await client.post(
        f"/api/v1/agent-runs/{run_id}/verdict",
        json={"verdict": "approved"},
    )
    assert second.status_code == 409


async def test_evaluate_persists_eval_rows(
    client,
    db_session,
    monkeypatch,
):
    """POST /agent-runs/{id}/evaluate should run checks and persist eval rows."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    game_id = resp.json()["id"]

    run = _fake_agent_run(db_session, game_id)
    db_session.add(run)
    await db_session.flush()
    run_id = run.id

    # Mock eval_runner to avoid requiring the eval_metrics file on disk
    from app.models.agent import AgentRunEvaluation as EvalModel
    from datetime import datetime, timezone

    async def fake_run_evaluation(agent_run_id: int, db):
        eval_row = EvalModel(
            agent_run_id=agent_run_id,
            eval_type="deterministic",
            metric_name="word_count",
            passed=True,
            score=1.0,
            detail={"words": 280},
            evaluated_at=datetime.now(timezone.utc),
        )
        db.add(eval_row)
        loaded = await db.get(AgentRun, agent_run_id)
        loaded.eval_score = 1.0
        await db.commit()
        # Expire all cached objects so the subsequent selectinload reload is fresh
        db.expire_all()

    monkeypatch.setattr(
        "app.api.v1.agent_runs.run_evaluation", fake_run_evaluation
    )

    eval_resp = await client.post(f"/api/v1/agent-runs/{run_id}/evaluate")
    assert eval_resp.status_code == 200
    payload = eval_resp.json()
    assert payload["eval_score"] is not None
    assert len(payload["evaluations"]) >= 1


async def test_list_agent_runs_returns_recent(
    client,
    db_session,
    monkeypatch,
):
    """GET /agent-runs should return the runs we inserted."""
    async def fake_scrape(url: str) -> ParsedBoxscore:
        return _fake_boxscore(url)

    monkeypatch.setattr("app.services.ingest.scrape_boxscore", fake_scrape)

    resp = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
        },
    )
    game_id = resp.json()["id"]

    for _ in range(3):
        run = _fake_agent_run(db_session, game_id)
        db_session.add(run)
    await db_session.flush()

    list_resp = await client.get("/api/v1/agent-runs")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 3
    assert items[0]["agent_name"] == "recap-writer"
