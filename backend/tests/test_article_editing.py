"""Behavior tests for human Article editing and the readiness gate."""

from sqlalchemy import func, select

from app.config import settings
from app.models.article import (
    ArticleReadinessDecision,
    ArticleVersion,
    ArticleWarningOverride,
)
from app.schemas.article import ArticleDraftOutput
from app.services import article_generation
from tests.test_article_generation import _article_brief, _safe_draft


async def _generated_version(client, db_session, monkeypatch) -> tuple[dict, dict]:
    brief = await _article_brief(client, db_session)

    async def safe_writer(_writer_input: dict) -> ArticleDraftOutput:
        return _safe_draft(brief)

    monkeypatch.setattr(article_generation, "generate_article_draft", safe_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": f"initial-editor-draft-{brief['id']}"},
    )
    assert queued.status_code == 202
    await article_generation.process_article_generation_job(
        db_session, queued.json()["id"]
    )
    current = await client.get(f"/api/v1/articles/{brief['id']}")
    assert current.status_code == 200
    return current.json(), current.json()["latest_version"]


def _human_payload(version: dict, *, headline: str | None = None) -> dict:
    return {
        "base_version_id": version["id"],
        "headline": headline or version["headline"],
        "headline_evidence_ids": version["headline_evidence_ids"],
        "blocks": version["blocks"],
    }


async def test_human_save_appends_attributable_version(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, base = await _generated_version(client, db_session, monkeypatch)
    payload = _human_payload(base, headline=f"{base['headline']} updated")

    response = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json=payload,
    )

    assert response.status_code == 201, response.json()
    saved = response.json()
    assert saved["version"] == 2
    assert saved["origin"] == "human"
    assert saved["parent_version_id"] == base["id"]
    assert saved["author"] == settings.PROTOTYPE_AUTH_USERNAME
    assert saved["evidence_hash"] == base["evidence_hash"]
    assert saved["style_hash"] == base["style_hash"]
    assert await db_session.scalar(select(func.count(ArticleVersion.id))) == 2

    versions = await client.get(f"/api/v1/articles/{brief['id']}/versions")
    assert [version["version"] for version in versions.json()] == [1, 2]


async def test_stale_human_save_never_overwrites_newer_version(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, base = await _generated_version(client, db_session, monkeypatch)
    first = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json=_human_payload(base, headline=f"{base['headline']} first edit"),
    )
    assert first.status_code == 201

    stale = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json=_human_payload(base, headline=f"{base['headline']} stale edit"),
    )

    assert stale.status_code == 409
    assert "stale" in stale.json()["detail"].lower()
    versions = await client.get(f"/api/v1/articles/{brief['id']}/versions")
    assert [version["headline"] for version in versions.json()] == [
        base["headline"],
        f"{base['headline']} first edit",
    ]


async def test_blocking_human_findings_are_saved_but_cannot_be_ready(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, base = await _generated_version(client, db_session, monkeypatch)
    payload = _human_payload(base, headline="Avery Adams scores 99 statement win")
    saved = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json=payload,
    )

    assert saved.status_code == 201
    codes = {finding["code"] for finding in saved.json()["validation_results"]}
    assert "unsupported_numeral" in codes
    assert "style:measured-language" in codes

    ready = await client.post(
        f"/api/v1/articles/{brief['id']}/versions/{saved.json()['id']}/ready",
        json={"warning_overrides": []},
    )
    assert ready.status_code == 409
    assert "blocking" in ready.json()["detail"].lower()


async def test_readiness_requires_and_audits_warning_override(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, base = await _generated_version(client, db_session, monkeypatch)
    saved = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json=_human_payload(base, headline=f"{base['headline']}!"),
    )
    assert saved.status_code == 201
    assert [finding["severity"] for finding in saved.json()["validation_results"]] == [
        "warning"
    ]

    missing_reason = await client.post(
        f"/api/v1/articles/{brief['id']}/versions/{saved.json()['id']}/ready",
        json={"warning_overrides": []},
    )
    assert missing_reason.status_code == 409

    ready = await client.post(
        f"/api/v1/articles/{brief['id']}/versions/{saved.json()['id']}/ready",
        json={
            "warning_overrides": [
                {
                    "finding_code": "style:no-exclamation",
                    "reason": "The SID approved this punctuation for the prototype.",
                }
            ]
        },
    )
    assert ready.status_code == 200, ready.json()
    assert ready.json()["status"] == "ready"
    assert ready.json()["decision"]["actor"] == settings.PROTOTYPE_AUTH_USERNAME
    assert (
        ready.json()["ready_version"]["warning_overrides"][0]["finding_code"]
        == "style:no-exclamation"
    )
    assert await db_session.scalar(select(func.count(ArticleWarningOverride.id))) == 1
    assert await db_session.scalar(select(func.count(ArticleReadinessDecision.id))) == 1

    detail = await client.get(f"/api/v1/articles/{brief['id']}")
    assert detail.json()["status"] == "ready"
    assert detail.json()["ready_version"]["id"] == saved.json()["id"]
    assert len(detail.json()["readiness_history"]) == 1

    queue = await client.get("/api/v1/articles")
    assert queue.status_code == 200
    assert queue.json()["items"][0]["owner"] == settings.PROTOTYPE_AUTH_USERNAME
    assert queue.json()["items"][0]["ready_version"]["id"] == saved.json()["id"]


async def test_ai_revision_stays_bound_to_base_version_and_evidence(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, base = await _generated_version(client, db_session, monkeypatch)
    captured: dict = {}

    async def revised_writer(writer_input: dict) -> ArticleDraftOutput:
        captured.update(writer_input)
        return _safe_draft(brief)

    monkeypatch.setattr(article_generation, "generate_article_draft", revised_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={
            "idempotency_key": f"editor-revision-{brief['id']}",
            "base_version_id": base["id"],
            "editor_instructions": "Tighten the lead without adding facts.",
        },
    )
    assert queued.status_code == 202, queued.json()
    assert queued.json()["base_version_id"] == base["id"]
    await article_generation.process_article_generation_job(
        db_session, queued.json()["id"]
    )

    assert captured["editor_revision"]["base_version"]["id"] == base["id"]
    assert captured["editor_revision"]["instructions"] == (
        "Tighten the lead without adding facts."
    )
    assert captured["evidence_bundle"]["content_hash"] == base["evidence_hash"]
    completed = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{queued.json()['id']}"
    )
    revised = completed.json()["article_version"]
    assert revised["version"] == 2
    assert revised["parent_version_id"] == base["id"]
    assert revised["editor_instructions"] == "Tighten the lead without adding facts."
