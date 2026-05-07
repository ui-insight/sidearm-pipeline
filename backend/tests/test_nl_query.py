"""Tests for the natural language query endpoint."""

from __future__ import annotations

from app.models.agent import AgentRun

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_nl_query_returns_result_for_valid_question(
    client,
    db_session,
    monkeypatch,
):
    """POST /nl-query with a valid question should return NLQueryResult."""
    fake_output = {
        "question": "How many games are ingested?",
        "sql": "SELECT COUNT(*) AS total FROM games",
        "rows": [{"total": 0}],
        "answer": "There are 0 games ingested.",
    }
    fake_run = AgentRun(
        agent_name="nl-query",
        model="claude-opus-4-6",
        prompt_version="abcd1234",
        game_id=None,
        trigger="api",
        input_payload={"question": "How many games are ingested?"},
        output_payload=fake_output,
        status="succeeded",
        run_metadata={},
    )
    db_session.add(fake_run)
    await db_session.flush()

    async def fake_run_nl_query(question: str, db):
        return fake_run

    monkeypatch.setattr("app.api.v1.nl_query.run_nl_query", fake_run_nl_query)

    resp = await client.post(
        "/api/v1/nl-query",
        json={"question": "How many games are ingested?"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["question"] == "How many games are ingested?"
    assert payload["sql"] == "SELECT COUNT(*) AS total FROM games"
    assert payload["answer"] == "There are 0 games ingested."
    assert payload["agent_run_id"] == fake_run.id


async def test_nl_query_creates_agent_run_record(
    client,
    db_session,
    monkeypatch,
):
    """POST /nl-query should create an AgentRun provenance record."""
    from sqlalchemy import select

    fake_run = AgentRun(
        agent_name="nl-query",
        model="claude-opus-4-6",
        prompt_version="abcd1234",
        game_id=None,
        trigger="api",
        input_payload={"question": "Which sport has the most games?"},
        output_payload={
            "question": "Which sport has the most games?",
            "sql": (
                "SELECT sport, COUNT(*) FROM games"
                " GROUP BY sport ORDER BY COUNT(*) DESC LIMIT 1"
            ),
            "rows": [{"sport": "football", "count": 3}],
            "answer": "Football has the most games with 3.",
        },
        status="succeeded",
        run_metadata={},
    )
    db_session.add(fake_run)
    await db_session.flush()

    async def fake_run_nl_query(question: str, db):
        return fake_run

    monkeypatch.setattr("app.api.v1.nl_query.run_nl_query", fake_run_nl_query)

    resp = await client.post(
        "/api/v1/nl-query",
        json={"question": "Which sport has the most games?"},
    )
    assert resp.status_code == 200

    # AgentRun should exist in DB
    row = await db_session.scalar(
        select(AgentRun).where(AgentRun.agent_name == "nl-query")
    )
    assert row is not None
    assert row.status == "succeeded"


async def test_nl_query_validates_empty_question(client):
    """POST /nl-query with an empty question should return 422."""
    resp = await client.post("/api/v1/nl-query", json={"question": ""})
    assert resp.status_code == 422


async def test_nl_query_validates_question_too_long(client):
    """POST /nl-query with a question exceeding 500 chars should return 422."""
    resp = await client.post(
        "/api/v1/nl-query", json={"question": "x" * 501}
    )
    assert resp.status_code == 422
