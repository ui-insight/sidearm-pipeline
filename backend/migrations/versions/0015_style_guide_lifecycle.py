"""Add immutable Style Guide lineage and lifecycle audit fields.

Revision ID: 0015_style_guide_lifecycle
Revises: 0014_article_revalidation
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_style_guide_lifecycle"
down_revision: str | None = "0014_article_revalidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("style_guide_versions") as batch_op:
        batch_op.add_column(
            sa.Column("predecessor_version_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "lifecycle_state",
                sa.String(length=16),
                server_default="draft",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("activated_by", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("retired_by", sa.String(length=128), nullable=True)
        )

    style_guides = sa.table(
        "style_guide_versions",
        sa.column("active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("lifecycle_state", sa.String()),
        sa.column("effective_at", sa.DateTime(timezone=True)),
        sa.column("activated_at", sa.DateTime(timezone=True)),
        sa.column("activated_by", sa.String()),
    )
    connection = op.get_bind()
    connection.execute(
        sa.update(style_guides).values(
            lifecycle_state=sa.case(
                (style_guides.c.active.is_(True), "active"),
                else_="retired",
            ),
            effective_at=style_guides.c.created_at,
            activated_at=sa.case(
                (style_guides.c.active.is_(True), style_guides.c.created_at),
                else_=None,
            ),
            activated_by=sa.case(
                (style_guides.c.active.is_(True), "system-seed"),
                else_=None,
            ),
        )
    )

    with op.batch_alter_table("style_guide_versions") as batch_op:
        batch_op.alter_column(
            "active",
            existing_type=sa.Boolean(),
            server_default=sa.false(),
            existing_nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_style_guide_predecessor",
            "style_guide_versions",
            ["predecessor_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_style_guide_scope_value",
            "(scope_type = 'shared_athletics' AND scope_value IS NULL) OR "
            "(scope_type <> 'shared_athletics' AND scope_value IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_style_guide_lifecycle_state",
            "lifecycle_state IN ('draft', 'active', 'retired')",
        )

    op.create_index(
        op.f("ix_style_guide_versions_predecessor_version_id"),
        "style_guide_versions",
        ["predecessor_version_id"],
    )
    op.create_index(
        op.f("ix_style_guide_versions_lifecycle_state"),
        "style_guide_versions",
        ["lifecycle_state"],
    )
    op.create_index(
        op.f("ix_style_guide_versions_effective_at"),
        "style_guide_versions",
        ["effective_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_style_guide_versions_effective_at"),
        table_name="style_guide_versions",
    )
    op.drop_index(
        op.f("ix_style_guide_versions_lifecycle_state"),
        table_name="style_guide_versions",
    )
    op.drop_index(
        op.f("ix_style_guide_versions_predecessor_version_id"),
        table_name="style_guide_versions",
    )
    with op.batch_alter_table("style_guide_versions") as batch_op:
        batch_op.drop_constraint("ck_style_guide_lifecycle_state", type_="check")
        batch_op.drop_constraint("ck_style_guide_scope_value", type_="check")
        batch_op.drop_constraint("fk_style_guide_predecessor", type_="foreignkey")
        batch_op.alter_column(
            "active",
            existing_type=sa.Boolean(),
            server_default=sa.true(),
            existing_nullable=False,
        )
        batch_op.drop_column("retired_by")
        batch_op.drop_column("retired_at")
        batch_op.drop_column("activated_by")
        batch_op.drop_column("activated_at")
        batch_op.drop_column("effective_at")
        batch_op.drop_column("lifecycle_state")
        batch_op.drop_column("predecessor_version_id")
