"""Behavior tests for evidence-bound Article Briefs."""

from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.models.achievement import AchievementSuggestion
from app.models.game import Game, SourceSnapshot
from tests.test_achievement_ai import _detected_suggestions


async def test_sid_creates_article_brief_from_approved_suggestion(
    client,
    db_session,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
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
            "angle": "Lead with the verified career high.",
            "audience": "Vandal fans",
            "constraints": "Keep the opening concise.",
            "idempotency_key": "article-brief-test-1",
        },
    )

    assert response.status_code == 201
    brief = response.json()
    assert brief["status"] == "brief"
    assert brief["game"]["id"] == game.id
    assert brief["article_type"] == "achievement_story"
    assert brief["angle"] == "Lead with the verified career high."
    assert brief["created_by"] == settings.PROTOTYPE_AUTH_USERNAME
    assert brief["evidence_bundle"]["content_hash"]
    evidence = brief["evidence_bundle"]["suggestions"][0]
    assert evidence["id"] == suggestion.id
    assert evidence["notability_policy_id"] == suggestion.notability_policy_id
    assert evidence["notability_policy_version"] == 1
    assert evidence["source"]["content_hash"]
    assert evidence["coverage_window"]["claim_scope"]
    assert evidence["verdict"] == {
        "state": "approved",
        "reviewed_at": verdict.json()["reviewed_at"],
        "reviewed_by": settings.PROTOTYPE_AUTH_USERNAME,
    }

    fetched = await client.get(f"/api/v1/articles/{brief['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == brief


async def test_article_brief_creation_is_idempotent(client, db_session) -> None:
    _, suggestions = await _detected_suggestions(db_session)
    suggestion = suggestions[0]
    await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion.id}/verdict",
        json={"state": "approved"},
    )
    payload = {
        "suggestion_ids": [suggestion.id],
        "article_type": "achievement_story",
        "angle": "Lead with the verified career high.",
        "audience": "Vandal fans",
        "constraints": None,
        "idempotency_key": "article-brief-idempotent",
    }

    first = await client.post("/api/v1/articles", json=payload)
    replay = await client.post("/api/v1/articles", json=payload)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()

    conflicting = await client.post(
        "/api/v1/articles",
        json={**payload, "angle": "A different editorial angle."},
    )
    assert conflicting.status_code == 409
    assert conflicting.json()["detail"] == (
        "The idempotency key was already used for a different Article Brief."
    )


async def test_article_brief_rejects_missing_pending_and_rejected_suggestions(
    client,
    db_session,
) -> None:
    _, suggestions = await _detected_suggestions(db_session)
    suggestion = suggestions[0]
    suggestion_id = suggestion.id

    async def create(suggestion_id: int, key: str):
        return await client.post(
            "/api/v1/articles",
            json={
                "suggestion_ids": [suggestion_id],
                "article_type": "achievement_story",
                "angle": "Use only approved evidence.",
                "audience": "Vandal fans",
                "constraints": None,
                "idempotency_key": key,
            },
        )

    pending = await create(suggestion_id, "article-brief-pending")
    assert pending.status_code == 409
    assert pending.json()["detail"] == (
        f"Achievement Suggestion {suggestion_id} is not approved."
    )

    await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion_id}/verdict",
        json={"state": "rejected"},
    )
    rejected = await create(suggestion_id, "article-brief-rejected")
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == (
        f"Achievement Suggestion {suggestion_id} is not approved."
    )

    missing = await create(999999, "article-brief-missing")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Achievement Suggestion not found: 999999."


async def test_article_brief_rejects_fact_changed_after_approval(
    client,
    db_session,
) -> None:
    _, suggestions = await _detected_suggestions(db_session)
    suggestion_id = suggestions[0].id
    await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion_id}/verdict",
        json={"state": "approved"},
    )
    suggestion = await db_session.scalar(
        select(AchievementSuggestion).where(AchievementSuggestion.id == suggestion_id)
    )
    assert suggestion is not None
    suggestion.computed_value += Decimal("1")
    await db_session.commit()

    response = await client.post(
        "/api/v1/articles",
        json={
            "suggestion_ids": [suggestion_id],
            "article_type": "achievement_story",
            "angle": "This must not use stale approval.",
            "audience": "Vandal fans",
            "constraints": None,
            "idempotency_key": "article-brief-stale-fact",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Achievement Suggestion {suggestion_id} changed after approval."
    )


async def test_article_brief_rejects_mixed_game_suggestions(
    client,
    db_session,
) -> None:
    _, suggestions = await _detected_suggestions(db_session)
    first = suggestions[0]
    other_game = Game(
        source_url="https://govandals.com/boxscore/article-other-game",
        canonical_uid="sidearm:womens-basketball:article-other-game",
        sport="womens-basketball",
        season="2025-26",
        game_date="2025-12-20",
        event_status="final",
        home_team="Idaho",
        away_team="Montana",
        home_score=78,
        away_score=70,
        exhibition=False,
    )
    db_session.add(other_game)
    await db_session.flush()
    other_source = SourceSnapshot(
        game_id=other_game.id,
        source_system="sidearm",
        source_type="boxscore_html",
        source_url=other_game.source_url,
        parser_version="test-v1",
        content_hash="other-game-source-hash",
        http_status=200,
        raw_body="fixture",
    )
    db_session.add(other_source)
    await db_session.flush()
    second = AchievementSuggestion(
        game_id=other_game.id,
        player_id=first.player_id,
        stat_definition_id=first.stat_definition_id,
        notability_policy_id=first.notability_policy_id,
        coverage_window_id=first.coverage_window_id,
        source_snapshot_id=other_source.id,
        suggestion_key=f"{first.suggestion_key}:other-game",
        achievement_type=first.achievement_type,
        scope=first.scope,
        computed_value=first.computed_value,
        comparison_value=first.comparison_value,
        rank=first.rank,
        notability_score=first.notability_score,
        context=first.context,
        coverage_context=first.coverage_context,
        phrasing=first.phrasing,
        ai_rank=1,
        state="pending",
    )
    db_session.add(second)
    await db_session.commit()
    first_id = first.id
    second_id = second.id
    for suggestion_id in (first_id, second_id):
        verdict = await client.patch(
            f"/api/v1/achievement-suggestions/{suggestion_id}/verdict",
            json={"state": "approved"},
        )
        assert verdict.status_code == 200

    response = await client.post(
        "/api/v1/articles",
        json={
            "suggestion_ids": [first_id, second_id],
            "article_type": "game_recap",
            "angle": "Do not combine separate games.",
            "audience": "Vandal fans",
            "constraints": None,
            "idempotency_key": "article-brief-mixed-game",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "All Achievement Suggestions must belong to the same game."
    )
