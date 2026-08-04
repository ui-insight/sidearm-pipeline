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
from app.schemas.game import NormalizedPlayerGameStatRead

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a veteran collegiate athletics communications writer \
on the staff of a university sports information department. You turn raw \
boxscore data into publication-ready coverage for the athletic department's \
website and social accounts.

House style:
- AP style, third person, past tense.
- Lead with the outcome (score and who won), then verified performance details.
- Describe game flow or a turning point only when the supplied scoring plays \
  directly support it.
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


class InsufficientGameEvidenceError(RuntimeError):
    """Raised when a game lacks enough box-score detail for grounded coverage."""


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


def _serialize_game(
    game: Game,
    normalized_player_stats: list[NormalizedPlayerGameStatRead],
) -> dict:
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
        "normalized_player_stats": _group_normalized_player_stats(
            normalized_player_stats
        ),
    }


def _group_normalized_player_stats(
    stats: list[NormalizedPlayerGameStatRead],
) -> list[dict]:
    """Group atomic warehouse facts into compact, source-backed player lines."""
    players: dict[tuple[int, str, str | None], dict] = {}
    for stat in stats:
        key = (stat.player_id, stat.player_name, stat.team_name)
        player = players.setdefault(
            key,
            {
                "player": stat.player_name,
                "team": stat.team_name,
                "stats": {},
            },
        )
        player["stats"][stat.stat_key] = {
            "label": stat.display_label,
            "value": str(stat.value),
            "source_field": stat.source_field,
            "source_value": stat.source_value,
        }
    return list(players.values())


def _schema_doc(recap_contract: str) -> str:
    return f"""Your JSON object must have exactly these keys:
{{
  "headline":         string  // punchy news headline under 90 characters
  "recap":            string  // {recap_contract}
  "spotlight_player": string  // standout player name as written in the stats
  "spotlight_body":   string  // 2-3 sentence feature with concrete stats
  "social_post":      string  // under 280 characters with score + stat nugget
}}"""


def _evidence_rules(payload: dict) -> tuple[str, str]:
    if payload["scoring_plays"]:
        return (
            "200-300 words in 2-3 short paragraphs; describe chronology only from "
            "the supplied scoring plays",
            "Scoring plays are available. Any statement about game flow, a run, a "
            "turning point, or late-game execution must cite those plays directly.",
        )
    return (
        "140-200 words in 2 short paragraphs focused on the result and stat lines",
        "No scoring plays are available. Do not describe game flow, turning points, "
        "runs, rallies, momentum, late-game execution, or how the score developed.",
    )


def _has_detailed_evidence(payload: dict) -> bool:
    return bool(
        payload["team_stats"]
        or payload["scoring_plays"]
        or any(group["rows"] for group in payload["player_stats"])
        or payload["normalized_player_stats"]
    )


_UNSUPPORTED_WITHOUT_PLAYS = (
    "late push",
    "down the stretch",
    "final minutes",
    "key possessions",
    "crucial free throws",
    "timely possessions",
    "when the game was on the line",
    "pulled away",
    "pull away",
    "rallied",
    "survived",
)

_UNSUPPORTED_FROM_BOXSCORE = (
    "home crowd",
    "coaching staff",
    "postseason resume",
    "next opponent",
    "grit and determination",
    "experience and fundamentals",
    "top-tier opponent",
    "testament to",
)

_UNSUPPORTED_COMPARATIVES = (
    "game-high",
    "game high",
    "led all scorers",
    "most in the game",
)


def _player_names(payload: dict) -> list[str]:
    names = [row["player"] for row in payload["normalized_player_stats"]]
    for group in payload["player_stats"]:
        columns = group["columns"]
        player_index = next(
            (
                index
                for index, column in enumerate(columns)
                if str(column).strip().lower() == "player"
            ),
            None,
        )
        if player_index is None:
            continue
        for row in group["rows"]:
            if not isinstance(row, list) or player_index >= len(row):
                continue
            name = re.sub(r"^\s*\d+\s*", "", str(row[player_index])).strip()
            if name:
                names.append(name)
    return names


def _coverage_quality_issues(
    coverage: GeneratedCoverage,
    payload: dict,
) -> list[str]:
    """Reject obvious unsupported filler before a legacy draft is persisted."""
    recap = coverage.recap.lower()
    coverage_text = " ".join(
        (
            coverage.headline,
            coverage.recap,
            coverage.spotlight_body,
            coverage.social_post,
        )
    ).lower()
    issues: list[str] = []

    if not payload["scoring_plays"]:
        matched = [
            phrase for phrase in _UNSUPPORTED_WITHOUT_PLAYS if phrase in coverage_text
        ]
        if matched:
            issues.append("unsupported game-flow language: " + ", ".join(matched))

    matched = [
        phrase for phrase in _UNSUPPORTED_FROM_BOXSCORE if phrase in coverage_text
    ]
    if matched:
        issues.append("unsupported contextual language: " + ", ".join(matched))

    matched = [
        phrase for phrase in _UNSUPPORTED_COMPARATIVES if phrase in coverage_text
    ]
    if matched:
        issues.append("unsupported comparative language: " + ", ".join(matched))

    expected_scores = [payload["home_score"], payload["away_score"]]
    if any(score is not None and str(score) not in recap for score in expected_scores):
        issues.append("recap does not include the final score")

    names = _player_names(payload)
    if names and not any(name.lower() in recap for name in names):
        issues.append("recap does not name a player from the supplied stat tables")

    return issues


async def generate_coverage(
    game: Game,
    normalized_player_stats: list[NormalizedPlayerGameStatRead] | None = None,
) -> GeneratedCoverage:
    """Call Claude to produce structured coverage for this game."""
    payload = _serialize_game(game, normalized_player_stats or [])
    if not _has_detailed_evidence(payload):
        raise InsufficientGameEvidenceError(
            "Detailed box-score evidence is unavailable for this game. Reingest "
            "the box score before generating coverage."
        )

    client = _get_client()
    recap_contract, chronology_rule = _evidence_rules(payload)

    user_message = (
        "Generate coverage for the game below. The boxscore JSON is authoritative "
        "— every factual statement and number must be directly supported by it. "
        "Pick the spotlight player by looking across all player stat categories "
        "and choosing the strongest performance, prioritizing the winning team.\n\n"
        "Evidence rules:\n"
        f"- {chronology_rule}\n"
        "- Every recap paragraph must contain at least one concrete score or stat "
        "from the boxscore.\n"
        "- Do not infer crowd reaction, coaching strategy, emotion, stakes, "
        "standings, postseason implications, or future schedule context.\n"
        "- Do not call a performance game-high or compare across both teams; the "
        "payload may contain resolved player facts for only one team.\n"
        "- Omit unsupported ideas entirely; do not mention that data is missing.\n"
        "- Avoid generic conclusions about grit, resilience, confidence, depth, "
        "pressure, or what the result says about a team. Do not repeat the lead.\n\n"
        f"{_schema_doc(recap_contract)}\n\n"
        f"BOXSCORE:\n{json.dumps(payload, indent=2)}"
    )
    retry_feedback = ""

    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        try:
            response = await client.messages.create(
                model=settings.CONTENT_MODEL,
                max_tokens=4000,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": user_message + retry_feedback,
                    }
                ],
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
        validation_issues: list[str] = []
        if payload_json is not None:
            try:
                coverage = GeneratedCoverage.model_validate(payload_json)
            except ValidationError:
                coverage = None
            if coverage is not None:
                validation_issues = _coverage_quality_issues(coverage, payload)
                if not validation_issues:
                    logger.info(
                        "Generated coverage game_id=%s model=%s usage=%s attempt=%s",
                        game.id,
                        settings.CONTENT_MODEL,
                        getattr(response, "usage", None),
                        attempt,
                    )
                    return coverage

        if attempt < _MAX_GENERATION_ATTEMPTS:
            if validation_issues:
                retry_feedback = (
                    "\n\nYour previous response was rejected for: "
                    + "; ".join(validation_issues)
                    + ". Rewrite it using only the supplied evidence."
                )
            logger.warning(
                "Coverage response failed validation; retrying game_id=%s "
                "model=%s attempt=%s issues=%s",
                game.id,
                settings.CONTENT_MODEL,
                attempt,
                validation_issues or ["invalid structured content"],
            )
            continue

        if text:
            logger.error("Could not validate model output: %s", text[:500])
            if validation_issues:
                raise RuntimeError(
                    "Model response contained unsupported or insufficiently "
                    "grounded coverage."
                )
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
