"""Add Article evidence revalidation audit records.

Revision ID: 0014_article_evidence_revalidation
Revises: 0013_article_editorial_versions
Create Date: 2026-07-29
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0014_article_evidence_revalidation"
down_revision: str | None = "0013_article_editorial_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _upgrade_reviewed_fact_hashes() -> None:
    """Replace fetch-identity-sensitive verdict hashes with material fingerprints."""
    suggestions = sa.table(
        "achievement_suggestions",
        sa.column("id", sa.Integer()),
        sa.column("game_id", sa.Integer()),
        sa.column("player_id", sa.Integer()),
        sa.column("stat_definition_id", sa.Integer()),
        sa.column("notability_policy_id", sa.Integer()),
        sa.column("coverage_window_id", sa.Integer()),
        sa.column("source_snapshot_id", sa.Integer()),
        sa.column("suggestion_key", sa.String()),
        sa.column("achievement_type", sa.String()),
        sa.column("scope", sa.String()),
        sa.column("computed_value", sa.Numeric()),
        sa.column("comparison_value", sa.Numeric()),
        sa.column("rank", sa.Integer()),
        sa.column("phrasing", sa.String()),
        sa.column("ai_model", sa.String()),
        sa.column("ai_prompt_version", sa.String()),
        sa.column("ai_output_hash", sa.String()),
        sa.column("context", sa.JSON()),
        sa.column("coverage_context", sa.JSON()),
        sa.column("reviewed_fact_hash", sa.String()),
    )
    games = sa.table(
        "games",
        sa.column("id", sa.Integer()),
        sa.column("canonical_uid", sa.String()),
        sa.column("sport", sa.String()),
        sa.column("season", sa.String()),
        sa.column("game_date", sa.String()),
        sa.column("event_status", sa.String()),
        sa.column("home_team", sa.String()),
        sa.column("away_team", sa.String()),
        sa.column("home_score", sa.Integer()),
        sa.column("away_score", sa.Integer()),
        sa.column("title", sa.String()),
        sa.column("source_url", sa.String()),
    )
    snapshots = sa.table(
        "source_snapshots",
        sa.column("id", sa.Integer()),
        sa.column("source_system", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("source_url", sa.String()),
        sa.column("parser_version", sa.String()),
        sa.column("content_hash", sa.String()),
    )
    coverage_windows = sa.table(
        "coverage_windows",
        sa.column("id", sa.Integer()),
        sa.column("grain", sa.String()),
        sa.column("first_season", sa.String()),
        sa.column("last_season", sa.String()),
        sa.column("completeness", sa.String()),
        sa.column("known_limitations", sa.String()),
        sa.column("source_system", sa.String()),
    )
    rows = (
        op.get_bind()
        .execute(
            sa.select(
                suggestions,
                *[
                    column.label(f"game_{column.name}")
                    for column in games.c
                    if column.name != "id"
                ],
                *[
                    column.label(f"source_{column.name}")
                    for column in snapshots.c
                    if column.name != "id"
                ],
                *[
                    column.label(f"coverage_{column.name}")
                    for column in coverage_windows.c
                    if column.name != "id"
                ],
            )
            .join(games, games.c.id == suggestions.c.game_id)
            .outerjoin(
                snapshots,
                snapshots.c.id == suggestions.c.source_snapshot_id,
            )
            .outerjoin(
                coverage_windows,
                coverage_windows.c.id == suggestions.c.coverage_window_id,
            )
            .where(suggestions.c.reviewed_fact_hash.is_not(None))
        )
        .mappings()
    )
    for row in rows:
        source = (
            {
                "source_system": row["source_source_system"],
                "source_type": row["source_source_type"],
                "source_url": row["source_source_url"],
                "parser_version": row["source_parser_version"],
                "content_hash": row["source_content_hash"],
            }
            if row["source_source_system"] is not None
            else None
        )
        coverage = (
            {
                "grain": row["coverage_grain"],
                "first_season": row["coverage_first_season"],
                "last_season": row["coverage_last_season"],
                "completeness": row["coverage_completeness"],
                "known_limitations": row["coverage_known_limitations"],
                "source_system": row["coverage_source_system"],
            }
            if row["coverage_grain"] is not None
            else None
        )
        value = {
            "suggestion_key": row["suggestion_key"],
            "game_id": row["game_id"],
            "player_id": row["player_id"],
            "stat_definition_id": row["stat_definition_id"],
            "notability_policy_id": row["notability_policy_id"],
            "achievement_type": row["achievement_type"],
            "scope": row["scope"],
            "computed_value": str(row["computed_value"]),
            "comparison_value": (
                str(row["comparison_value"])
                if row["comparison_value"] is not None
                else None
            ),
            "rank": row["rank"],
            "phrasing": row["phrasing"],
            "ai_model": row["ai_model"],
            "ai_prompt_version": row["ai_prompt_version"],
            "ai_output_hash": row["ai_output_hash"],
            "context": row["context"],
            "coverage_context": row["coverage_context"],
            "game": {
                "id": row["game_id"],
                "canonical_uid": row["game_canonical_uid"],
                "sport": row["game_sport"],
                "season": row["game_season"],
                "game_date": row["game_game_date"],
                "event_status": row["game_event_status"],
                "home_team": row["game_home_team"],
                "away_team": row["game_away_team"],
                "home_score": row["game_home_score"],
                "away_score": row["game_away_score"],
                "title": row["game_title"],
                "source_url": row["game_source_url"],
            },
            "source": source,
            "coverage_window": coverage,
        }
        op.get_bind().execute(
            suggestions.update()
            .where(suggestions.c.id == row["id"])
            .values(reviewed_fact_hash=_canonical_hash(value))
        )


def upgrade() -> None:
    op.create_table(
        "article_evidence_revalidations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("previous_evidence_bundle_id", sa.Integer(), nullable=False),
        sa.Column("refreshed_evidence_bundle_id", sa.Integer(), nullable=True),
        sa.Column("change_hash", sa.String(length=64), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_evidence_bundle_id"],
            ["evidence_bundles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["refreshed_evidence_bundle_id"],
            ["evidence_bundles.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "article_id",
        "previous_evidence_bundle_id",
        "refreshed_evidence_bundle_id",
        "change_hash",
        "resolved_by",
    ):
        op.create_index(
            op.f(f"ix_article_evidence_revalidations_{column}"),
            "article_evidence_revalidations",
            [column],
        )
    _upgrade_reviewed_fact_hashes()


def downgrade() -> None:
    op.drop_table("article_evidence_revalidations")
