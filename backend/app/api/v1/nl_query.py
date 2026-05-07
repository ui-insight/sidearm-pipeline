"""Natural language query endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.nl_query import run_nl_query
from app.db.engine import get_db
from app.schemas.agent import NLQueryRequest, NLQueryResult

router = APIRouter()


@router.post(
    "",
    response_model=NLQueryResult,
    status_code=status.HTTP_200_OK,
    summary="Answer a natural language question about the games database",
)
async def nl_query(
    payload: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> NLQueryResult:
    """Translate a natural language question into SQL and execute it (read-only).

    Returns the generated SQL, raw result rows, and a plain English answer.
    An AgentRun provenance record is created for every request.

    This agent is Tier-2 read-only per ADR-003 — it never writes to the database.
    """
    try:
        agent_run = await run_nl_query(payload.question, db)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    output = agent_run.output_payload or {}
    return NLQueryResult(
        question=output.get("question", payload.question),
        sql=output.get("sql"),
        rows=output.get("rows", []),
        answer=output.get("answer", ""),
        agent_run_id=agent_run.id,
    )
