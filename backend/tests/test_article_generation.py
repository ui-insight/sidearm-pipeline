"""Behavior tests for durable, evidence-bound Article Draft generation."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models.article import ArticleGenerationJob, ArticleVersion
from app.schemas.article import ArticleDraftOutput
from app.services import article_generation, article_writer
from tests.test_achievement_ai import _detected_suggestions


class _FakeMessages:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))]
        )


class _FakeAnthropic:
    def __init__(self, payload: dict) -> None:
        self.messages = _FakeMessages(payload)


def test_article_writer_builds_a_mindrouter_client(monkeypatch) -> None:
    captured: dict = {}
    fake_client = object()

    def fake_anthropic(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(article_writer.settings, "MINDROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        article_writer.settings,
        "MINDROUTER_BASE_URL",
        "https://mindrouter.example.edu/anthropic",
    )
    monkeypatch.setattr(article_writer, "AsyncAnthropic", fake_anthropic)
    monkeypatch.setattr(article_writer, "_client", None)

    assert article_writer._get_client() is fake_client
    assert captured == {
        "api_key": "test-key",
        "base_url": "https://mindrouter.example.edu/anthropic",
    }


def test_article_writer_requires_a_mindrouter_key(monkeypatch) -> None:
    monkeypatch.setattr(article_writer.settings, "MINDROUTER_API_KEY", None)
    monkeypatch.setattr(article_writer, "_client", None)

    with pytest.raises(RuntimeError, match="MINDROUTER_API_KEY"):
        article_writer._get_client()


async def _article_brief(client, db_session) -> dict:
    _, suggestions = await _detected_suggestions(db_session)
    suggestion = suggestions[0]
    verdict = await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion.id}/verdict",
        json={"state": "approved"},
    )
    assert verdict.status_code == 200
    response = await client.post(
        "/api/v1/articles",
        json={
            "suggestion_ids": [suggestion.id],
            "article_type": "achievement_story",
            "angle": "Lead with the approved achievement.",
            "audience": "Vandal fans",
            "constraints": "Keep the opening concise.",
            "idempotency_key": f"article-generation-brief-{suggestion.id}",
        },
    )
    assert response.status_code == 201
    return response.json()


def _safe_draft(brief: dict) -> ArticleDraftOutput:
    evidence = brief["evidence_bundle"]["suggestions"][0]
    evidence_id = evidence["evidence_item_id"]
    player_name = evidence["player_name"]
    value = str(evidence["computed_value"]).split(".")[0]
    qualifier = evidence["coverage_window"]["claim_scope"]
    supported_claim = evidence["phrasing"] or (
        f"{player_name} recorded {value} {evidence['stat_label'].lower()} {qualifier}."
    )
    return ArticleDraftOutput.model_validate(
        {
            "headline": (
                f"{player_name}: {value} {evidence['stat_label']} {qualifier}"
            ),
            "headline_evidence_ids": [evidence_id],
            "blocks": [
                {
                    "kind": "lead",
                    "text": supported_claim,
                    "evidence_ids": [evidence_id],
                }
            ],
        }
    )


async def test_generation_job_creates_validated_immutable_ai_version(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief = await _article_brief(client, db_session)
    captured_input: dict = {}

    async def safe_writer(writer_input: dict) -> ArticleDraftOutput:
        captured_input.update(writer_input)
        return _safe_draft(brief)

    monkeypatch.setattr(article_generation, "generate_article_draft", safe_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "article-generation-safe-1"},
    )

    assert queued.status_code == 202
    job = queued.json()
    assert job["state"] == "queued"
    assert job["attempt_count"] == 0
    assert job["provider"] == "mindrouter-anthropic"
    assert job["model"] == "qwen/qwen3.6-27b"
    assert job["style_snapshot"]["versions"][0]["guide_key"] == ("athletics-default")

    processed = await article_generation.process_article_generation_job(
        db_session,
        job["id"],
    )
    assert processed is True
    assert set(captured_input) == {
        "article_brief",
        "evidence_bundle",
        "style_guide",
    }
    assert "raw_body" not in str(captured_input)

    status = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{job['id']}"
    )
    assert status.status_code == 200
    completed = status.json()
    assert completed["validation_results"] == [], completed["validation_results"]
    assert completed["state"] == "succeeded", completed
    assert completed["attempt_count"] == 1
    assert completed["error_code"] is None
    assert completed["output_hash"]
    version = completed["article_version"]
    assert version["version"] == 1
    assert version["origin"] == "ai"
    assert version["provider"] == "mindrouter-anthropic"
    assert version["model"] == "qwen/qwen3.6-27b"
    assert version["headline_evidence_ids"] == _safe_draft(brief).headline_evidence_ids
    assert version["evidence_hash"] == brief["evidence_bundle"]["content_hash"]
    assert version["style_hash"] == completed["style_hash"]
    assert version["prompt_version"] == "article-writer-v1"
    assert version["validation_results"] == []

    article = await client.get(f"/api/v1/articles/{brief['id']}")
    assert article.status_code == 200
    assert article.json()["status"] == "in_edit"
    assert article.json()["latest_version"]["id"] == version["id"]


async def test_unsafe_writer_output_fails_without_partial_article_version(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief = await _article_brief(client, db_session)
    evidence_id = brief["evidence_bundle"]["suggestions"][0]["evidence_item_id"]

    async def unsafe_writer(_writer_input: dict) -> ArticleDraftOutput:
        return ArticleDraftOutput.model_validate(
            {
                "headline": "Jordan Smith posts 99 in a statement win",
                "headline_evidence_ids": [evidence_id],
                "blocks": [
                    {
                        "kind": "lead",
                        "text": "Jordan Smith set a career high with 99 points.",
                        "evidence_ids": [evidence_id],
                    },
                    {
                        "kind": "body",
                        "text": "The unsupported record belongs in no draft.",
                        "evidence_ids": ["achievement-suggestion:999999"],
                    },
                ],
            }
        )

    monkeypatch.setattr(article_generation, "generate_article_draft", unsafe_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "article-generation-unsafe-1"},
    )
    job_id = queued.json()["id"]
    await article_generation.process_article_generation_job(db_session, job_id)

    status = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{job_id}"
    )
    failed = status.json()
    assert failed["state"] == "failed"
    assert failed["error_code"] == "validation_failed"
    assert failed["article_version"] is None
    codes = {finding["code"] for finding in failed["validation_results"]}
    assert {
        "unsupported_numeral",
        "unsupported_entity",
        "missing_coverage_qualifier",
        "unknown_evidence_id",
        "style:measured-language",
    }.issubset(codes)
    version_count = await db_session.scalar(select(func.count(ArticleVersion.id)))
    assert version_count == 0
    article = await client.get(f"/api/v1/articles/{brief['id']}")
    assert article.json()["status"] == "brief"


async def test_provider_failure_preserves_brief_and_allows_retry(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief = await _article_brief(client, db_session)

    async def unavailable_writer(_writer_input: dict) -> ArticleDraftOutput:
        raise RuntimeError("Writer provider unavailable; retry later.")

    monkeypatch.setattr(
        article_generation,
        "generate_article_draft",
        unavailable_writer,
    )
    first = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "article-generation-provider-failure"},
    )
    await article_generation.process_article_generation_job(
        db_session,
        first.json()["id"],
    )
    failed = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{first.json()['id']}"
    )
    assert failed.json()["state"] == "failed"
    assert failed.json()["error_code"] == "provider_unavailable"
    assert failed.json()["article_version"] is None

    retry = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "article-generation-provider-retry"},
    )
    assert retry.status_code == 202
    assert retry.json()["state"] == "queued"


async def test_expired_running_job_is_reclaimed_after_restart(
    client,
    db_session,
    test_session_factory,
    monkeypatch,
) -> None:
    brief = await _article_brief(client, db_session)

    async def safe_writer(_writer_input: dict) -> ArticleDraftOutput:
        return _safe_draft(brief)

    monkeypatch.setattr(article_generation, "generate_article_draft", safe_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "article-generation-reclaim"},
    )
    job = await db_session.get(ArticleGenerationJob, queued.json()["id"])
    assert job is not None
    job.state = "running"
    job.attempt_count = 1
    job.lease_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    job_id = job.id
    await db_session.commit()

    processed = await article_generation.process_next_article_generation_job(
        test_session_factory,
    )
    assert processed is True
    db_session.expire_all()
    status = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{job_id}"
    )
    assert status.json()["state"] == "succeeded", status.json()
    assert status.json()["attempt_count"] == 2


async def test_generation_request_is_idempotent_and_rejects_parallel_job(
    client,
    db_session,
) -> None:
    brief = await _article_brief(client, db_session)
    path = f"/api/v1/articles/{brief['id']}/generation-jobs"
    payload = {"idempotency_key": "article-generation-idempotent"}
    first = await client.post(path, json=payload)
    replay = await client.post(path, json=payload)

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json() == first.json()

    parallel = await client.post(
        path,
        json={"idempotency_key": "article-generation-parallel"},
    )
    assert parallel.status_code == 409
    assert parallel.json()["detail"] == (
        "This Article already has an active generation job."
    )


async def test_writer_provider_receives_only_bounded_editorial_inputs(
    monkeypatch,
) -> None:
    output = {
        "headline": "Idaho wins 72-66",
        "headline_evidence_ids": ["game:1"],
        "blocks": [
            {
                "kind": "lead",
                "text": "Idaho won 72-66.",
                "evidence_ids": ["game:1"],
            }
        ],
    }
    fake_client = _FakeAnthropic(output)
    monkeypatch.setattr(article_writer, "_get_client", lambda: fake_client)
    writer_input = {
        "article_brief": {"angle": "Lead with the result."},
        "evidence_bundle": {"content_hash": "evidence-hash"},
        "style_guide": {"rules": []},
    }

    result = await article_writer.generate_article_draft(writer_input)

    assert result.headline == output["headline"]
    call = fake_client.messages.calls[0]
    provider_input = json.loads(call["messages"][0]["content"])
    assert set(provider_input) == {
        "article_brief",
        "evidence_bundle",
        "style_guide",
    }
    assert provider_input == writer_input


async def test_writer_provider_receives_bounded_editor_revision(monkeypatch) -> None:
    output = {
        "headline": "Idaho wins 72-66",
        "headline_evidence_ids": ["game:1"],
        "blocks": [
            {
                "kind": "lead",
                "text": "Idaho won 72-66.",
                "evidence_ids": ["game:1"],
            }
        ],
    }
    fake_client = _FakeAnthropic(output)
    monkeypatch.setattr(article_writer, "_get_client", lambda: fake_client)
    writer_input = {
        "article_brief": {"angle": "Lead with the result."},
        "evidence_bundle": {"content_hash": "evidence-hash"},
        "style_guide": {"rules": []},
        "editor_revision": {
            "instructions": "Tighten the lead without adding facts.",
            "base_version": {
                "id": 4,
                "version": 2,
                "headline": "Idaho earns a road victory",
                "headline_evidence_ids": ["game:1"],
                "blocks": output["blocks"],
            },
        },
    }

    await article_writer.generate_article_draft(writer_input)

    call = fake_client.messages.calls[0]
    provider_input = json.loads(call["messages"][0]["content"])
    assert provider_input == writer_input
