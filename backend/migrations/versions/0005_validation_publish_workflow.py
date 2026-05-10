"""Add validation and publish workflow tables/columns.

Revision ID: 0005_validation_publish_workflow
Revises: 0004_agent_runs_provenance
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_validation_publish_workflow"
down_revision: str | None = "0004_agent_runs_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "games",
        sa.Column("validation_detail", json_type, nullable=True),
    )

    op.create_table(
        "publish_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("detail", json_type, nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_publish_events_game_id"), "publish_events", ["game_id"]
    )
    op.create_index(
        op.f("ix_publish_events_changed_at"), "publish_events", ["changed_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_publish_events_changed_at"), table_name="publish_events")
    op.drop_index(op.f("ix_publish_events_game_id"), table_name="publish_events")
    op.drop_table("publish_events")
    op.drop_column("games", "validation_detail")
    op.drop_column("games", "last_validated_at")
