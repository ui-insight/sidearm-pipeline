"""Add evidence-bound Article Brief persistence.

Revision ID: 0011_article_briefs
Revises: 0010_achievement_review_verdicts
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_article_briefs"
down_revision: str | None = "0010_achievement_review_verdicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "achievement_suggestions",
        sa.Column("reviewed_fact_hash", sa.String(length=64), nullable=True),
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="brief",
            nullable=False,
        ),
        sa.Column("article_type", sa.String(length=32), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "article_type IN ('game_recap', 'player_spotlight', 'achievement_story')",
            name="ck_article_type",
        ),
        sa.CheckConstraint(
            "status IN ('brief', 'generating', 'in_edit', 'ready', "
            "'needs_revalidation', 'archived')",
            name="ck_article_status",
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_article_creator_idempotency_key",
        ),
    )
    for column in ("article_type", "created_by", "game_id", "status"):
        op.create_index(op.f(f"ix_articles_{column}"), "articles", [column])

    op.create_table(
        "article_achievement_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("achievement_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("suggestion_key", sa.String(length=255), nullable=False),
        sa.Column("reviewed_fact_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["achievement_suggestion_id"],
            ["achievement_suggestions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "suggestion_key",
            name="uq_article_achievement_suggestion",
        ),
    )
    op.create_index(
        op.f("ix_article_achievement_suggestions_achievement_suggestion_id"),
        "article_achievement_suggestions",
        ["achievement_suggestion_id"],
    )
    op.create_index(
        op.f("ix_article_achievement_suggestions_article_id"),
        "article_achievement_suggestions",
        ["article_id"],
    )

    op.create_table(
        "evidence_bundles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("content", json_type, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_evidence_bundle_version"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "version",
            name="uq_evidence_bundle_article_version",
        ),
    )
    op.create_index(
        op.f("ix_evidence_bundles_article_id"),
        "evidence_bundles",
        ["article_id"],
    )
    op.create_index(
        op.f("ix_evidence_bundles_content_hash"),
        "evidence_bundles",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_table("evidence_bundles")
    op.drop_table("article_achievement_suggestions")
    op.drop_table("articles")
    op.drop_column("achievement_suggestions", "reviewed_fact_hash")
