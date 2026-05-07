"""ORM models for agent provenance tracking."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class AgentRun(Base):
    """Durable provenance record for one agent invocation."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id", ondelete="SET NULL"), index=True, nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(32), default="manual")
    input_payload: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    output_payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    human_verdict_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    game: Mapped["Game | None"] = relationship("Game", back_populates="agent_runs")  # noqa: F821
    steps: Mapped[list["AgentRunStep"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        order_by="AgentRunStep.step_order",
    )
    evaluations: Mapped[list["AgentRunEvaluation"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )


class AgentRunStep(Base):
    """One discrete step within an agent run (serialize → call_model → parse → evaluate)."""

    __tablename__ = "agent_run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=0)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    output_snapshot: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentRunEvaluation(Base):
    """One metric result from the eval harness for an agent run."""

    __tablename__ = "agent_run_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    eval_type: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool | None] = mapped_column(nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent_run: Mapped[AgentRun] = relationship(back_populates="evaluations")
