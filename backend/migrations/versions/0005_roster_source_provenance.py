"""Generalize source provenance for roster ingestion.

Revision ID: 0005_roster_source_provenance
Revises: 0004_normalized_warehouse_core
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_roster_source_provenance"
down_revision: str | None = "0004_normalized_warehouse_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_snapshots",
        sa.Column(
            "source_system",
            sa.String(length=64),
            server_default=sa.text("'sidearm'"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_snapshots",
        sa.Column(
            "source_type",
            sa.String(length=64),
            server_default=sa.text("'boxscore_html'"),
            nullable=False,
        ),
    )
    op.add_column(
        "source_snapshots",
        sa.Column("source_url", sa.String(length=1024), nullable=True),
    )

    snapshots = sa.table(
        "source_snapshots",
        sa.column("game_id", sa.Integer()),
        sa.column("event_source_id", sa.Integer()),
        sa.column("source_url", sa.String()),
    )
    event_sources = sa.table(
        "event_sources",
        sa.column("id", sa.Integer()),
        sa.column("source_url", sa.String()),
    )
    games = sa.table(
        "games",
        sa.column("id", sa.Integer()),
        sa.column("source_url", sa.String()),
    )
    event_source_url = (
        sa.select(event_sources.c.source_url)
        .where(event_sources.c.id == snapshots.c.event_source_id)
        .scalar_subquery()
    )
    game_source_url = (
        sa.select(games.c.source_url)
        .where(games.c.id == snapshots.c.game_id)
        .scalar_subquery()
    )
    op.get_bind().execute(
        sa.update(snapshots).values(
            source_url=sa.func.coalesce(event_source_url, game_source_url)
        )
    )

    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.alter_column("game_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column(
            "source_url", existing_type=sa.String(length=1024), nullable=False
        )

    op.add_column(
        "data_quality_issues",
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_data_quality_issues_deduplication_key"),
        "data_quality_issues",
        ["deduplication_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_data_quality_issues_deduplication_key"),
        table_name="data_quality_issues",
    )
    with op.batch_alter_table("data_quality_issues") as batch_op:
        batch_op.drop_column("deduplication_key")

    snapshots = sa.table(
        "source_snapshots",
        sa.column("id", sa.Integer()),
        sa.column("game_id", sa.Integer()),
    )
    player_seasons = sa.table(
        "player_seasons",
        sa.column("source_snapshot_id", sa.Integer()),
    )
    quality_issues = sa.table(
        "data_quality_issues",
        sa.column("source_snapshot_id", sa.Integer()),
    )
    non_game_snapshot_ids = sa.select(snapshots.c.id).where(
        snapshots.c.game_id.is_(None)
    )
    bind = op.get_bind()
    bind.execute(
        sa.update(player_seasons)
        .where(player_seasons.c.source_snapshot_id.in_(non_game_snapshot_ids))
        .values(source_snapshot_id=None)
    )
    bind.execute(
        sa.update(quality_issues)
        .where(quality_issues.c.source_snapshot_id.in_(non_game_snapshot_ids))
        .values(source_snapshot_id=None)
    )
    bind.execute(sa.delete(snapshots).where(snapshots.c.game_id.is_(None)))

    with op.batch_alter_table("source_snapshots") as batch_op:
        batch_op.alter_column("game_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("source_url")
        batch_op.drop_column("source_type")
        batch_op.drop_column("source_system")
