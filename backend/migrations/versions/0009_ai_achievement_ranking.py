"""Add validated AI ranking provenance to achievement suggestions.

Revision ID: 0009_ai_achievement_ranking
Revises: 0008_deterministic_achievements
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_ai_achievement_ranking"
down_revision: str | None = "0008_deterministic_achievements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "achievement_suggestions",
        sa.Column("ai_rank", sa.Integer(), nullable=True),
    )
    op.add_column(
        "achievement_suggestions",
        sa.Column("ai_model", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "achievement_suggestions",
        sa.Column("ai_prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "achievement_suggestions",
        sa.Column("ai_output_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "achievement_suggestions",
        sa.Column("ai_ranked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_achievement_suggestions_ai_rank"),
        "achievement_suggestions",
        ["ai_rank"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_achievement_suggestions_ai_rank"),
        table_name="achievement_suggestions",
    )
    op.drop_column("achievement_suggestions", "ai_ranked_at")
    op.drop_column("achievement_suggestions", "ai_output_hash")
    op.drop_column("achievement_suggestions", "ai_prompt_version")
    op.drop_column("achievement_suggestions", "ai_model")
    op.drop_column("achievement_suggestions", "ai_rank")
