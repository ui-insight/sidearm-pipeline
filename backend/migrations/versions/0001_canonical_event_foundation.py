"""Create canonical event foundation tables.

Revision ID: 0001_canonical_event_foundation
Revises:
Create Date: 2026-04-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_canonical_event_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("canonical_uid", sa.String(length=255), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("sport", sa.String(length=64), nullable=True),
        sa.Column("sport_name", sa.String(length=128), nullable=True),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("season", sa.String(length=16), nullable=True),
        sa.Column("game_date", sa.String(length=64), nullable=True),
        sa.Column("event_shape", sa.String(length=64), nullable=False),
        sa.Column("event_status", sa.String(length=32), nullable=False),
        sa.Column("publish_status", sa.String(length=32), nullable=False),
        sa.Column("home_team", sa.String(length=255), nullable=True),
        sa.Column("away_team", sa.String(length=255), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("location_name", sa.String(length=255), nullable=True),
        sa.Column("venue_name", sa.String(length=255), nullable=True),
        sa.Column("home_away_neutral", sa.String(length=16), nullable=True),
        sa.Column("conference_event", sa.Boolean(), nullable=False),
        sa.Column("exhibition", sa.Boolean(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_successful_ingest_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_uid", name="uq_games_canonical_uid"),
        sa.UniqueConstraint("source_url", name="uq_games_source_url"),
    )
    op.create_index(op.f("ix_games_canonical_uid"), "games", ["canonical_uid"])
    op.create_index(op.f("ix_games_source_event_id"), "games", ["source_event_id"])

    op.create_table(
        "event_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("primary_source", sa.Boolean(), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "source_type",
            "source_url",
            name="uq_event_source_url",
        ),
    )
    op.create_index(op.f("ix_event_sources_game_id"), "event_sources", ["game_id"])
    op.create_index(
        op.f("ix_event_sources_source_id"),
        "event_sources",
        ["source_id"],
    )

    op.create_table(
        "event_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
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
        op.f("ix_event_status_history_game_id"),
        "event_status_history",
        ["game_id"],
    )

    op.create_table(
        "player_stat_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("columns", json_type, nullable=False),
        sa.Column("rows", json_type, nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_player_stat_groups_game_id"),
        "player_stat_groups",
        ["game_id"],
    )

    op.create_table(
        "scoring_plays",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=True),
        sa.Column("clock", sa.String(length=16), nullable=True),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scoring_plays_game_id"), "scoring_plays", ["game_id"])

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("event_source_id", sa.Integer(), nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("raw_body", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["event_source_id"],
            ["event_sources.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_source_snapshots_content_hash"),
        "source_snapshots",
        ["content_hash"],
    )
    op.create_index(
        op.f("ix_source_snapshots_event_source_id"),
        "source_snapshots",
        ["event_source_id"],
    )
    op.create_index(
        op.f("ix_source_snapshots_game_id"),
        "source_snapshots",
        ["game_id"],
    )

    op.create_table(
        "team_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("stat_name", sa.String(length=128), nullable=False),
        sa.Column("home_value", sa.String(length=64), nullable=True),
        sa.Column("away_value", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_team_stats_game_id"), "team_stats", ["game_id"])

    op.create_table(
        "generated_content",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("recap", sa.Text(), nullable=False),
        sa.Column("spotlight_player", sa.String(length=255), nullable=True),
        sa.Column("spotlight_body", sa.Text(), nullable=False),
        sa.Column("social_post", sa.Text(), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generated_content_game_id"),
        "generated_content",
        ["game_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_generated_content_game_id"), table_name="generated_content")
    op.drop_table("generated_content")
    op.drop_index(op.f("ix_team_stats_game_id"), table_name="team_stats")
    op.drop_table("team_stats")
    op.drop_index(op.f("ix_source_snapshots_game_id"), table_name="source_snapshots")
    op.drop_index(
        op.f("ix_source_snapshots_event_source_id"),
        table_name="source_snapshots",
    )
    op.drop_index(
        op.f("ix_source_snapshots_content_hash"),
        table_name="source_snapshots",
    )
    op.drop_table("source_snapshots")
    op.drop_index(op.f("ix_scoring_plays_game_id"), table_name="scoring_plays")
    op.drop_table("scoring_plays")
    op.drop_index(
        op.f("ix_player_stat_groups_game_id"),
        table_name="player_stat_groups",
    )
    op.drop_table("player_stat_groups")
    op.drop_index(
        op.f("ix_event_status_history_game_id"),
        table_name="event_status_history",
    )
    op.drop_table("event_status_history")
    op.drop_index(op.f("ix_event_sources_source_id"), table_name="event_sources")
    op.drop_index(op.f("ix_event_sources_game_id"), table_name="event_sources")
    op.drop_table("event_sources")
    op.drop_index(op.f("ix_games_source_event_id"), table_name="games")
    op.drop_index(op.f("ix_games_canonical_uid"), table_name="games")
    op.drop_table("games")
