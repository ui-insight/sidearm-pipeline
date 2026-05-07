"""Add agent runs provenance tables.

Revision ID: 0004_agent_runs_provenance
Revises: 0003_ingest_retry_attempts
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_agent_runs_provenance"
down_revision: str | None = "0003_ingest_retry_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("input_payload", json_type, nullable=False),
        sa.Column("output_payload", json_type, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("eval_score", sa.Float(), nullable=True),
        sa.Column("human_verdict", sa.String(length=32), nullable=True),
        sa.Column("human_verdict_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("run_metadata", json_type, nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_agent_name"), "agent_runs", ["agent_name"])
    op.create_index(op.f("ix_agent_runs_game_id"), "agent_runs", ["game_id"])
    op.create_index(op.f("ix_agent_runs_human_verdict"), "agent_runs", ["human_verdict"])
    op.create_index(op.f("ix_agent_runs_started_at"), "agent_runs", ["started_at"])
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"])

    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("input_snapshot", json_type, nullable=True),
        sa.Column("output_snapshot", json_type, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_run_steps_agent_run_id"),
        "agent_run_steps",
        ["agent_run_id"],
    )

    op.create_table(
        "agent_run_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=False),
        sa.Column("eval_type", sa.String(length=32), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("detail", json_type, nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_run_evaluations_agent_run_id"),
        "agent_run_evaluations",
        ["agent_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_run_evaluations_agent_run_id"),
        table_name="agent_run_evaluations",
    )
    op.drop_table("agent_run_evaluations")
    op.drop_index(
        op.f("ix_agent_run_steps_agent_run_id"), table_name="agent_run_steps"
    )
    op.drop_table("agent_run_steps")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_started_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_human_verdict"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_game_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_name"), table_name="agent_runs")
    op.drop_table("agent_runs")
