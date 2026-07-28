"""Add human Article editing and readiness audit records.

Revision ID: 0013_article_editorial_versions
Revises: 0012_article_generation
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_article_editorial_versions"
down_revision: str | None = "0012_article_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("article_generation_jobs") as batch_op:
        batch_op.add_column(sa.Column("base_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("editor_instructions", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_article_generation_jobs_base_version_id_article_versions",
            "article_versions",
            ["base_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_article_generation_jobs_base_version_id"),
            ["base_version_id"],
        )

    with op.batch_alter_table("article_versions") as batch_op:
        batch_op.add_column(sa.Column("editor_instructions", sa.Text(), nullable=True))

    with op.batch_alter_table("articles") as batch_op:
        batch_op.add_column(sa.Column("ready_version_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_articles_ready_version_id_article_versions",
            "article_versions",
            ["ready_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            op.f("ix_articles_ready_version_id"),
            ["ready_version_id"],
        )

    op.create_table(
        "article_warning_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_version_id", sa.Integer(), nullable=False),
        sa.Column("finding_code", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("overridden_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["article_version_id"],
            ["article_versions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("article_version_id", "finding_code", "overridden_by"):
        op.create_index(
            op.f(f"ix_article_warning_overrides_{column}"),
            "article_warning_overrides",
            [column],
        )

    op.create_table(
        "article_readiness_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("article_version_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('ready', 'reopened')",
            name="ck_article_readiness_action",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["article_version_id"],
            ["article_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("action", "actor", "article_id", "article_version_id"):
        op.create_index(
            op.f(f"ix_article_readiness_decisions_{column}"),
            "article_readiness_decisions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("article_readiness_decisions")
    op.drop_table("article_warning_overrides")

    with op.batch_alter_table("articles") as batch_op:
        batch_op.drop_index(op.f("ix_articles_ready_version_id"))
        batch_op.drop_constraint(
            "fk_articles_ready_version_id_article_versions",
            type_="foreignkey",
        )
        batch_op.drop_column("ready_version_id")

    with op.batch_alter_table("article_versions") as batch_op:
        batch_op.drop_column("editor_instructions")

    with op.batch_alter_table("article_generation_jobs") as batch_op:
        batch_op.drop_index(op.f("ix_article_generation_jobs_base_version_id"))
        batch_op.drop_constraint(
            "fk_article_generation_jobs_base_version_id_article_versions",
            type_="foreignkey",
        )
        batch_op.drop_column("editor_instructions")
        batch_op.drop_column("base_version_id")
