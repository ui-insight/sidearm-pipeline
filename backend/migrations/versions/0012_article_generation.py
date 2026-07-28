"""Add durable Article generation jobs, Style Guides, and Article Versions.

Revision ID: 0012_article_generation
Revises: 0011_article_briefs
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_article_generation"
down_revision: str | None = "0011_article_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "style_guide_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guide_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_value", sa.String(length=128), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("rules", json_type, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_style_guide_version"),
        sa.CheckConstraint(
            "scope_type IN ('shared_athletics', 'sport', 'article_type', 'channel')",
            name="ck_style_guide_scope_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "guide_key",
            "version",
            name="uq_style_guide_key_version",
        ),
    )
    for column in ("active", "content_hash", "guide_key", "scope_type", "scope_value"):
        op.create_index(
            op.f(f"ix_style_guide_versions_{column}"),
            "style_guide_versions",
            [column],
        )

    style_table = sa.table(
        "style_guide_versions",
        sa.column("guide_key", sa.String),
        sa.column("version", sa.Integer),
        sa.column("name", sa.String),
        sa.column("scope_type", sa.String),
        sa.column("scope_value", sa.String),
        sa.column("instructions", sa.Text),
        sa.column("rules", json_type),
        sa.column("content_hash", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("created_by", sa.String),
    )
    op.bulk_insert(
        style_table,
        [
            {
                "guide_key": "athletics-default",
                "version": 1,
                "name": "Vandals Athletics seed guide",
                "scope_type": "shared_athletics",
                "scope_value": None,
                "instructions": (
                    "Use AP style, third person, and measured language. Lead with "
                    "the approved achievement and preserve every Coverage Window "
                    "qualifier exactly. Do not invent quotes or context."
                ),
                "rules": [
                    {
                        "key": "headline-length",
                        "category": "length",
                        "severity": "error",
                        "enforcement": "headline_max_chars",
                        "value": 90,
                    },
                    {
                        "key": "unsupported-fact-classes",
                        "category": "facts",
                        "severity": "error",
                        "enforcement": "forbidden_fact_classes",
                        "value": ["quotes", "injuries", "attendance", "weather"],
                    },
                    {
                        "key": "measured-language",
                        "category": "tone",
                        "severity": "error",
                        "enforcement": "forbidden_terms",
                        "value": ["all cylinders", "statement win", "came to play"],
                    },
                    {
                        "key": "no-exclamation",
                        "category": "tone",
                        "severity": "warning",
                        "enforcement": "forbidden_terms",
                        "value": ["!"],
                    },
                ],
                "content_hash": (
                    "235970f2ad3e28ea01af9ce0e6206d1c1b3b71df011acf69a10bc32e294a9ab2"
                ),
                "active": True,
                "created_by": "system-seed",
            }
        ],
    )

    op.create_table(
        "article_generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("evidence_bundle_id", sa.Integer(), nullable=False),
        sa.Column("style_guide_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("writer_input", json_type, nullable=False),
        sa.Column("style_snapshot", json_type, nullable=False),
        sa.Column("style_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("validation_results", json_type, nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_article_generation_attempts"),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_article_generation_job_state",
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evidence_bundle_id"], ["evidence_bundles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["style_guide_version_id"],
            ["style_guide_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id",
            "requested_by",
            "idempotency_key",
            name="uq_article_generation_request",
        ),
    )
    for column in (
        "article_id",
        "evidence_bundle_id",
        "requested_by",
        "state",
        "style_hash",
        "style_guide_version_id",
    ):
        op.create_index(
            op.f(f"ix_article_generation_jobs_{column}"),
            "article_generation_jobs",
            [column],
        )

    op.create_table(
        "article_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
        sa.Column("evidence_bundle_id", sa.Integer(), nullable=False),
        sa.Column("style_guide_version_id", sa.Integer(), nullable=False),
        sa.Column("generation_job_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("headline_evidence_ids", json_type, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("blocks", json_type, nullable=False),
        sa.Column("author", sa.String(length=128), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("style_snapshot", json_type, nullable=False),
        sa.Column("style_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("validation_results", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "origin IN ('ai', 'human')",
            name="ck_article_version_origin",
        ),
        sa.CheckConstraint("version > 0", name="ck_article_version_number"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["evidence_bundle_id"], ["evidence_bundles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"],
            ["article_generation_jobs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["article_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["style_guide_version_id"],
            ["style_guide_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "version", name="uq_article_version"),
        sa.UniqueConstraint(
            "generation_job_id", name="uq_article_version_generation_job"
        ),
    )
    for column in (
        "article_id",
        "evidence_bundle_id",
        "evidence_hash",
        "generation_job_id",
        "parent_version_id",
        "style_guide_version_id",
        "style_hash",
    ):
        op.create_index(
            op.f(f"ix_article_versions_{column}"),
            "article_versions",
            [column],
        )


def downgrade() -> None:
    op.drop_table("article_versions")
    op.drop_table("article_generation_jobs")
    op.drop_table("style_guide_versions")
