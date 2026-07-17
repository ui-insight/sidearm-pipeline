"""Add deployment-wide shared workspace views.

Revision ID: 0007_shared_workspace_views
Revises: 0006_player_identity_resolutions
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_shared_workspace_views"
down_revision: str | None = "0006_player_identity_resolutions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_views",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("view_kind", sa.String(length=16), nullable=False),
        sa.Column(
            "params",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "view_kind IN ('season', 'comparison')",
            name="ck_workspace_view_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_workspace_views_created_at"),
        "workspace_views",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_workspace_views_created_by"),
        "workspace_views",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workspace_views_created_by"), table_name="workspace_views")
    op.drop_index(op.f("ix_workspace_views_created_at"), table_name="workspace_views")
    op.drop_table("workspace_views")
