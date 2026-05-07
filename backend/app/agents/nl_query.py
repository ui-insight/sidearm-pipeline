"""Natural language query agent.

Capability Tier 2: Read-only (see ADR-003).

Translates a natural language question into a SQL SELECT query,
executes it read-only against the games database, and summarizes
the results in plain English. Never writes to the database.

Uses the MCP database server (describe_schema, execute_read_query)
in a dynamic tool-use loop so the model drives its own data access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from anthropic import AsyncAnthropic, AuthenticationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents._mcp_client import mcp_session, mcp_tools_to_anthropic
from app.config import settings
from app.models.agent import AgentRun, AgentRunStep

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "agents"
    / "nl-query"
    / "prompt.md"
)

_FALLBACK_SYSTEM_PROMPT = (
    "You are a database assistant for the Vandals Stats Pipeline. "
    "You have two tools available: describe_schema (to learn the database schema) "
    "and execute_read_query (to run SELECT queries). "
    "Call describe_schema first to understand the schema, then generate and run "
    "a SELECT query to answer the user's question, then respond in plain English."
)

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


async def run_nl_query(question: str, db: AsyncSession) -> AgentRun:
    """Run the nl-query agent for a natural language question.

    Creates an AgentRun with full step provenance. Never writes to the DB
    (reads only). Returns the completed AgentRun.

    The agent drives its own data access via an MCP tool-use loop:
    1. The model calls describe_schema to inspect available tables.
    2. The model calls execute_read_query with a SELECT statement.
    3. The model emits end_turn with a plain-English answer.

    Each tool call is recorded as an AgentRunStep for full provenance.
    """
    system_prompt, prompt_version = _load_prompt()
    run_start = time.monotonic()

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

    client = _get_client()
    answer = ""
    last_sql: str | None = None
    last_rows: list = []

    try:
        async with mcp_session("database") as session:
            tool_list = await session.list_tools()
            tools = mcp_tools_to_anthropic(tool_list.tools)
            messages: list[dict] = [{"role": "user", "content": question}]
            step_order = 0

            for iteration in range(settings.MAX_TOOL_ITERATIONS):
                try:
                    response = await client.messages.create(
                        model=settings.CONTENT_MODEL,
                        max_tokens=2000,
                        system=system_prompt,
                        tools=tools,
                        messages=messages,
                    )
                except AuthenticationError as exc:
                    err = "Upstream rejected the API key."
                    await _add_step(
                        db,
                        agent_run,
                        "call_model",
                        step_order,
                        None,
                        None,
                        "failed",
                        datetime.now(UTC),
                        0,
                        err,
                    )
                    await _fail_run(db, agent_run, run_start, err)
                    raise RuntimeError(err) from exc

                if response.stop_reason == "end_turn":
                    answer = next(
                        (b.text for b in response.content if b.type == "text"), ""
                    )
                    break

                # Process tool_use blocks
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    step_start = time.monotonic()
                    step_started_at = datetime.now(UTC)
                    try:
                        result = await session.call_tool(block.name, block.input)
                        content = (
                            result.content[0].text if result.content else ""
                        )
                        if block.name == "execute_read_query":
                            last_sql = block.input.get("sql")
                            try:
                                last_rows = json.loads(content) if content else []
                            except json.JSONDecodeError:
                                last_rows = []
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": content,
                            }
                        )
                        await _add_step(
                            db,
                            agent_run,
                            f"tool:{block.name}",
                            step_order,
                            {"input": block.input},
                            {"output_length": len(content)},
                            "succeeded",
                            step_started_at,
                            int((time.monotonic() - step_start) * 1000),
                        )
                    except Exception as exc:
                        err = str(exc)
                        await _add_step(
                            db,
                            agent_run,
                            f"tool:{block.name}",
                            step_order,
                            {"input": block.input},
                            None,
                            "failed",
                            step_started_at,
                            int((time.monotonic() - step_start) * 1000),
                            err,
                        )
                        await _fail_run(db, agent_run, run_start, err)
                        raise RuntimeError(
                            f"Tool {block.name} failed: {exc}"
                        ) from exc
                    step_order += 1

                messages.append(
                    {"role": "assistant", "content": response.content}
                )
                messages.append({"role": "user", "content": tool_results})
            else:
                err = (
                    f"Tool-use loop exceeded MAX_TOOL_ITERATIONS="
                    f"{settings.MAX_TOOL_ITERATIONS}"
                )
                await _fail_run(db, agent_run, run_start, err)
                raise RuntimeError(err)

    except RuntimeError:
        raise
    except Exception as exc:
        await _fail_run(db, agent_run, run_start, str(exc))
        raise

    # ── Finalize ─────────────────────────────────────────────────────────────
    total_ms = int((time.monotonic() - run_start) * 1000)
    agent_run.output_payload = {
        "question": question,
        "sql": last_sql,
        "rows": last_rows,
        "answer": answer,
    }
    agent_run.status = "succeeded"
    agent_run.finished_at = datetime.now(UTC)
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
    finished_at = datetime.now(UTC)
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
    agent_run.finished_at = datetime.now(UTC)
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
