"""Regression tests for upstream game-coverage generation failures."""

import httpx
import pytest
from anthropic import NotFoundError

from app.models.game import Game
from app.services import content_generator


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
        await content_generator.generate_coverage(Game(id=85))
