"""Regression tests for upstream game-coverage generation failures."""

import json
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from anthropic import NotFoundError

from app.models.game import Game
from app.schemas.game import NormalizedPlayerGameStatRead
from app.services import content_generator


def _game_with_player_evidence() -> Game:
    return Game(
        id=85,
        home_team="Idaho",
        away_team="Montana State",
        home_score=73,
        away_score=70,
    )


def _normalized_player_evidence() -> list[NormalizedPlayerGameStatRead]:
    return [
        NormalizedPlayerGameStatRead(
            player_id=3,
            player_name="Gardner, Kyra",
            team_id=1,
            team_name="Idaho",
            stat_key="points",
            display_label="Points",
            value=Decimal(18),
            value_type="integer",
            source_field="PTS",
            source_value="18",
            source_snapshot_id=89,
        )
    ]


async def test_generate_coverage_rejects_score_only_game(monkeypatch) -> None:
    """Do not ask a model to pad a final score into an unsupported article."""

    def unexpected_client():
        raise AssertionError(
            "The provider must not be called without detailed evidence"
        )

    monkeypatch.setattr(content_generator, "_get_client", unexpected_client)

    with pytest.raises(
        content_generator.InsufficientGameEvidenceError,
        match="Reingest the box score",
    ):
        await content_generator.generate_coverage(
            Game(
                id=85,
                home_team="Idaho",
                away_team="Montana State",
                home_score=73,
                away_score=70,
            )
        )


async def test_generate_coverage_uses_evidence_aware_writing_contract(
    monkeypatch,
) -> None:
    """Keep a stats-only recap short and forbid unsupported game narrative."""
    captured_request = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured_request.update(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        text=json.dumps(
                            {
                                "headline": "Gardner leads Idaho past Montana State",
                                "recap": (
                                    "Idaho defeated Montana State 73-70. Gardner, "
                                    "Kyra scored 18 points and made four 3-pointers."
                                ),
                                "spotlight_player": "Gardner, Kyra",
                                "spotlight_body": (
                                    "Gardner, Kyra scored 18 points with seven "
                                    "rebounds and four made 3-pointers."
                                ),
                                "social_post": (
                                    "Idaho 73, Montana State 70. Gardner, Kyra "
                                    "finished with 18 points and seven rebounds."
                                ),
                            }
                        ),
                    )
                ],
                usage=None,
            )

    class FakeClient:
        messages = FakeMessages()

    game = _game_with_player_evidence()
    monkeypatch.setattr(content_generator, "_get_client", lambda: FakeClient())

    coverage = await content_generator.generate_coverage(
        game,
        _normalized_player_evidence(),
    )

    user_message = captured_request["messages"][0]["content"]
    assert coverage.spotlight_player == "Gardner, Kyra"
    assert captured_request["temperature"] == 0.2
    assert "140-200 words" in user_message
    assert "250-350 words" not in user_message
    assert "Do not describe game flow, turning points, runs" in user_message
    assert "Every recap paragraph must contain" in user_message
    assert "do not mention that data is missing" in user_message
    assert '"normalized_player_stats"' in user_message
    assert '"source_value": "18"' in user_message


async def test_generate_coverage_retries_unsupported_game_flow(monkeypatch) -> None:
    """Reject plausible-sounding chronology when no play sequence supports it."""
    bad_coverage = {
        "headline": "Idaho survives Montana State",
        "recap": (
            "Idaho defeated Montana State 73-70, surviving a late push. The "
            "Vandals controlled key possessions down the stretch and relied on "
            "crucial free throws when the game was on the line."
        ),
        "spotlight_player": "Gardner, Kyra",
        "spotlight_body": "Gardner, Kyra led Idaho with 18 points.",
        "social_post": "Idaho 73, Montana State 70. Gardner scored 18 points.",
    }
    good_coverage = {
        "headline": "Gardner's 18 points lead Idaho past Montana State",
        "recap": (
            "Idaho defeated Montana State 73-70. Gardner, Kyra scored 18 "
            "points, made four 3-pointers and collected seven rebounds."
        ),
        "spotlight_player": "Gardner, Kyra",
        "spotlight_body": (
            "Gardner, Kyra scored 18 points with seven rebounds and four "
            "made 3-pointers."
        ),
        "social_post": (
            "Idaho 73, Montana State 70. Gardner finished with 18 points "
            "and seven rebounds."
        ),
    }
    responses = [bad_coverage, good_coverage]
    calls = 0

    class FakeMessages:
        async def create(self, **kwargs):
            nonlocal calls
            response = responses[calls]
            calls += 1
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=json.dumps(response))],
                usage=None,
            )

    class FakeClient:
        messages = FakeMessages()

    game = _game_with_player_evidence()
    monkeypatch.setattr(content_generator, "_get_client", lambda: FakeClient())

    coverage = await content_generator.generate_coverage(
        game,
        _normalized_player_evidence(),
    )

    assert calls == 2
    assert coverage.headline == good_coverage["headline"]


async def test_generate_coverage_retries_invalid_json_once(monkeypatch) -> None:
    """Recover from one transient provider formatting failure."""
    responses = [
        "not valid JSON",
        json.dumps(
            {
                "headline": "Idaho wins",
                "recap": (
                    "Idaho defeated Montana State 73-70 as Gardner, Kyra "
                    "scored 18 points."
                ),
                "spotlight_player": "Gardner, Kyra",
                "spotlight_body": "Gardner, Kyra led Idaho with 18 points.",
                "social_post": "Idaho 73, Montana State 70. Gardner scored 18.",
            }
        ),
    ]
    calls = 0

    class FakeMessages:
        async def create(self, **kwargs):
            nonlocal calls
            text = responses[calls]
            calls += 1
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=text)],
                usage=None,
            )

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(content_generator, "_get_client", lambda: FakeClient())

    coverage = await content_generator.generate_coverage(
        _game_with_player_evidence(),
        _normalized_player_evidence(),
    )

    assert calls == 2
    assert coverage.headline == "Idaho wins"


async def test_generate_coverage_reports_unavailable_model(monkeypatch) -> None:
    """Turn a provider model 404 into an actionable application error."""
    request = httpx.Request("POST", "https://mindrouter.example.edu/messages")
    response = httpx.Response(404, request=request)

    class FakeMessages:
        async def create(self, **kwargs):
            raise NotFoundError(
                "model not found",
                response=response,
                body={
                    "type": "error",
                    "error": {
                        "type": "not_found_error",
                        "message": "model: claude-opus-4-7",
                    },
                },
            )

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(content_generator, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(content_generator.settings, "CONTENT_MODEL", "claude-opus-4-7")

    with pytest.raises(
        RuntimeError,
        match=(
            "Configured content model 'claude-opus-4-7' is unavailable from "
            "the upstream provider"
        ),
    ):
        await content_generator.generate_coverage(
            _game_with_player_evidence(),
            _normalized_player_evidence(),
        )
