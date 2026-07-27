"""Verify natural-language questions stay inside the semantic query catalog."""

import json
from types import SimpleNamespace

from app.config import settings
from app.services import semantic_question
from tests.test_semantic_queries import seed_semantic_query_facts


class FakeMessages:
    """Return sequential Anthropic-compatible JSON responses."""

    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(payload))]
        )


class FakeAnthropic:
    def __init__(self, payloads: list[dict]) -> None:
        self.messages = FakeMessages(payloads)


async def test_ask_maps_executes_and_phrases_verified_query(
    client, db_session, monkeypatch
) -> None:
    await seed_semantic_query_facts(db_session)
    fake = FakeAnthropic(
        [
            {
                "answerable": True,
                "query": {
                    "query_id": "team_season_record",
                    "season": "2025-26",
                    "conference_scope": "all",
                },
                "reason": None,
            },
            {
                "answer": (
                    "Idaho won 2 games and lost 1 in 2025-26. The result has "
                    "1 open quality issue."
                )
            },
        ]
    )
    monkeypatch.setattr(semantic_question, "_get_client", lambda: fake)

    response = await client.post(
        "/api/v1/semantic-queries/ask",
        json={"question": "What was Idaho's record in 2025-26?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["query_id"] == "team_season_record"
    assert payload["query"]["season"] == "2025-26"
    assert payload["result"]["result"]["games_played"] == 3
    assert payload["answer"].startswith("Idaho won 2 games")
    assert payload["model"] == (settings.NLQ_MODEL or settings.ACHIEVEMENT_MODEL)
    assert len(fake.messages.calls) == 2
    assert "available_values" in fake.messages.calls[0]["messages"][0]["content"]
    assert "warehouse_result" in fake.messages.calls[1]["messages"][0]["content"]


async def test_ask_returns_honest_out_of_catalog_response(
    client, db_session, monkeypatch
) -> None:
    await seed_semantic_query_facts(db_session)
    fake = FakeAnthropic(
        [
            {
                "answerable": False,
                "query": None,
                "reason": "The verified catalog does not include injury reports.",
            }
        ]
    )
    monkeypatch.setattr(semantic_question, "_get_client", lambda: fake)

    response = await client.post(
        "/api/v1/semantic-queries/ask",
        json={"question": "Which players are injured?"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unanswerable"
    assert response.json()["query"] is None
    assert response.json()["result"] is None
    assert len(fake.messages.calls) == 1


async def test_ask_rejects_number_not_present_in_result(
    client, db_session, monkeypatch
) -> None:
    await seed_semantic_query_facts(db_session)
    fake = FakeAnthropic(
        [
            {
                "answerable": True,
                "query": {
                    "query_id": "team_season_record",
                    "season": "2025-26",
                },
                "reason": None,
            },
            {"answer": "Idaho won 99 games in 2025-26."},
        ]
    )
    monkeypatch.setattr(semantic_question, "_get_client", lambda: fake)

    response = await client.post(
        "/api/v1/semantic-queries/ask",
        json={"question": "What was Idaho's record in 2025-26?"},
    )

    assert response.status_code == 502
    assert "introduced a number" in response.json()["detail"]


async def test_ask_validates_question_length(client) -> None:
    response = await client.post("/api/v1/semantic-queries/ask", json={"question": "?"})
    assert response.status_code == 422

    whitespace = await client.post(
        "/api/v1/semantic-queries/ask", json={"question": "   "}
    )
    assert whitespace.status_code == 422
