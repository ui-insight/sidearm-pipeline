"""Add ingest run history.

Revision ID: 0002_ingest_run_history
Revises: 0001_canonical_event_foundation
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingest_run_history"
down_revision: str | None = "0001_canonical_event_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("sport", sa.String(length=64), nullable=True),
        sa.Column("season", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("error_type", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_metadata", json_type, nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingest_runs_game_id"), "ingest_runs", ["game_id"])
    op.create_index(op.f("ix_ingest_runs_season"), "ingest_runs", ["season"])
    op.create_index(
        op.f("ix_ingest_runs_source_event_id"),
        "ingest_runs",
        ["source_event_id"],
    )
    op.create_index(op.f("ix_ingest_runs_sport"), "ingest_runs", ["sport"])
    op.create_index(op.f("ix_ingest_runs_started_at"), "ingest_runs", ["started_at"])
    op.create_index(op.f("ix_ingest_runs_status"), "ingest_runs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ingest_runs_status"), table_name="ingest_runs")
    op.drop_index(op.f("ix_ingest_runs_started_at"), table_name="ingest_runs")
    op.drop_index(op.f("ix_ingest_runs_sport"), table_name="ingest_runs")
    op.drop_index(
        op.f("ix_ingest_runs_source_event_id"),
        table_name="ingest_runs",
    )
    op.drop_index(op.f("ix_ingest_runs_season"), table_name="ingest_runs")
    op.drop_index(op.f("ix_ingest_runs_game_id"), table_name="ingest_runs")
    op.drop_table("ingest_runs")
