"""Add deterministic achievement detection records.

Revision ID: 0008_deterministic_achievements
Revises: 0007_shared_workspace_views
Create Date: 2026-07-25
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_deterministic_achievements"
down_revision: str | None = "0007_shared_workspace_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

SCOPE_WEIGHTS = {
    "season_high": "2.0",
    "career_high": "3.0",
    "threshold_crossing": "4.0",
    "all_time_top_n": "5.0",
}
METRIC_RULES = {
    "points": ("1.0", [1000, 1500, 2000]),
    "total_rebounds": ("0.9", [500, 750, 1000]),
    "assists": ("0.9", [250, 500]),
    "steals": ("0.8", [100, 200]),
    "blocks": ("0.8", [100, 200]),
    "three_point_field_goals_made": ("0.8", [100, 200]),
    "field_goals_made": ("0.7", [250, 500]),
    "free_throws_made": ("0.6", [250, 500]),
    "offensive_rebounds": ("0.7", [250, 500]),
    "defensive_rebounds": ("0.7", [250, 500]),
}


def upgrade() -> None:
    op.create_table(
        "notability_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("scope_weights", json_type, nullable=False),
        sa.Column("top_n", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("top_n > 0", name="ck_notability_policy_top_n"),
        sa.CheckConstraint("version > 0", name="ck_notability_policy_version"),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sport_program_id",
            "version",
            name="uq_notability_policy_program_version",
        ),
    )
    op.create_index(
        op.f("ix_notability_policies_active"),
        "notability_policies",
        ["active"],
    )
    op.create_index(
        op.f("ix_notability_policies_sport_program_id"),
        "notability_policies",
        ["sport_program_id"],
    )

    op.create_table(
        "notability_policy_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notability_policy_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("importance_weight", sa.Numeric(8, 3), nullable=False),
        sa.Column("thresholds", json_type, nullable=False),
        sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "importance_weight >= 0",
            name="ck_notability_policy_metric_weight",
        ),
        sa.ForeignKeyConstraint(
            ["notability_policy_id"],
            ["notability_policies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"],
            ["stat_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notability_policy_id",
            "stat_definition_id",
            name="uq_notability_policy_metric",
        ),
    )
    op.create_index(
        op.f("ix_notability_policy_metrics_notability_policy_id"),
        "notability_policy_metrics",
        ["notability_policy_id"],
    )
    op.create_index(
        op.f("ix_notability_policy_metrics_stat_definition_id"),
        "notability_policy_metrics",
        ["stat_definition_id"],
    )

    op.create_table(
        "achievement_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("notability_policy_id", sa.Integer(), nullable=False),
        sa.Column("coverage_window_id", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("suggestion_key", sa.String(length=255), nullable=False),
        sa.Column("achievement_type", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("computed_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("comparison_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("notability_score", sa.Numeric(12, 3), nullable=False),
        sa.Column("context", json_type, nullable=False),
        sa.Column("coverage_context", json_type, nullable=False),
        sa.Column("phrasing", sa.String(length=1024), nullable=True),
        sa.Column(
            "state",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "achievement_type IN ('career_high', 'season_high', "
            "'threshold_crossing', 'all_time_top_n')",
            name="ck_achievement_suggestion_type",
        ),
        sa.CheckConstraint(
            "notability_score >= 0",
            name="ck_achievement_suggestion_score",
        ),
        sa.CheckConstraint(
            "scope IN ('career', 'season', 'program')",
            name="ck_achievement_suggestion_scope",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'rejected')",
            name="ck_achievement_suggestion_state",
        ),
        sa.ForeignKeyConstraint(
            ["coverage_window_id"], ["coverage_windows.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["notability_policy_id"],
            ["notability_policies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"],
            ["stat_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "suggestion_key",
            name="uq_achievement_suggestion_game_key",
        ),
    )
    for column in (
        "achievement_type",
        "coverage_window_id",
        "game_id",
        "notability_policy_id",
        "player_id",
        "scope",
        "source_snapshot_id",
        "stat_definition_id",
        "state",
    ):
        op.create_index(
            op.f(f"ix_achievement_suggestions_{column}"),
            "achievement_suggestions",
            [column],
        )

    _seed_wbb_notability_policy()


def _seed_wbb_notability_policy() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    programs = sa.Table("sport_programs", metadata, autoload_with=connection)
    definitions = sa.Table("stat_definitions", metadata, autoload_with=connection)
    policies = sa.Table("notability_policies", metadata, autoload_with=connection)
    metric_rules = sa.Table(
        "notability_policy_metrics", metadata, autoload_with=connection
    )
    program_id = connection.scalar(
        sa.select(programs.c.id).where(programs.c.slug == "womens-basketball")
    )
    if program_id is None:
        return
    result = connection.execute(
        policies.insert().values(
            sport_program_id=program_id,
            version=1,
            name="WBB seed notability rubric",
            scope_weights=SCOPE_WEIGHTS,
            top_n=10,
            active=True,
        )
    )
    policy_id = result.inserted_primary_key[0]
    definition_rows = connection.execute(
        sa.select(definitions.c.id, definitions.c.stat_key).where(
            definitions.c.sport_program_id == program_id,
            definitions.c.entity_scope == "player",
        )
    ).all()
    for definition_id, stat_key in definition_rows:
        rule = METRIC_RULES.get(stat_key)
        if rule is None:
            continue
        weight, thresholds = rule
        connection.execute(
            metric_rules.insert().values(
                notability_policy_id=policy_id,
                stat_definition_id=definition_id,
                importance_weight=Decimal(weight),
                thresholds=thresholds,
                suppressed=False,
            )
        )


def downgrade() -> None:
    op.drop_table("achievement_suggestions")
    op.drop_table("notability_policy_metrics")
    op.drop_table("notability_policies")
