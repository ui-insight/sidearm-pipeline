"""Pydantic schemas for agent run provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentRunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_run_id: int
    step_name: str
    step_order: int
    input_snapshot: dict | None = None
    output_snapshot: dict | None = None
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error_message: str | None = None


class AgentRunEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_run_id: int
    eval_type: str
    metric_name: str
    passed: bool | None = None
    score: float | None = None
    detail: dict = Field(default_factory=dict)
    evaluated_at: datetime


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    model: str
    prompt_version: str
    game_id: int | None = None
    trigger: str
    input_payload: dict = Field(default_factory=dict)
    output_payload: dict | None = None
    status: str
    eval_score: float | None = None
    human_verdict: str | None = None
    human_verdict_at: datetime | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    run_metadata: dict = Field(default_factory=dict)
    steps: list[AgentRunStepRead] = []
    evaluations: list[AgentRunEvaluationRead] = []


class AgentRunSummary(BaseModel):
    """Lightweight listing view for agent runs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    model: str
    status: str
    eval_score: float | None = None
    human_verdict: str | None = None
    started_at: datetime
    duration_ms: int | None = None
    game_id: int | None = None


class VerdictRequest(BaseModel):
    """Request body for submitting a human verdict on an agent run."""

    verdict: Literal["approved", "rejected"]


class NLQueryRequest(BaseModel):
    """Request body for a natural language database query."""

    question: str = Field(..., min_length=1, max_length=500, description="Natural language question")


class NLQueryResult(BaseModel):
    """Result of a natural language query."""

    question: str
    sql: str | None = None
    rows: list[dict] = Field(default_factory=list)
    answer: str
    agent_run_id: int
