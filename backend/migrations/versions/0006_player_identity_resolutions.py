"""Persist reviewed player identity resolutions.

Revision ID: 0006_player_identity_resolutions
Revises: 0005_roster_source_provenance
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_player_identity_resolutions"
down_revision: str | None = "0005_roster_source_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_identity_resolutions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("match_key", sa.String(length=64), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("season", sa.String(length=16), nullable=False),
        sa.Column("source_player_id", sa.String(length=128), nullable=True),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("jersey_number", sa.String(length=16), nullable=True),
        sa.Column("created_from_issue_id", sa.Integer(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_from_issue_id"],
            ["data_quality_issues.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"],
            ["sport_programs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "sport_program_id",
        "player_id",
        "source_player_id",
        "created_from_issue_id",
    ):
        op.create_index(
            op.f(f"ix_player_identity_resolutions_{column}"),
            "player_identity_resolutions",
            [column],
        )
    op.create_index(
        op.f("ix_player_identity_resolutions_match_key"),
        "player_identity_resolutions",
        ["match_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_player_identity_resolutions_match_key"),
        table_name="player_identity_resolutions",
    )
    for column in (
        "created_from_issue_id",
        "source_player_id",
        "player_id",
        "sport_program_id",
    ):
        op.drop_index(
            op.f(f"ix_player_identity_resolutions_{column}"),
            table_name="player_identity_resolutions",
        )
    op.drop_table("player_identity_resolutions")
