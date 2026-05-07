"""Agent run provenance and verdict endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.eval_runner import run_evaluation
from app.db.engine import get_db
from app.models.agent import AgentRun
from app.models.content import GeneratedContent
from app.schemas.agent import AgentRunRead, AgentRunSummary, VerdictRequest
from app.schemas.content import GeneratedContentRead

router = APIRouter()


@router.get(
    "",
    response_model=list[AgentRunSummary],
    summary="List recent agent runs",
)
async def list_agent_runs(
    agent_name: str | None = Query(default=None, description="Filter by agent name"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunSummary]:
    """Return recent agent runs, newest first. Filterable by agent name and status."""
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    if agent_name:
        stmt = stmt.where(AgentRun.agent_name == agent_name)
    if status_filter:
        stmt = stmt.where(AgentRun.status == status_filter)

    result = await db.scalars(stmt)
    return [AgentRunSummary.model_validate(row) for row in result.all()]


@router.get(
    "/{run_id}",
    response_model=AgentRunRead,
    summary="Get a single agent run with steps and evaluations",
)
async def get_agent_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    """Return one agent run with its step records and evaluation results."""
    agent_run = await _load_agent_run(db, run_id)
    if agent_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )
    return AgentRunRead.model_validate(agent_run)


@router.post(
    "/{run_id}/evaluate",
    response_model=AgentRunRead,
    summary="Run eval harness on an agent run",
)
async def evaluate_agent_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
) -> AgentRunRead:
    """Run the evaluation harness on a completed agent run.

    Executes deterministic checks and updates AgentRun.eval_score.
    Persists one AgentRunEvaluation row per metric.
    """
    agent_run = await _load_agent_run(db, run_id)
    if agent_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    if agent_run.status not in ("succeeded", "failed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot evaluate a run with status={agent_run.status!r}",
        )

    try:
        await run_evaluation(run_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Reload with relationships
    agent_run = await _load_agent_run(db, run_id)
    return AgentRunRead.model_validate(agent_run)


@router.post(
    "/{run_id}/verdict",
    summary="Submit a human verdict (approved or rejected)",
)
async def submit_verdict(
    run_id: int,
    payload: VerdictRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a human verdict on an agent run.

    - **approved**: Creates a ``GeneratedContent`` record from the run's output and
      returns ``GeneratedContentRead`` (HTTP 200).
    - **rejected**: Marks the run as rejected and returns ``AgentRunRead`` (HTTP 200).

    Only runs with status='succeeded' and human_verdict=None may receive a verdict.
    """
    agent_run = await _load_agent_run(db, run_id)
    if agent_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    if agent_run.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only verdict a succeeded run, got status={agent_run.status!r}",
        )

    if agent_run.human_verdict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run already has verdict={agent_run.human_verdict!r}",
        )

    now = datetime.now(timezone.utc)
    agent_run.human_verdict = payload.verdict
    agent_run.human_verdict_at = now

    if payload.verdict == "approved":
        output = agent_run.output_payload or {}
        record = GeneratedContent(
            game_id=agent_run.game_id,
            headline=output.get("headline"),
            recap=output.get("recap", ""),
            spotlight_player=output.get("spotlight_player"),
            spotlight_body=output.get("spotlight_body", ""),
            social_post=output.get("social_post", ""),
            model=agent_run.model,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return GeneratedContentRead.model_validate(record)

    # rejected
    await db.commit()
    agent_run = await _load_agent_run(db, run_id)
    return AgentRunRead.model_validate(agent_run)


async def _load_agent_run(db: AsyncSession, run_id: int) -> AgentRun | None:
    stmt = (
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.steps),
            selectinload(AgentRun.evaluations),
        )
    )
    return await db.scalar(stmt)
