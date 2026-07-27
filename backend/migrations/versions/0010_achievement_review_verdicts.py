"""Add SID review provenance to achievement suggestions.

Revision ID: 0010_achievement_review_verdicts
Revises: 0009_ai_achievement_ranking
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_achievement_review_verdicts"
down_revision: str | None = "0009_ai_achievement_ranking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "achievement_suggestions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "achievement_suggestions",
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("achievement_suggestions", "reviewed_by")
    op.drop_column("achievement_suggestions", "reviewed_at")
