"""Provider adapter for evidence-bound Article Draft generation."""

from __future__ import annotations

import json

from anthropic import APIError, AsyncAnthropic, AuthenticationError
from pydantic import ValidationError

from app.config import settings
from app.schemas.article import ArticleDraftOutput
from app.services.content_generator import _extract_json

ARTICLE_PROMPT_VERSION = "article-writer-v1"
ARTICLE_PROVIDER = "anthropic-messages"

OUTPUT_CONTRACT = {
    "headline": "string",
    "headline_evidence_ids": ["evidence-id"],
    "blocks": [
        {
            "kind": "lead | body | closing",
            "text": "string",
            "evidence_ids": ["evidence-id"],
        }
    ],
}

SYSTEM_PROMPT = """You are an athletics communications writer operating inside a
strict evidence boundary. Use only the supplied Article Brief, Evidence Bundle, and
resolved Style Guide. Do not browse, infer missing facts, calculate new statistics,
invent quotes, or add external context. Every headline and factual block must cite
one or more supplied evidence IDs. Preserve Coverage Window claim-scope wording
exactly whenever making comparative, ranking, record, career-high, or season-high
claims. Return one JSON object only, with no markdown or commentary. The required
JSON shape is: """ + json.dumps(OUTPUT_CONTRACT, separators=(",", ":"))

_client: AsyncAnthropic | None = None


def article_model() -> str:
    """Return the configured Article writer model."""
    return settings.ARTICLE_MODEL or settings.CONTENT_MODEL


def _get_client() -> AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "The Article writer is unavailable because ANTHROPIC_API_KEY is not "
            "configured. The Article Brief is unchanged and can be retried."
        )

    global _client
    if _client is None:
        kwargs = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        _client = AsyncAnthropic(**kwargs)
    return _client


async def generate_article_draft(writer_input: dict) -> ArticleDraftOutput:
    """Generate strict structured copy from the already-bounded writer input."""
    client = _get_client()
    request_payload = {
        "article_brief": writer_input["article_brief"],
        "evidence_bundle": writer_input["evidence_bundle"],
        "style_guide": writer_input["style_guide"],
    }
    if "editor_revision" in writer_input:
        request_payload["editor_revision"] = writer_input["editor_revision"]
    try:
        response = await client.messages.create(
            model=article_model(),
            max_tokens=settings.ARTICLE_GENERATION_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        request_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                }
            ],
        )
    except AuthenticationError as exc:
        raise RuntimeError(
            "The Article writer rejected its API credentials. The Article Brief "
            "is unchanged and can be retried after configuration is corrected."
        ) from exc
    except APIError as exc:
        raise RuntimeError(
            "The Article writer provider is unavailable. The Article Brief is "
            "unchanged and can be retried."
        ) from exc

    text = next(
        (block.text for block in response.content if block.type == "text"),
        None,
    )
    if not text:
        raise RuntimeError(
            "The Article writer returned no structured copy. The Article Brief "
            "is unchanged and can be retried."
        )
    parsed = _extract_json(text)
    if parsed is None:
        raise RuntimeError(
            "The Article writer returned invalid JSON. The Article Brief is "
            "unchanged and can be retried."
        )
    try:
        return ArticleDraftOutput.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError(
            "The Article writer response did not match the required structure. "
            "The Article Brief is unchanged and can be retried."
        ) from exc
