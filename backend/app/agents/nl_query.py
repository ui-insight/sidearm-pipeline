"""Natural language query agent.

Capability Tier 2: Read-only (see ADR-003).

Translates a natural language question into a SQL SELECT query,
executes it read-only against the games database, and summarizes
the results in plain English. Never writes to the database.
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
from typing import Any

from anthropic import AsyncAnthropic, AuthenticationError
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import AgentRun, AgentRunStep

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "agents" / "nl-query" / "prompt.md"
)

_FALLBACK_SYSTEM_PROMPT = (
    "You are a database assistant for the Vandals Stats Pipeline. "
    "Translate natural language questions into SQL SELECT queries. "
    "Only generate SELECT statements — never INSERT, UPDATE, DELETE, DROP, or any mutating SQL. "
    'Respond with a JSON object: {"sql": string|null, "answer": string}'
)

MAX_ROWS = 100

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    global _client
    if _client is None:
        kwargs: dict = {"api_key": settings.ANTHROPIC_API_KEY}
        if settings.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
        _client = AsyncAnthropic(**kwargs)
    return _client


@lru_cache(maxsize=1)
def _load_prompt() -> tuple[str, str]:
    """Load the system prompt from file or fall back to inline."""
    if _PROMPT_PATH.exists():
        raw = _PROMPT_PATH.read_text(encoding="utf-8")
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end != -1:
                raw = raw[end + 3 :].lstrip()
        system_prompt = raw.strip()
    else:
        system_prompt = _FALLBACK_SYSTEM_PROMPT

    prompt_version = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
    return system_prompt, prompt_version


def _is_select_only(sql: str) -> bool:
    """Return True only if the SQL statement begins with SELECT."""
    return bool(re.match(r"(?i)^\s*SELECT\b", sql.strip()))


async def _get_schema_description(db: AsyncSession) -> str:
    """Build a compact schema description from SQLAlchemy metadata."""

    def _inspect(conn):
        meta = MetaData()
        meta.reflect(bind=conn)
        lines = []
        for table_name, table in sorted(meta.tables.items()):
            cols = ", ".join(col.name for col in table.columns)
            lines.append(f"  {table_name}({cols})")
        return "\n".join(lines)

    async with db.bind.connect() as conn:
        schema_text = await conn.run_sync(_inspect)

    return schema_text


async def run_nl_query(question: str, db: AsyncSession) -> AgentRun:
    """Run the nl-query agent for a natural language question.

    Creates an AgentRun with full step provenance. Never writes to the DB
    (reads only). Returns the completed AgentRun.
    """
    system_prompt, prompt_version = _load_prompt()
    run_start = time.monotonic()
    started_at = datetime.now(timezone.utc)

    agent_run = AgentRun(
        agent_name="nl-query",
        model=settings.CONTENT_MODEL,
        prompt_version=prompt_version,
        game_id=None,
        trigger="api",
        input_payload={"question": question},
        status="running",
        run_metadata={},
    )
    db.add(agent_run)
    await db.flush()

    # ── Step 1: introspect schema ────────────────────────────────────────────
    step1_start = time.monotonic()
    step1_started_at = datetime.now(timezone.utc)
    schema_desc = ""
    try:
        schema_desc = await _get_schema_description(db)
        await _add_step(
            db,
            agent_run,
            "introspect_schema",
            0,
            None,
            {"schema_preview": schema_desc[:500]},
            "succeeded",
            step1_started_at,
            int((time.monotonic() - step1_start) * 1000),
        )
    except Exception as exc:
        await _add_step(
            db,
            agent_run,
            "introspect_schema",
            0,
            None,
            None,
            "failed",
            step1_started_at,
            int((time.monotonic() - step1_start) * 1000),
            str(exc),
        )
        await _fail_run(db, agent_run, run_start, str(exc))
        raise

    # ── Step 2: call_model ───────────────────────────────────────────────────
    step2_start = time.monotonic()
    step2_started_at = datetime.now(timezone.utc)
    generated_sql: str | None = None
    try:
        client = _get_client()
        user_message = (
            f"DATABASE SCHEMA:\n{schema_desc}\n\n"
            f"QUESTION: {question}\n\n"
            "Generate a SQL SELECT query to answer this question. "
            "Remember: only SELECT statements. "
            'Respond with JSON: {"sql": <query or null>, "answer": <placeholder>}'
        )
        response = await client.messages.create(
            model=settings.CONTENT_MODEL,
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = next(
            (block.text for block in response.content if block.type == "text"), ""
        )
        parsed = _extract_json(raw_text)
        generated_sql = parsed.get("sql") if parsed else None
        await _add_step(
            db,
            agent_run,
            "call_model",
            1,
            {"question": question},
            {"generated_sql": generated_sql, "raw_length": len(raw_text)},
            "succeeded",
            step2_started_at,
            int((time.monotonic() - step2_start) * 1000),
        )
    except AuthenticationError as exc:
        err = "Upstream rejected the API key."
        await _add_step(
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
        await _fail_run(db, agent_run, run_start, err)
        raise RuntimeError(err) from exc
    except Exception as exc:
        await _add_step(
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
        await _fail_run(db, agent_run, run_start, str(exc))
        raise

    # ── Step 3: execute_sql ──────────────────────────────────────────────────
    step3_start = time.monotonic()
    step3_started_at = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    if generated_sql:
        if not _is_select_only(generated_sql):
            err = f"Safety guard: non-SELECT SQL rejected: {generated_sql[:100]}"
            logger.warning(err)
            await _add_step(
                db,
                agent_run,
                "execute_sql",
                2,
                {"sql": generated_sql},
                None,
                "failed",
                step3_started_at,
                int((time.monotonic() - step3_start) * 1000),
                err,
            )
            await _fail_run(db, agent_run, run_start, err)
            raise RuntimeError(err)
        try:
            result = await db.execute(text(generated_sql))
            col_names = list(result.keys())
            raw_rows = result.fetchmany(MAX_ROWS)
            rows = [dict(zip(col_names, row)) for row in raw_rows]
            await _add_step(
                db,
                agent_run,
                "execute_sql",
                2,
                {"sql": generated_sql},
                {"row_count": len(rows)},
                "succeeded",
                step3_started_at,
                int((time.monotonic() - step3_start) * 1000),
            )
        except Exception as exc:
            await _add_step(
                db,
                agent_run,
                "execute_sql",
                2,
                {"sql": generated_sql},
                None,
                "failed",
                step3_started_at,
                int((time.monotonic() - step3_start) * 1000),
                str(exc),
            )
            await _fail_run(db, agent_run, run_start, str(exc))
            raise RuntimeError(f"SQL execution failed: {exc}") from exc

    # ── Step 4: format_response ──────────────────────────────────────────────
    step4_start = time.monotonic()
    step4_started_at = datetime.now(timezone.utc)
    answer = ""
    try:
        client = _get_client()
        if generated_sql and rows:
            summarize_prompt = (
                f"QUESTION: {question}\n\n"
                f"SQL USED: {generated_sql}\n\n"
                f"RESULT ROWS (up to {MAX_ROWS}):\n"
                f"{json.dumps(rows[:10], default=str, indent=2)}\n\n"
                f"Total rows returned: {len(rows)}\n\n"
                "Write a concise, plain English answer to the question based on "
                "these results. Be specific with numbers."
            )
            sum_response = await client.messages.create(
                model=settings.CONTENT_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": summarize_prompt}],
            )
            answer = next(
                (block.text for block in sum_response.content if block.type == "text"),
                "Could not summarize results.",
            )
        elif generated_sql and not rows:
            answer = "The query returned no results."
        else:
            answer = "This question could not be answered with the available data."

        await _add_step(
            db,
            agent_run,
            "format_response",
            3,
            {"row_count": len(rows)},
            {"answer_length": len(answer)},
            "succeeded",
            step4_started_at,
            int((time.monotonic() - step4_start) * 1000),
        )
    except Exception as exc:
        await _add_step(
            db,
            agent_run,
            "format_response",
            3,
            None,
            None,
            "failed",
            step4_started_at,
            int((time.monotonic() - step4_start) * 1000),
            str(exc),
        )
        await _fail_run(db, agent_run, run_start, str(exc))
        raise

    # ── Finalize ─────────────────────────────────────────────────────────────
    total_ms = int((time.monotonic() - run_start) * 1000)
    agent_run.output_payload = {
        "question": question,
        "sql": generated_sql,
        "rows": rows,
        "answer": answer,
    }
    agent_run.status = "succeeded"
    agent_run.finished_at = datetime.now(timezone.utc)
    agent_run.duration_ms = total_ms
    await db.commit()

    logger.info(
        "nl-query succeeded agent_run_id=%s duration_ms=%s",
        agent_run.id,
        total_ms,
    )
    return agent_run


async def _add_step(
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
) -> None:
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


async def _fail_run(
    db: AsyncSession,
    agent_run: AgentRun,
    run_start: float,
    error_message: str,
) -> None:
    agent_run.status = "failed"
    agent_run.finished_at = datetime.now(timezone.utc)
    agent_run.duration_ms = int((time.monotonic() - run_start) * 1000)
    agent_run.run_metadata = {**agent_run.run_metadata, "error_message": error_message}
    await db.commit()


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from model text."""

    def _try(s: str) -> dict | None:
        try:
            v = json.loads(s)
            return v if isinstance(v, dict) else None
        except Exception:
            return None

    parsed = _try(text.strip())
    if parsed is not None:
        return parsed

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return _try(text[start : end + 1])

    return None
