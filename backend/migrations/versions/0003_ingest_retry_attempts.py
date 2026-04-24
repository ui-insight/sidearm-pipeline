"""Add ingest retry attempt metadata.

Revision ID: 0003_ingest_retry_attempts
Revises: 0002_ingest_run_history
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ingest_retry_attempts"
down_revision: str | None = "0002_ingest_run_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingest_runs",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "ingest_runs",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ingest_runs", "max_attempts")
    op.drop_column("ingest_runs", "attempt_count")
