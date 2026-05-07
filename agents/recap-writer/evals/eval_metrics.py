"""Deterministic eval metrics for the recap-writer agent.

Each check function returns an EvalResult dataclass. The composite_score
function aggregates them into a single 0.0–1.0 float.

These metrics are designed to be run both locally via pytest (test_evals.py)
and via the backend eval_runner service (backend/app/agents/eval_runner.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """Result of a single evaluation check."""

    metric: str
    passed: bool | None
    score: float | None
    detail: dict[str, Any] = field(default_factory=dict)


def check_score_present(
    recap: str, home_score: int | None, away_score: int | None
) -> EvalResult:
    """Check that both final scores appear somewhere in the recap text."""
    if home_score is None or away_score is None:
        return EvalResult(
            metric="score_present",
            passed=None,
            score=None,
            detail={"reason": "scores not available in game data"},
        )

    home_str = str(home_score)
    away_str = str(away_score)
    home_present = home_str in recap
    away_present = away_str in recap
    passed = home_present and away_present

    return EvalResult(
        metric="score_present",
        passed=passed,
        score=1.0 if passed else 0.0,
        detail={
            "home_score": home_score,
            "away_score": away_score,
            "home_found": home_present,
            "away_found": away_present,
        },
    )


def check_teams_mentioned(
    recap: str, home_team: str | None, away_team: str | None
) -> EvalResult:
    """Check that both team names appear in the recap."""
    if not home_team or not away_team:
        return EvalResult(
            metric="teams_mentioned",
            passed=None,
            score=None,
            detail={"reason": "team names not available"},
        )

    # Use case-insensitive search; check for partial match (first word of team name)
    home_word = home_team.split()[0] if home_team else ""
    away_word = away_team.split()[0] if away_team else ""

    home_present = bool(re.search(re.escape(home_word), recap, re.IGNORECASE))
    away_present = bool(re.search(re.escape(away_word), recap, re.IGNORECASE))
    passed = home_present and away_present

    return EvalResult(
        metric="teams_mentioned",
        passed=passed,
        score=1.0 if passed else (0.5 if home_present or away_present else 0.0),
        detail={
            "home_team": home_team,
            "away_team": away_team,
            "home_found": home_present,
            "away_found": away_present,
        },
    )


def check_word_count(recap: str, min_words: int = 250, max_words: int = 350) -> EvalResult:
    """Check that the recap falls within the target word count range."""
    words = recap.split()
    count = len(words)
    passed = min_words <= count <= max_words

    # Partial credit: within range edges
    if passed:
        score = 1.0
    elif count < min_words:
        score = max(0.0, count / min_words)
    else:
        score = max(0.0, 1.0 - (count - max_words) / max_words)

    return EvalResult(
        metric="word_count",
        passed=passed,
        score=score,
        detail={"actual": count, "min": min_words, "max": max_words},
    )


def check_headline_length(headline: str, max_chars: int = 90) -> EvalResult:
    """Check that the headline is within the character limit."""
    length = len(headline)
    passed = length <= max_chars
    return EvalResult(
        metric="headline_length",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - (length - max_chars) / max_chars),
        detail={"actual": length, "max": max_chars},
    )


def check_social_length(social: str, max_chars: int = 280) -> EvalResult:
    """Check that the social post is within the character limit."""
    length = len(social)
    passed = length <= max_chars
    return EvalResult(
        metric="social_length",
        passed=passed,
        score=1.0 if passed else max(0.0, 1.0 - (length - max_chars) / max_chars),
        detail={"actual": length, "max": max_chars},
    )


def check_stats_cited(recap: str, team_stats: list[dict]) -> EvalResult:
    """Check that at least one numeric value from team stats appears in the recap."""
    if not team_stats:
        return EvalResult(
            metric="stats_cited",
            passed=None,
            score=None,
            detail={"reason": "no team stats available"},
        )

    cited_count = 0
    cited_examples: list[str] = []

    for stat in team_stats:
        for value_key in ("home_value", "away_value"):
            val = stat.get(value_key)
            if val and str(val).strip() and str(val).strip() in recap:
                cited_count += 1
                cited_examples.append(f"{stat.get('stat_name')}: {val}")
                break

    passed = cited_count > 0
    return EvalResult(
        metric="stats_cited",
        passed=passed,
        score=min(1.0, cited_count / max(1, len(team_stats) * 0.1)),
        detail={"cited_count": cited_count, "examples": cited_examples[:3]},
    )


async def llm_judge(
    coverage: dict,
    game_data: dict,
    client,
) -> EvalResult:
    """LLM-as-judge scorer: rate factual accuracy and style on 0.0–1.0.

    Args:
        coverage: The generated coverage dict (headline, recap, etc.)
        game_data: The serialized game data used to generate the coverage
        client: An AsyncAnthropic client instance

    Returns:
        EvalResult with score 0.0–1.0 and reasoning in detail
    """
    import json

    judge_prompt = f"""You are evaluating AI-generated sports coverage for factual accuracy and style.

ORIGINAL GAME DATA:
{json.dumps(game_data, indent=2)}

GENERATED COVERAGE:
Headline: {coverage.get("headline", "")}

Recap:
{coverage.get("recap", "")}

Spotlight Player: {coverage.get("spotlight_player", "")}
Spotlight Body: {coverage.get("spotlight_body", "")}

Social Post: {coverage.get("social_post", "")}

Rate this coverage on a scale of 0.0 to 1.0 based on:
1. Factual accuracy (all stats cited actually appear in the game data)
2. No invented information (no made-up quotes, attendance, injuries)
3. Appropriate style (AP style, past tense, measured tone)

Respond with a JSON object: {{"score": float, "reason": string}}
"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        import re as _re

        text = next(
            (block.text for block in response.content if block.type == "text"), ""
        )
        # Try to parse JSON from response
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            match = _re.search(r'\{"score":\s*([0-9.]+)', text)
            if match:
                parsed = {"score": float(match.group(1)), "reason": ""}

        if parsed:
            score = float(parsed.get("score", 0.5))
            reason = parsed.get("reason", "")
        else:
            score = 0.5
            reason = "Could not parse judge response"

        return EvalResult(
            metric="llm_judge",
            passed=score >= 0.7,
            score=min(1.0, max(0.0, score)),
            detail={"reason": reason},
        )
    except Exception as exc:
        return EvalResult(
            metric="llm_judge",
            passed=None,
            score=None,
            detail={"error": str(exc)},
        )


def composite_score(results: list[EvalResult]) -> float:
    """Compute a weighted composite score from 0.0–1.0.

    Weights:
    - score_present: 0.25
    - teams_mentioned: 0.15
    - word_count: 0.15
    - headline_length: 0.10
    - social_length: 0.10
    - stats_cited: 0.15
    - llm_judge: 0.10
    """
    weights = {
        "score_present": 0.25,
        "teams_mentioned": 0.15,
        "word_count": 0.15,
        "headline_length": 0.10,
        "social_length": 0.10,
        "stats_cited": 0.15,
        "llm_judge": 0.10,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for result in results:
        w = weights.get(result.metric, 0.05)
        if result.score is not None:
            weighted_sum += result.score * w
            total_weight += w

    if total_weight == 0.0:
        return 0.0

    return weighted_sum / total_weight
