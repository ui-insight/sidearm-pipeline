"""AI sports-writing generator.

Takes a fully-loaded Game (with team stats, player stats, scoring plays) and
produces a Fanword-style coverage bundle: headline, recap, player spotlight,
and social post — all in one call via the Anthropic SDK.

The SDK is pointed at whatever Messages-API-compatible gateway you like:
- Default: Anthropic's API (use an ``sk-ant-...`` key).
- University of Idaho: set ``ANTHROPIC_BASE_URL=https://mindrouter.uidaho.edu/anthropic``
  and use a MindRouter key. Pick an available MindRouter model via
  ``CONTENT_MODEL`` — MindRouter proxies to Llama/Qwen/etc., not to Claude.

The prompt asks the model to emit a single JSON object matching a documented
schema. That's the lowest-common-denominator way to get structured output
across different providers without depending on Anthropic's ``output_config``
extension.
"""

from __future__ import annotations

import json
import logging
import re

from anthropic import APIStatusError, AsyncAnthropic, AuthenticationError
from pydantic import ValidationError

from app.config import settings
from app.models.game import Game
from app.schemas.content import GeneratedCoverage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a veteran collegiate athletics communications writer \
on the staff of a university sports information department. You turn raw \
boxscore data into publication-ready coverage for the athletic department's \
website and social accounts.

House style:
- AP style, third person, past tense.
- Lead with the outcome (score and who won), then the turning point, then \
  supporting context.
- Name players as they appear in the stat tables ("Last, First").
- Cite concrete numbers from the provided stats — never invent statistics, \
  quotes, attendance, weather, or injuries.
- Keep hype measured. Avoid clichés like "all cylinders", "statement win", \
  or "came to play".
- Do NOT use emoji in the recap or spotlight. At most one tasteful emoji is \
  allowed in the social post.

You respond with a single JSON object and nothing else. No prose outside the \
JSON, no markdown code fences, no commentary."""


_client: AsyncAnthropic | None = None
_MAX_GENERATION_ATTEMPTS = 2


def _get_client() -> AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. Set it in .env to enable "
            "AI content generation."
        )

    global _client
    if _client is None:
        kwargs = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        _client = AsyncAnthropic(**kwargs)
    return _client


def _serialize_game(game: Game) -> dict:
    """Flatten a Game ORM record into a compact JSON payload for the model."""
    return {
        "sport": game.sport,
        "season": game.season,
        "game_date": game.game_date,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "home_score": game.home_score,
        "away_score": game.away_score,
        "title": game.title,
        "scoring_plays": [
            {
                "period": play.period,
                "clock": play.clock,
                "team": play.team,
                "description": play.description,
                "away_score": play.away_score,
                "home_score": play.home_score,
            }
            for play in sorted(game.scoring_plays, key=lambda p: p.sort_order)
        ],
        "team_stats": [
            {
                "stat": stat.stat_name,
                "home": stat.home_value,
                "away": stat.away_value,
            }
            for stat in sorted(game.team_stats, key=lambda s: s.sort_order)
        ],
        "player_stats": [
            {
                "category": group.category,
                "team": group.team,
                "columns": group.columns,
                "rows": group.rows,
            }
            for group in game.player_stats
        ],
    }


_SCHEMA_DOC = """Your JSON object must have exactly these keys:
{
  "headline":         string  // punchy news headline under 90 characters
  "recap":            string  // 250-350 word, 2-3 paragraph game recap in AP style
  "spotlight_player": string  // standout player name as written in the stats
  "spotlight_body":   string  // 2-3 sentence feature with concrete stats
  "social_post":      string  // under 280 characters with score + stat nugget
}"""


async def generate_coverage(game: Game) -> GeneratedCoverage:
    """Call Claude to produce structured coverage for this game."""
    client = _get_client()

    payload = _serialize_game(game)

    user_message = (
        "Generate coverage for the game below. The boxscore JSON is authoritative "
        "— every number you cite must come from it. Pick the spotlight player by "
        "looking across all player stat categories and choosing the single most "
        "dominant performance, regardless of team.\n\n"
        f"{_SCHEMA_DOC}\n\n"
        f"BOXSCORE:\n{json.dumps(payload, indent=2)}"
    )

    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        try:
            response = await client.messages.create(
                model=settings.CONTENT_MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except AuthenticationError as exc:
            raise RuntimeError(
                "Upstream rejected the API key. Check ANTHROPIC_API_KEY "
                "(and ANTHROPIC_BASE_URL if using a gateway like MindRouter)."
            ) from exc
        except APIStatusError as exc:
            if exc.status_code == 404:
                raise RuntimeError(
                    f"Configured content model '{settings.CONTENT_MODEL}' is "
                    "unavailable from the upstream provider. Check CONTENT_MODEL "
                    "and ANTHROPIC_BASE_URL."
                ) from exc
            raise RuntimeError(
                f"Upstream content provider returned status {exc.status_code}. "
                "Try again or check the configured provider."
            ) from exc

        text = next(
            (block.text for block in response.content if block.type == "text"),
            None,
        )
        payload_json = _extract_json(text) if text else None
        if payload_json is not None:
            try:
                coverage = GeneratedCoverage.model_validate(payload_json)
            except ValidationError:
                coverage = None
            if coverage is not None:
                logger.info(
                    "Generated coverage game_id=%s model=%s usage=%s attempt=%s",
                    game.id,
                    settings.CONTENT_MODEL,
                    getattr(response, "usage", None),
                    attempt,
                )
                return coverage

        if attempt < _MAX_GENERATION_ATTEMPTS:
            logger.warning(
                "Coverage response was not valid structured content; retrying "
                "game_id=%s model=%s attempt=%s",
                game.id,
                settings.CONTENT_MODEL,
                attempt,
            )
            continue

        if text:
            logger.error("Could not validate model output: %s", text[:500])
            raise RuntimeError("Model response was not valid structured content.")
        raise RuntimeError("Model returned no text block.")

    raise RuntimeError("Coverage generation exhausted its retry budget.")


def _extract_json(text: str) -> dict | None:
    """Pull a JSON object out of a model response.

    Prefers a fenced ```json block; otherwise falls back to the first balanced
    ``{...}`` span. Also attempts a repair pass when a model (often a local
    Llama served via MindRouter) emits valid JSON but drops the final closing
    braces.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        parsed = _try_parse(fenced.group(1))
        if parsed is not None:
            return parsed

    parsed = _try_parse(text.strip())
    if parsed is not None:
        return parsed

    start = text.find("{")
    if start == -1:
        return None

    candidate = text[start:]
    depth = 0
    last_close = -1
    for i, ch in enumerate(candidate):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                last_close = i
                parsed = _try_parse(candidate[: i + 1])
                if parsed is not None:
                    return parsed

    if depth > 0:
        repaired = _repair_truncated_json(candidate, depth)
        parsed = _try_parse(repaired)
        if parsed is not None:
            return parsed

    if last_close > 0:
        return _try_parse(candidate[: last_close + 1])

    return None


def _try_parse(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _repair_truncated_json(candidate: str, open_depth: int) -> str:
    """Attempt to close an unbalanced JSON object dropped mid-stream.

    Handles the common case where a local model finishes the last string
    value but omits the trailing ``}``. Trims any partial trailing token
    (unclosed string, dangling comma) before appending the needed braces.
    """
    trimmed = candidate.rstrip()

    # If we're in the middle of a string, drop everything back to the last
    # fully-closed value so json.loads doesn't choke on an unterminated string.
    in_string = False
    escape = False
    last_safe = 0
    for i, ch in enumerate(trimmed):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string and ch in ",}":
            last_safe = i + 1

    if in_string:
        trimmed = trimmed[:last_safe].rstrip().rstrip(",")
    else:
        trimmed = trimmed.rstrip(",")

    return trimmed + "}" * open_depth
