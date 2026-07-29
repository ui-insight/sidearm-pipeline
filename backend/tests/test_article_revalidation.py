"""Behavior tests for Article evidence drift and deliberate revalidation."""

from decimal import Decimal

from sqlalchemy import func, select

from app.models.achievement import AchievementSuggestion
from app.models.article import (
    Article,
    ArticleEvidenceRevalidation,
    ArticleVersion,
    EvidenceBundle,
)
from app.models.coverage_window import CoverageWindow
from app.models.game import Game, SourceSnapshot
from app.models.player_game_stat import PlayerGameStat
from app.services.achievement_detection import detect_achievement_suggestions
from tests.test_article_editing import _generated_version
from tests.test_article_generation import _article_brief


async def _current_suggestion(db_session, brief: dict) -> AchievementSuggestion:
    suggestion_key = brief["evidence_bundle"]["suggestions"][0]["suggestion_key"]
    suggestion = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == brief["game"]["id"],
            AchievementSuggestion.suggestion_key == suggestion_key,
        )
    )
    assert suggestion is not None
    return suggestion


async def test_unchanged_redetection_preserves_article_and_bundle_identity(
    client,
    db_session,
) -> None:
    brief = await _article_brief(client, db_session)
    article = await db_session.get(Article, brief["id"])
    game = await db_session.get(Game, article.game_id)
    previous_source = brief["evidence_bundle"]["suggestions"][0]["source"]
    repeated_snapshot = SourceSnapshot(
        game_id=game.id,
        source_system=previous_source["source_system"],
        source_type=previous_source["source_type"],
        source_url=previous_source["source_url"],
        parser_version="test-v1",
        content_hash=previous_source["content_hash"],
        http_status=200,
        raw_body="same material fixture",
    )
    db_session.add(repeated_snapshot)
    await db_session.flush()
    fact = await db_session.scalar(
        select(PlayerGameStat).where(PlayerGameStat.game_id == game.id)
    )
    assert fact is not None
    fact.source_snapshot_id = repeated_snapshot.id

    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    current = (await client.get(f"/api/v1/articles/{brief['id']}")).json()
    assert current["status"] == "brief"
    assert current["evidence_bundle"]["id"] == brief["evidence_bundle"]["id"]
    assert current["active_revalidation"] is None
    assert (
        await db_session.scalar(select(func.count(ArticleEvidenceRevalidation.id))) == 0
    )


async def test_changed_fact_requires_revalidation_and_blocks_editorial_actions(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, version = await _generated_version(client, db_session, monkeypatch)
    article = await db_session.get(Article, brief["id"])
    game = await db_session.get(Game, article.game_id)
    fact = await db_session.scalar(
        select(PlayerGameStat).where(PlayerGameStat.game_id == article.game_id)
    )
    assert fact is not None
    fact.value += Decimal("5")

    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    detail = (await client.get(f"/api/v1/articles/{brief['id']}")).json()
    assert detail["status"] == "needs_revalidation"
    assert (
        detail["active_revalidation"]["previous_evidence_bundle_id"]
        == (brief["evidence_bundle"]["id"])
    )
    change_types = {
        change["change_type"] for change in detail["active_revalidation"]["changes"]
    }
    assert {"fact_changed", "approval_changed"}.issubset(change_types)

    generation = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={
            "idempotency_key": "blocked-stale-evidence-generation",
            "base_version_id": version["id"],
            "editor_instructions": "This must remain blocked.",
        },
    )
    assert generation.status_code == 409
    assert "revalidation" in generation.json()["detail"].lower()

    save = await client.post(
        f"/api/v1/articles/{brief['id']}/versions",
        json={
            "base_version_id": version["id"],
            "headline": version["headline"],
            "headline_evidence_ids": version["headline_evidence_ids"],
            "blocks": version["blocks"],
        },
    )
    assert save.status_code == 409

    ready = await client.post(
        f"/api/v1/articles/{brief['id']}/versions/{version['id']}/ready",
        json={"warning_overrides": []},
    )
    assert ready.status_code == 409


async def test_coverage_change_and_revoked_approval_explain_drift(
    client,
    db_session,
) -> None:
    coverage_brief = await _article_brief(client, db_session)
    coverage = await db_session.scalar(select(CoverageWindow))
    assert coverage is not None
    coverage.known_limitations = "Coverage now begins with the 2024-25 season."
    article = await db_session.get(Article, coverage_brief["id"])
    game = await db_session.get(Game, article.game_id)

    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    coverage_detail = (
        await client.get(f"/api/v1/articles/{coverage_brief['id']}")
    ).json()
    assert any(
        change["change_type"] == "coverage_changed"
        for change in coverage_detail["active_revalidation"]["changes"]
    )

    # Use a fresh database-backed Article suggestion to verify an explicit verdict
    # revocation also invalidates the Article immediately.
    suggestion = await _current_suggestion(db_session, coverage_brief)
    reapprove = await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion.id}/verdict",
        json={"state": "approved"},
    )
    assert reapprove.status_code == 200
    revoked = await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion.id}/verdict",
        json={"state": "rejected"},
    )
    assert revoked.status_code == 200
    detail = (await client.get(f"/api/v1/articles/{coverage_brief['id']}")).json()
    assert detail["status"] == "needs_revalidation"
    assert any(
        change["change_type"] == "approval_changed"
        and change["current_value"] == "rejected"
        for change in detail["active_revalidation"]["changes"]
    )


async def test_refresh_appends_bundle_and_review_version_without_mutating_history(
    client,
    db_session,
    monkeypatch,
) -> None:
    brief, original_version = await _generated_version(client, db_session, monkeypatch)
    article = await db_session.get(Article, brief["id"])
    game = await db_session.get(Game, article.game_id)
    fact = await db_session.scalar(
        select(PlayerGameStat).where(PlayerGameStat.game_id == article.game_id)
    )
    assert fact is not None
    fact.value += Decimal("5")
    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    replacement = await _current_suggestion(db_session, brief)
    approved = await client.patch(
        f"/api/v1/achievement-suggestions/{replacement.id}/verdict",
        json={"state": "approved"},
    )
    assert approved.status_code == 200

    refreshed = await client.post(
        f"/api/v1/articles/{brief['id']}/revalidation/refresh"
    )
    assert refreshed.status_code == 200, refreshed.json()
    current = refreshed.json()
    assert current["status"] == "in_edit"
    assert current["active_revalidation"] is None
    assert current["evidence_bundle"]["version"] == 2
    assert current["evidence_bundle"]["id"] != brief["evidence_bundle"]["id"]
    assert current["latest_version"]["version"] == 2
    assert current["latest_version"]["parent_version_id"] == original_version["id"]
    assert (
        current["latest_version"]["evidence_bundle_id"]
        == current["evidence_bundle"]["id"]
    )
    assert (
        current["latest_version"]["evidence_hash"]
        == current["evidence_bundle"]["content_hash"]
    )
    assert any(
        finding["severity"] == "error"
        for finding in current["latest_version"]["validation_results"]
    )

    original_bundle = await db_session.get(
        EvidenceBundle, brief["evidence_bundle"]["id"]
    )
    persisted_original = await db_session.get(ArticleVersion, original_version["id"])
    assert original_bundle.content_hash == brief["evidence_bundle"]["content_hash"]
    assert persisted_original.evidence_hash == original_version["evidence_hash"]
    assert await db_session.scalar(select(func.count(EvidenceBundle.id))) == 2
    assert await db_session.scalar(select(func.count(ArticleVersion.id))) == 2


async def test_refresh_requires_current_approved_evidence(client, db_session) -> None:
    brief = await _article_brief(client, db_session)
    article = await db_session.get(Article, brief["id"])
    game = await db_session.get(Game, article.game_id)
    fact = await db_session.scalar(
        select(PlayerGameStat).where(PlayerGameStat.game_id == article.game_id)
    )
    assert fact is not None
    fact.value += Decimal("5")
    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    response = await client.post(f"/api/v1/articles/{brief['id']}/revalidation/refresh")
    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()
