"""Recap-writer agent with provenance tracking.

Replaces the core of services/content_generator.py with full AgentRun
step recording, prompt versioning, and human-review gating.

The agent does NOT create GeneratedContent directly. Instead it returns
an AgentRun record. GeneratedContent is only created when a human approves
via POST /api/v1/agent-runs/{id}/verdict.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from anthropic import AsyncAnthropic, AuthenticationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import AgentRun, AgentRunStep
from app.models.game import Game

logger = logging.getLogger(__name__)

# Prompt file lives at project root agents/ directory.
_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "agents"
    / "recap-writer"
    / "prompt.md"
)

_FALLBACK_PROMPT = (
    "You are a veteran collegiate athletics communications writer "
    "on the staff of a university sports information department. You turn raw "
    "boxscore data into publication-ready coverage for the athletic department's "
    "website and social accounts.\n\n"
    "House style:\n"
    "- AP style, third person, past tense.\n"
    "- Lead with the outcome (score and who won), then the turning point, then "
    "supporting context.\n"
    "- Name players as they appear in the stat tables (\"Last, First\").\n"
    "- Cite concrete numbers from the provided stats — never invent statistics, "
    "quotes, attendance, weather, or injuries.\n"
    "- Keep hype measured. Avoid clichés like \"all cylinders\", \"statement win\", "
    "or \"came to play\".\n"
    "- Do NOT use emoji in the recap or spotlight. At most one tasteful emoji is "
    "allowed in the social post.\n\n"
    "You respond with a single JSON object and nothing else. No prose outside the "
    "JSON, no markdown code fences, no commentary."
)

_SCHEMA_DOC = """{
  "headline":         string  // punchy news headline under 90 characters
  "recap":            string  // 250-350 word, 2-3 paragraph game recap in AP style
  "spotlight_player": string  // standout player name as written in the stats
  "spotlight_body":   string  // 2-3 sentence feature with concrete stats
  "social_post":      string  // under 280 characters with score + stat nugget
}"""

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured. Set it in .env to enable "
            "AI content generation."
        )

    global _client
    if _client is None:
        kwargs: dict = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        _client = AsyncAnthropic(**kwargs)
    return _client


@lru_cache(maxsize=1)
def _load_prompt() -> tuple[str, str]:
    """Load the prompt file and return (system_prompt, prompt_version).

    Caches on first call. prompt_version is the first 16 hex chars of SHA-256.
    """
    if _PROMPT_PATH.exists():
        raw = _PROMPT_PATH.read_text(encoding="utf-8")
        # Strip YAML frontmatter (---...---) if present
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end != -1:
                raw = raw[end + 3 :].lstrip()
        system_prompt = raw.strip()
    else:
        system_prompt = _FALLBACK_PROMPT

    prompt_version = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
    return system_prompt, prompt_version


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


async def _record_step(
    db: AsyncSession,
    agent_run: AgentRun,
    step_name: str,
    step_order: int,
    input_snapshot: dict | None,
    output_snapshot: dict | None,
    status: str,
    started_at: datetime,
    duration_ms: int,
    error_message: str | None = None,
) -> AgentRunStep:
    """Persist one step record for an agent run."""
    finished_at = datetime.now(timezone.utc)
    step = AgentRunStep(
        agent_run_id=agent_run.id,
        step_name=step_name,
        step_order=step_order,
        input_snapshot=input_snapshot,
        output_snapshot=output_snapshot,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        error_message=error_message,
    )
    db.add(step)
    await db.flush()
    return step


async def run_recap_writer(
    game: Game,
    db: AsyncSession,
    trigger: str = "manual",
) -> AgentRun:
    """Run the recap-writer agent for a game, recording full provenance.

    Returns an AgentRun with status="succeeded" or "failed".
    The AgentRun is committed to the database.
    GeneratedContent is NOT created here — a human verdict is required.
    """
    system_prompt, prompt_version = _load_prompt()
    run_start = time.monotonic()
    started_at = datetime.now(timezone.utc)

    agent_run = AgentRun(
        agent_name="recap-writer",
        model=settings.CONTENT_MODEL,
        prompt_version=prompt_version,
        game_id=game.id,
        trigger=trigger,
        input_payload={},
        status="running",
        run_metadata={"game_canonical_uid": game.canonical_uid or ""},
    )
    db.add(agent_run)
    await db.flush()  # get agent_run.id

    # ── Step 1: serialize_input ──────────────────────────────────────────────
    step1_start = time.monotonic()
    step1_started_at = datetime.now(timezone.utc)
    try:
        game_payload = _serialize_game(game)
        agent_run.input_payload = game_payload
        await _record_step(
            db,
            agent_run,
            step_name="serialize_input",
            step_order=0,
            input_snapshot={"game_id": game.id},
            output_snapshot=game_payload,
            status="succeeded",
            started_at=step1_started_at,
            duration_ms=int((time.monotonic() - step1_start) * 1000),
        )
    except Exception as exc:
        await _fail_run(db, agent_run, started_at, run_start, str(exc))
        raise

    # ── Step 2: call_model ───────────────────────────────────────────────────
    step2_start = time.monotonic()
    step2_started_at = datetime.now(timezone.utc)
    raw_text: str | None = None
    try:
        client = _get_client()
        user_message = (
            "Generate coverage for the game below. The boxscore JSON is authoritative "
            "— every number you cite must come from it. Pick the spotlight player by "
            "looking across all player stat categories and choosing the single most "
            "dominant performance, regardless of team.\n\n"
            f"Your JSON object must have exactly these keys:\n{_SCHEMA_DOC}\n\n"
            f"BOXSCORE:\n{json.dumps(game_payload, indent=2)}"
        )
        response = await client.messages.create(
            model=settings.CONTENT_MODEL,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = next(
            (block.text for block in response.content if block.type == "text"),
            None,
        )
        usage = getattr(response, "usage", None)
        await _record_step(
            db,
            agent_run,
            step_name="call_model",
            step_order=1,
            input_snapshot={"model": settings.CONTENT_MODEL},
            output_snapshot={
                "raw_text_length": len(raw_text) if raw_text else 0,
                "usage": {
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                }
                if usage
                else None,
            },
            status="succeeded",
            started_at=step2_started_at,
            duration_ms=int((time.monotonic() - step2_start) * 1000),
        )
    except AuthenticationError as exc:
        err = (
            "Upstream rejected the API key. Check ANTHROPIC_API_KEY "
            "(and ANTHROPIC_BASE_URL if using a gateway like MindRouter)."
        )
        await _record_step(
            db,
            agent_run,
            "call_model",
            1,
            None,
            None,
            "failed",
            step2_started_at,
            int((time.monotonic() - step2_start) * 1000),
            err,
        )
        await _fail_run(db, agent_run, started_at, run_start, err)
        raise RuntimeError(err) from exc
    except Exception as exc:
        await _record_step(
            db,
            agent_run,
            "call_model",
            1,
            None,
            None,
            "failed",
            step2_started_at,
            int((time.monotonic() - step2_start) * 1000),
            str(exc),
        )
        await _fail_run(db, agent_run, started_at, run_start, str(exc))
        raise

    if not raw_text:
        err = "Model returned no text block."
        await _fail_run(db, agent_run, started_at, run_start, err)
        raise RuntimeError(err)

    # ── Step 3: parse_output ─────────────────────────────────────────────────
    step3_start = time.monotonic()
    step3_started_at = datetime.now(timezone.utc)
    try:
        parsed = _extract_json(raw_text)
        if parsed is None:
            raise ValueError("Model response was not parseable JSON.")
        from app.schemas.content import GeneratedCoverage

        coverage = GeneratedCoverage.model_validate(parsed)
        output_payload = coverage.model_dump()
        agent_run.output_payload = output_payload
        await _record_step(
            db,
            agent_run,
            step_name="parse_output",
            step_order=2,
            input_snapshot={"raw_text_length": len(raw_text)},
            output_snapshot=output_payload,
            status="succeeded",
            started_at=step3_started_at,
            duration_ms=int((time.monotonic() - step3_start) * 1000),
        )
    except Exception as exc:
        await _record_step(
            db,
            agent_run,
            "parse_output",
            2,
            None,
            None,
            "failed",
            step3_started_at,
            int((time.monotonic() - step3_start) * 1000),
            str(exc),
        )
        await _fail_run(db, agent_run, started_at, run_start, str(exc))
        raise RuntimeError(f"Failed to parse model output: {exc}") from exc

    # ── Finalize run ─────────────────────────────────────────────────────────
    total_ms = int((time.monotonic() - run_start) * 1000)
    agent_run.status = "succeeded"
    agent_run.finished_at = datetime.now(timezone.utc)
    agent_run.duration_ms = total_ms
    await db.commit()

    logger.info(
        "recap-writer succeeded agent_run_id=%s game_id=%s model=%s duration_ms=%s",
        agent_run.id,
        game.id,
        settings.CONTENT_MODEL,
        total_ms,
    )
    return agent_run


async def _fail_run(
    db: AsyncSession,
    agent_run: AgentRun,
    started_at: datetime,
    run_start: float,
    error_message: str,
) -> None:
    """Mark an AgentRun as failed and commit."""
    agent_run.status = "failed"
    agent_run.finished_at = datetime.now(timezone.utc)
    agent_run.duration_ms = int((time.monotonic() - run_start) * 1000)
    agent_run.run_metadata = {
        **agent_run.run_metadata,
        "error_message": error_message,
    }
    await db.commit()


def _extract_json(text: str) -> dict | None:
    """Pull a JSON object out of a model response."""
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
    """Attempt to close an unbalanced JSON object dropped mid-stream."""
    trimmed = candidate.rstrip()

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
