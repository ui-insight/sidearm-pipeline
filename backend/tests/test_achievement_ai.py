"""Verify AI ranking cannot alter deterministic Achievement Suggestion facts."""

import json
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.achievement import AchievementSuggestion
from app.models.game import Game, SourceSnapshot
from app.models.player import Player
from app.models.player_game_stat import PlayerGameStat
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.achievement_ai import (
    PROMPT_VERSION,
    UnsafeAchievementOutputError,
    rank_and_phrase_achievement_suggestions,
)
from app.services.achievement_detection import detect_achievement_suggestions
from tests.test_achievement_detection import _seed_achievement_history


class FakeMessages:
    """Return a controlled Anthropic-compatible response and retain the prompt."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


class FakeAnthropic:
    def __init__(self, payload: dict) -> None:
        self.messages = FakeMessages(payload)


def _valid_items(suggestions: list[AchievementSuggestion]) -> list[dict[str, str]]:
    phrase_by_type = {
        "career_high": ("Alice Adams set a career high with 50 Points since 2023-24."),
        "season_high": (
            "Alice Adams set a 2025-26 season high with 50 Points since 2023-24."
        ),
        "threshold_crossing": (
            "Alice Adams reached 100 career Points since 2023-24, for a verified "
            "total of 110."
        ),
        "all_time_top_n": (
            "Alice Adams recorded 50 Points, ranking No. 2 since 2023-24."
        ),
    }
    return [
        {
            "suggestion_key": suggestion.suggestion_key,
            "phrasing": phrase_by_type[suggestion.achievement_type],
        }
        for suggestion in reversed(suggestions)
    ]


async def _detected_suggestions(db_session):
    game, *_ = await _seed_achievement_history(db_session)
    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()
    suggestions = list(
        await db_session.scalars(
            select(AchievementSuggestion)
            .where(AchievementSuggestion.game_id == game.id)
            .order_by(AchievementSuggestion.suggestion_key)
        )
    )
    return game, suggestions


async def test_ranking_persists_only_validated_phrasing_and_provenance(
    db_session,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    items = _valid_items(suggestions)
    fake_client = FakeAnthropic({"ranked_suggestions": items})

    result = await rank_and_phrase_achievement_suggestions(
        db_session,
        game_id=game.id,
        client=fake_client,
    )
    await db_session.commit()

    assert [row.suggestion_key for row in result.suggestions] == [
        item["suggestion_key"] for item in items
    ]
    assert [row.ai_rank for row in result.suggestions] == [1, 2, 3, 4]
    assert all(row.phrasing for row in result.suggestions)
    assert all(row.ai_model == settings.ACHIEVEMENT_MODEL for row in result.suggestions)
    assert all(row.ai_prompt_version == PROMPT_VERSION for row in result.suggestions)
    assert all(len(row.ai_output_hash or "") == 64 for row in result.suggestions)
    assert all(row.ai_ranked_at is not None for row in result.suggestions)

    call = fake_client.messages.calls[0]
    assert call["system"].startswith("You are assisting")
    assert "source_url" not in call["messages"][0]["content"]
    assert all(
        suggestion.suggestion_key in call["messages"][0]["content"]
        for suggestion in suggestions
    )


async def test_ranking_rejects_model_generated_number_without_partial_writes(
    db_session,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    items = _valid_items(suggestions)
    items[0]["phrasing"] = re.sub(r"\d+(?:-\d+)?", "999", items[0]["phrasing"], count=1)

    with pytest.raises(UnsafeAchievementOutputError, match="fact-only phrase"):
        await rank_and_phrase_achievement_suggestions(
            db_session,
            game_id=game.id,
            client=FakeAnthropic({"ranked_suggestions": items}),
        )

    persisted = list(
        await db_session.scalars(
            select(AchievementSuggestion).where(
                AchievementSuggestion.game_id == game.id
            )
        )
    )
    assert all(row.phrasing is None for row in persisted)
    assert all(row.ai_rank is None for row in persisted)


async def test_ranking_rejects_model_generated_nonnumeric_fact(db_session) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    items = _valid_items(suggestions)
    items[0]["phrasing"] = (
        items[0]["phrasing"].removesuffix(".") + " in a championship win."
    )

    with pytest.raises(UnsafeAchievementOutputError, match="fact-only phrase"):
        await rank_and_phrase_achievement_suggestions(
            db_session,
            game_id=game.id,
            client=FakeAnthropic({"ranked_suggestions": items}),
        )

    assert all(row.phrasing is None for row in suggestions)


async def test_ranking_excludes_candidates_without_source_provenance(
    db_session,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    excluded = suggestions[0]
    excluded.source_snapshot_id = None
    excluded.phrasing = "Previously validated phrasing."
    excluded.ai_rank = 1
    excluded.ai_model = "previous-model"
    await db_session.commit()
    included = [row for row in suggestions if row.id != excluded.id]
    fake_client = FakeAnthropic({"ranked_suggestions": _valid_items(included)})

    result = await rank_and_phrase_achievement_suggestions(
        db_session,
        game_id=game.id,
        client=fake_client,
    )

    assert len(result.suggestions) == 3
    prompt = fake_client.messages.calls[0]["messages"][0]["content"]
    assert excluded.suggestion_key not in prompt
    assert excluded.phrasing is None
    assert excluded.ai_rank is None
    assert excluded.ai_model is None


async def test_ranking_rejects_missing_candidate_key(db_session) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    items = _valid_items(suggestions)[:-1]

    with pytest.raises(UnsafeAchievementOutputError, match="every verified"):
        await rank_and_phrase_achievement_suggestions(
            db_session,
            game_id=game.id,
            client=FakeAnthropic({"ranked_suggestions": items}),
        )


async def test_achievement_suggestion_api_lists_and_ranks(
    client,
    db_session,
    monkeypatch,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    fake_client = FakeAnthropic({"ranked_suggestions": _valid_items(suggestions)})
    monkeypatch.setattr(
        "app.services.achievement_ai._get_client",
        lambda: fake_client,
    )

    listed = await client.get(f"/api/v1/achievement-suggestions/games/{game.id}")
    ranked = await client.post(f"/api/v1/achievement-suggestions/games/{game.id}/rank")

    assert listed.status_code == 200
    assert len(listed.json()) == 4
    assert all(item["phrasing"] is None for item in listed.json())
    assert ranked.status_code == 200
    assert ranked.json()["prompt_version"] == PROMPT_VERSION
    assert [item["ai_rank"] for item in ranked.json()["suggestions"]] == [1, 2, 3, 4]


async def test_review_queue_persists_verdict_and_reviewer(client, db_session) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    for ai_rank, row in enumerate(suggestions, start=1):
        row.ai_rank = ai_rank
        row.phrasing = f"Verified achievement phrasing for {row.suggestion_key}."
    await db_session.commit()
    suggestion = suggestions[0]

    queue = await client.get("/api/v1/achievement-suggestions/review-queue")
    verdict = await client.patch(
        f"/api/v1/achievement-suggestions/{suggestion.id}/verdict",
        json={"state": "approved"},
    )
    approved = await client.get(
        "/api/v1/achievement-suggestions/review-queue?state=approved"
    )

    assert queue.status_code == 200
    assert queue.json()["pending_count"] == 4
    assert queue.json()["items"][0]["game_id"] == game.id
    assert len(queue.json()["items"][0]["suggestions"]) == 4
    assert verdict.status_code == 200
    assert verdict.json()["state"] == "approved"
    assert verdict.json()["reviewed_by"] == settings.PROTOTYPE_AUTH_USERNAME
    assert verdict.json()["reviewed_at"] is not None
    assert approved.json()["approved_count"] == 1
    assert approved.json()["items"][0]["suggestions"][0]["id"] == suggestion.id


async def test_review_rejection_downweights_future_matching_pattern(
    client,
    db_session,
) -> None:
    game, suggestions = await _detected_suggestions(db_session)
    career_high = next(
        row for row in suggestions if row.achievement_type == "career_high"
    )
    response = await client.patch(
        f"/api/v1/achievement-suggestions/{career_high.id}/verdict",
        json={"state": "rejected"},
    )
    assert response.status_code == 200

    player = await db_session.get(Player, career_high.player_id)
    definition = await db_session.get(StatDefinition, career_high.stat_definition_id)
    idaho = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    future_game = Game(
        source_url="https://govandals.com/boxscore/future",
        canonical_uid="sidearm:womens-basketball:2025-26:future",
        sport="womens-basketball",
        season="2025-26",
        game_date="2025-12-15",
        event_status="final",
        exhibition=False,
    )
    db_session.add(future_game)
    await db_session.flush()
    snapshot = SourceSnapshot(
        game=future_game,
        source_system="sidearm",
        source_type="boxscore_html",
        source_url=future_game.source_url,
        parser_version="test-v1",
        content_hash="future-game-hash",
        http_status=200,
        raw_body="fixture",
    )
    db_session.add(snapshot)
    await db_session.flush()
    db_session.add(
        PlayerGameStat(
            game=future_game,
            player=player,
            team=idaho,
            stat_definition=definition,
            source_snapshot=snapshot,
            value=70,
            source_field="PTS",
            source_value="70",
        )
    )
    await db_session.flush()

    await detect_achievement_suggestions(db_session, game=future_game)
    future_career_high = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == future_game.id,
            AchievementSuggestion.achievement_type == "career_high",
        )
    )

    assert future_career_high.context["prior_rejected"] == 1
    assert future_career_high.context["feedback_multiplier"] == "0.667"
    assert future_career_high.notability_score < career_high.notability_score
