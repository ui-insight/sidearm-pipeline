"""Rank and phrase verified Achievement Suggestions without changing facts."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from anthropic import AsyncAnthropic, AuthenticationError
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.achievement import AchievementSuggestion
from app.models.game import Game, SourceSnapshot
from app.models.player import Player
from app.models.stat_definition import StatDefinition
from app.schemas.achievement import AchievementAIOutput

logger = logging.getLogger(__name__)

PROMPT_VERSION = "achievement-ranking-v1"
SYSTEM_PROMPT = """You are assisting a collegiate sports information director.

You receive verified Achievement Suggestion records computed by the athletics
warehouse. Rank their editorial usefulness and select one supplied, SID-ready
phrase for each suggestion.

Hard boundaries:
- Use every suggestion_key exactly once. Never create or omit a candidate.
- Return phrasing exactly matching one of that candidate's allowed_phrasings.
- Treat all supplied facts as immutable. Do not calculate or infer new facts.
- Use numerals exactly as supplied. Never spell out a number or add a numeral.
- Preserve the exact player name, metric label, and coverage qualifier.
- Do not turn a partial-history statement into an all-time or program record.
- Keep each sentence factual, concise, and free of hype, quotes, or injuries.

Return one JSON object and nothing else. The object must contain only a
ranked_suggestions array. Each array item must contain only suggestion_key and
phrasing. Array order is the editorial ranking."""

_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d+(?:,\d{3})*(?:\.\d+)?(?:-\d+)?")
_NUMBER_WORD_PATTERN = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
    r"million)\b",
    flags=re.IGNORECASE,
)
_OVERCLAIM_PATTERN = re.compile(
    r"\b(?:all[- ]time|school record|program record|most in program history)\b",
    flags=re.IGNORECASE,
)


class AchievementAIError(RuntimeError):
    """Base error for a ranking request that must not be persisted."""


class NoVerifiedAchievementSuggestionsError(AchievementAIError):
    """Raised when a game has no source-backed candidates safe for the model."""


class UnsafeAchievementOutputError(AchievementAIError):
    """Raised when model output changes or adds factual content."""


@dataclass(frozen=True)
class VerifiedCandidate:
    """One source-backed suggestion plus immutable display context."""

    suggestion: AchievementSuggestion
    player_name: str
    stat_key: str
    stat_label: str
    phrase_facts: dict[str, str | int | None]
    phrase_numbers: frozenset[str]
    required_numbers: frozenset[str]
    claim_scope: str
    season: str | None


@dataclass(frozen=True)
class AchievementAIResult:
    """Metadata for one validated and persisted model call."""

    game_id: int
    model: str
    prompt_version: str
    suggestions: list[AchievementSuggestion]


async def rank_and_phrase_achievement_suggestions(
    db: AsyncSession,
    *,
    game_id: int,
    client: AsyncAnthropic | None = None,
) -> AchievementAIResult:
    """Rank verified candidates and persist only fact-preserving phrasing."""
    game = await db.get(Game, game_id)
    if game is None:
        raise NoVerifiedAchievementSuggestionsError("Game not found.")

    candidates = await _verified_candidates(db, game=game)
    if not candidates:
        raise NoVerifiedAchievementSuggestionsError(
            "No source-backed Achievement Suggestions with known coverage are "
            "available for this game."
        )
    candidates = candidates[: settings.ACHIEVEMENT_AI_MAX_CANDIDATES]

    model_client = client or _get_client()
    user_message = _user_message(candidates)
    try:
        response = await model_client.messages.create(
            model=settings.ACHIEVEMENT_MODEL,
            max_tokens=6000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except AuthenticationError as exc:
        raise AchievementAIError(
            "Upstream rejected the AI API key. Check ANTHROPIC_API_KEY and "
            "ANTHROPIC_BASE_URL."
        ) from exc
    except Exception as exc:
        raise AchievementAIError(f"Achievement ranking request failed: {exc}") from exc

    text = next(
        (block.text for block in response.content if block.type == "text"),
        None,
    )
    if not text:
        raise UnsafeAchievementOutputError("Model returned no text block.")
    output = _parse_output(text)
    _validate_output(output, candidates)

    await db.execute(
        update(AchievementSuggestion)
        .where(
            AchievementSuggestion.game_id == game_id,
            AchievementSuggestion.state == "pending",
        )
        .values(
            phrasing=None,
            ai_rank=None,
            ai_model=None,
            ai_prompt_version=None,
            ai_output_hash=None,
            ai_ranked_at=None,
        )
    )
    candidates_by_key = {
        candidate.suggestion.suggestion_key: candidate for candidate in candidates
    }
    now = datetime.now(UTC)
    ranked: list[AchievementSuggestion] = []
    for ai_rank, item in enumerate(output.ranked_suggestions, start=1):
        suggestion = candidates_by_key[item.suggestion_key].suggestion
        suggestion.phrasing = item.phrasing.strip()
        suggestion.ai_rank = ai_rank
        suggestion.ai_model = settings.ACHIEVEMENT_MODEL
        suggestion.ai_prompt_version = PROMPT_VERSION
        suggestion.ai_output_hash = hashlib.sha256(
            suggestion.phrasing.encode("utf-8")
        ).hexdigest()
        suggestion.ai_ranked_at = now
        ranked.append(suggestion)
    await db.flush()

    logger.info(
        "Ranked achievement suggestions game_id=%s candidates=%s model=%s "
        "prompt_version=%s usage=%s",
        game_id,
        len(ranked),
        settings.ACHIEVEMENT_MODEL,
        PROMPT_VERSION,
        getattr(response, "usage", None),
    )
    return AchievementAIResult(
        game_id=game_id,
        model=settings.ACHIEVEMENT_MODEL,
        prompt_version=PROMPT_VERSION,
        suggestions=ranked,
    )


def _get_client() -> AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise AchievementAIError(
            "ANTHROPIC_API_KEY is not configured. Deterministic Achievement "
            "Suggestions remain available without AI phrasing."
        )
    kwargs = {"api_key": settings.ANTHROPIC_API_KEY}
    if settings.ANTHROPIC_BASE_URL:
        kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
    return AsyncAnthropic(**kwargs)


async def _verified_candidates(
    db: AsyncSession,
    *,
    game: Game,
) -> list[VerifiedCandidate]:
    rows = (
        await db.execute(
            select(AchievementSuggestion, Player, StatDefinition)
            .join(Player, Player.id == AchievementSuggestion.player_id)
            .join(
                StatDefinition,
                StatDefinition.id == AchievementSuggestion.stat_definition_id,
            )
            .join(
                SourceSnapshot,
                SourceSnapshot.id == AchievementSuggestion.source_snapshot_id,
            )
            .where(
                AchievementSuggestion.game_id == game.id,
                AchievementSuggestion.state == "pending",
            )
            .order_by(
                AchievementSuggestion.notability_score.desc(),
                AchievementSuggestion.suggestion_key,
            )
        )
    ).all()
    candidates: list[VerifiedCandidate] = []
    for suggestion, player, definition in rows:
        completeness = suggestion.coverage_context.get("completeness")
        claim_scope = str(suggestion.coverage_context.get("claim_scope") or "")
        if completeness not in {"complete", "partial"} or not claim_scope:
            continue
        phrase_facts = _phrase_facts(suggestion, game=game)
        candidates.append(
            VerifiedCandidate(
                suggestion=suggestion,
                player_name=player.display_name,
                stat_key=definition.stat_key,
                stat_label=definition.display_label,
                phrase_facts=phrase_facts,
                phrase_numbers=frozenset(_numbers(json.dumps(phrase_facts))),
                required_numbers=frozenset(_required_numbers(suggestion, game=game)),
                claim_scope=claim_scope,
                season=game.season,
            )
        )
    return candidates


def _user_message(candidates: list[VerifiedCandidate]) -> str:
    payload = [
        {
            "suggestion_key": candidate.suggestion.suggestion_key,
            "player_name": candidate.player_name,
            "achievement_type": candidate.suggestion.achievement_type,
            "stat_key": candidate.stat_key,
            "stat_label": candidate.stat_label,
            "deterministic_ranking_input": {
                "notability_score": _decimal_text(candidate.suggestion.notability_score)
            },
            "immutable_phrase_facts": candidate.phrase_facts,
            "allowed_phrasings": sorted(_allowed_phrases(candidate)),
        }
        for candidate in candidates
    ]
    schema = {
        "ranked_suggestions": [
            {"suggestion_key": "existing key", "phrasing": "one sentence"}
        ]
    }
    return (
        "Rank and phrase the verified candidates below. The deterministic score "
        "is a ranking input only and must never appear in phrasing. Use the exact "
        "coverage qualifier in every sentence.\n\n"
        f"RESPONSE SHAPE:\n{json.dumps(schema, indent=2)}\n\n"
        f"VERIFIED CANDIDATES:\n{json.dumps(payload, indent=2)}"
    )


def _phrase_facts(suggestion: AchievementSuggestion, *, game: Game) -> dict:
    context = suggestion.context
    facts = {
        "game_value": _decimal_text(Decimal(str(context["game_value"]))),
        "computed_value": _decimal_text(suggestion.computed_value),
        "comparison_value": (
            _decimal_text(suggestion.comparison_value)
            if suggestion.comparison_value is not None
            else None
        ),
        "program_rank": suggestion.rank,
        "season": game.season,
        "claim_scope": suggestion.coverage_context["claim_scope"],
    }
    for key in (
        "previous_high",
        "threshold",
        "career_total_before",
        "career_total_after",
        "top_n",
        "tied_at_rank",
    ):
        value = context.get(key)
        if value is not None:
            facts[key] = _fact_value(value)
    return facts


def _required_numbers(
    suggestion: AchievementSuggestion,
    *,
    game: Game,
) -> set[str]:
    numbers = {_decimal_text(suggestion.computed_value)}
    if suggestion.achievement_type == "threshold_crossing":
        numbers = {_decimal_text(Decimal(str(suggestion.context["threshold"])))}
    elif suggestion.achievement_type == "all_time_top_n":
        if suggestion.rank is None:
            raise UnsafeAchievementOutputError("Top-N suggestion is missing rank.")
        numbers.add(str(suggestion.rank))
    elif suggestion.achievement_type == "season_high" and game.season:
        numbers.add(game.season)
    return numbers


def _validate_output(
    output: AchievementAIOutput,
    candidates: list[VerifiedCandidate],
) -> None:
    expected_keys = [candidate.suggestion.suggestion_key for candidate in candidates]
    returned_keys = [item.suggestion_key for item in output.ranked_suggestions]
    if len(returned_keys) != len(set(returned_keys)):
        raise UnsafeAchievementOutputError("Model returned a duplicate suggestion key.")
    if set(returned_keys) != set(expected_keys):
        raise UnsafeAchievementOutputError(
            "Model must return every verified suggestion key exactly once."
        )

    candidates_by_key = {
        candidate.suggestion.suggestion_key: candidate for candidate in candidates
    }
    for item in output.ranked_suggestions:
        _validate_phrase(item.phrasing.strip(), candidates_by_key[item.suggestion_key])


def _validate_phrase(phrase: str, candidate: VerifiedCandidate) -> None:
    if phrase not in _allowed_phrases(candidate):
        raise UnsafeAchievementOutputError(
            f"Phrasing for {candidate.suggestion.suggestion_key} did not match "
            "a supplied fact-only phrase."
        )
    lowered = phrase.casefold()
    if candidate.player_name.casefold() not in lowered:
        raise UnsafeAchievementOutputError(
            f"Phrasing for {candidate.suggestion.suggestion_key} changed or omitted "
            "the player name."
        )
    if candidate.stat_label.casefold() not in lowered:
        raise UnsafeAchievementOutputError(
            f"Phrasing for {candidate.suggestion.suggestion_key} changed or omitted "
            "the metric label."
        )
    if candidate.claim_scope.casefold() not in lowered:
        raise UnsafeAchievementOutputError(
            f"Phrasing for {candidate.suggestion.suggestion_key} omitted the "
            "Coverage Window qualifier."
        )
    if _NUMBER_WORD_PATTERN.search(phrase):
        raise UnsafeAchievementOutputError("Phrasing must use supplied numerals only.")

    returned_numbers = _numbers(phrase)
    if not returned_numbers.issubset(candidate.phrase_numbers):
        novel = sorted(returned_numbers - candidate.phrase_numbers)
        raise UnsafeAchievementOutputError(
            "Phrasing introduced unsupported numerals: " + ", ".join(novel)
        )
    missing = candidate.required_numbers - returned_numbers
    if missing:
        raise UnsafeAchievementOutputError(
            "Phrasing omitted required evidence numerals: " + ", ".join(sorted(missing))
        )
    if candidate.claim_scope.casefold() != "all-time" and _OVERCLAIM_PATTERN.search(
        phrase
    ):
        raise UnsafeAchievementOutputError(
            "Phrasing overstated partial warehouse coverage."
        )

    required_claim = {
        "career_high": "career high",
        "season_high": "season high",
        "threshold_crossing": "career",
        "all_time_top_n": "no.",
    }[candidate.suggestion.achievement_type]
    if required_claim not in lowered:
        raise UnsafeAchievementOutputError(
            f"Phrasing for {candidate.suggestion.suggestion_key} omitted its "
            "verified achievement type."
        )


def _allowed_phrases(candidate: VerifiedCandidate) -> set[str]:
    facts = candidate.phrase_facts
    name = candidate.player_name
    label = candidate.stat_label
    scope = candidate.claim_scope
    computed = facts["computed_value"]

    if candidate.suggestion.achievement_type == "career_high":
        return {
            f"{name} set a career high with {computed} {label} {scope}.",
            f"With {computed} {label}, {name} set a career high {scope}.",
        }
    if candidate.suggestion.achievement_type == "season_high":
        season = facts["season"]
        return {
            f"{name} set a {season} season high with {computed} {label} {scope}.",
            f"With {computed} {label}, {name} set a {season} season high {scope}.",
        }
    if candidate.suggestion.achievement_type == "threshold_crossing":
        threshold = facts["threshold"]
        total = facts["career_total_after"]
        return {
            f"{name} reached {threshold} career {label} {scope}, for a verified "
            f"total of {total}.",
            f"{name} crossed {threshold} career {label} {scope} and now has {total}.",
        }
    rank = facts["program_rank"]
    game_value = facts["game_value"]
    return {
        f"{name} recorded {game_value} {label}, ranking No. {rank} {scope}.",
        f"With {game_value} {label}, {name} ranks No. {rank} {scope}.",
    }


def _parse_output(text: str) -> AchievementAIOutput:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
        return AchievementAIOutput.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise UnsafeAchievementOutputError(
            "Model response did not match the required JSON schema."
        ) from exc


def _numbers(value: str) -> set[str]:
    return {_normalize_number(match) for match in _NUMBER_PATTERN.findall(value)}


def _normalize_number(value: str) -> str:
    value = value.replace(",", "")
    if "-" in value:
        return value
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def _decimal_text(value: Decimal) -> str:
    return _normalize_number(format(value, "f"))


def _fact_value(value: object) -> str | int:
    if isinstance(value, int):
        return value
    try:
        return _decimal_text(Decimal(str(value)))
    except ArithmeticError:
        return str(value)
