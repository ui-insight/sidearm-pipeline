"""Add the normalized athletics warehouse core.

Revision ID: 0004_normalized_warehouse_core
Revises: 0003_ingest_retry_attempts
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_normalized_warehouse_core"
down_revision: str | None = "0003_ingest_retry_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "sport_programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("sport", sa.String(length=64), nullable=False),
        sa.Column("gender", sa.String(length=32), nullable=True),
        sa.Column("season_format", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sport_programs_slug"), "sport_programs", ["slug"], unique=True
    )
    op.create_index(op.f("ix_sport_programs_sport"), "sport_programs", ["sport"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=128), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("is_idaho", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_teams_slug"), "teams", ["slug"], unique=True)
    op.create_index(op.f("ix_teams_canonical_name"), "teams", ["canonical_name"])

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_players_display_name"), "players", ["display_name"])

    op.create_table(
        "opponent_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("observed_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "sport_program_id",
            "normalized_alias",
            name="uq_opponent_alias_namespace",
        ),
    )
    op.create_index(
        op.f("ix_opponent_aliases_sport_program_id"),
        "opponent_aliases",
        ["sport_program_id"],
    )
    op.create_index(
        op.f("ix_opponent_aliases_team_id"), "opponent_aliases", ["team_id"]
    )

    op.create_table(
        "player_external_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("source_player_id", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
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
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "institution",
            "source_player_id",
            name="uq_player_external_identity_namespace",
        ),
    )
    op.create_index(
        op.f("ix_player_external_identities_player_id"),
        "player_external_identities",
        ["player_id"],
    )
    op.create_index(
        op.f("ix_player_external_identities_source_player_id"),
        "player_external_identities",
        ["source_player_id"],
    )

    op.create_table(
        "player_seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.String(length=16), nullable=False),
        sa.Column("jersey_number", sa.String(length=16), nullable=True),
        sa.Column("class_year", sa.String(length=64), nullable=True),
        sa.Column("position", sa.String(length=64), nullable=True),
        sa.Column("bio_url", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "sport_program_id",
            "season",
            name="uq_player_season_membership",
        ),
    )
    for column in (
        "player_id",
        "sport_program_id",
        "team_id",
        "source_snapshot_id",
        "season",
    ):
        op.create_index(op.f(f"ix_player_seasons_{column}"), "player_seasons", [column])

    op.create_table(
        "stat_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("stat_key", sa.String(length=128), nullable=False),
        sa.Column("display_label", sa.String(length=128), nullable=False),
        sa.Column("entity_scope", sa.String(length=32), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("aggregation_method", sa.String(length=32), nullable=False),
        sa.Column("comparison_direction", sa.String(length=16), nullable=False),
        sa.Column("qualifying_minimum", sa.Numeric(18, 6), nullable=True),
        sa.Column("display_format", sa.String(length=64), nullable=True),
        sa.Column("source_field_aliases", json_type, nullable=False),
        sa.Column("ratio_numerator_stat_key", sa.String(length=128), nullable=True),
        sa.Column("ratio_denominator_stat_key", sa.String(length=128), nullable=True),
        sa.Column("record_book_eligible", sa.Boolean(), nullable=False),
        sa.Column("notability_eligible", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "aggregation_method IN ('sum', 'maximum', 'minimum', 'average', "
            "'ratio_from_components', 'latest', 'non_aggregable')",
            name="ck_stat_definition_aggregation_method",
        ),
        sa.CheckConstraint(
            "comparison_direction IN ('higher', 'lower', 'neutral')",
            name="ck_stat_definition_comparison_direction",
        ),
        sa.CheckConstraint(
            "entity_scope IN ('player', 'team', 'event', 'participant')",
            name="ck_stat_definition_entity_scope",
        ),
        sa.CheckConstraint(
            "aggregation_method != 'ratio_from_components' OR "
            "(ratio_numerator_stat_key IS NOT NULL AND "
            "ratio_denominator_stat_key IS NOT NULL)",
            name="ck_stat_definition_ratio_components",
        ),
        sa.CheckConstraint(
            "value_type IN ('integer', 'decimal', 'duration')",
            name="ck_stat_definition_value_type",
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sport_program_id",
            "entity_scope",
            "stat_key",
            name="uq_stat_definition_program_scope_key",
        ),
    )
    op.create_index(
        op.f("ix_stat_definitions_sport_program_id"),
        "stat_definitions",
        ["sport_program_id"],
    )
    op.create_index(
        op.f("ix_stat_definitions_stat_key"), "stat_definitions", ["stat_key"]
    )

    _create_game_fact_tables()
    _create_season_fact_tables()
    _create_trust_tables()
    _seed_wbb_reference_data()


def _create_game_fact_tables() -> None:
    op.create_table(
        "player_game_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=True),
        sa.Column("source_value", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "player_id",
            "stat_definition_id",
            name="uq_player_game_stat_fact",
        ),
    )
    _create_fact_indexes(
        "player_game_stats",
        ("game_id", "player_id", "team_id", "stat_definition_id", "source_snapshot_id"),
    )

    op.create_table(
        "team_game_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=True),
        sa.Column("source_value", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "team_id",
            "stat_definition_id",
            name="uq_team_game_stat_fact",
        ),
    )
    _create_fact_indexes(
        "team_game_stats",
        ("game_id", "team_id", "stat_definition_id", "source_snapshot_id"),
    )


def _create_season_fact_tables() -> None:
    op.create_table(
        "player_season_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_season_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=True),
        sa.Column("source_value", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["player_season_id"], ["player_seasons.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_season_id",
            "stat_definition_id",
            name="uq_player_season_stat_fact",
        ),
    )
    _create_fact_indexes(
        "player_season_stats",
        ("player_season_id", "stat_definition_id", "source_snapshot_id"),
    )

    op.create_table(
        "team_season_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.String(length=16), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=False),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_field", sa.String(length=128), nullable=True),
        sa.Column("source_value", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sport_program_id",
            "season",
            "team_id",
            "stat_definition_id",
            name="uq_team_season_stat_fact",
        ),
    )
    _create_fact_indexes(
        "team_season_stats",
        (
            "sport_program_id",
            "season",
            "team_id",
            "stat_definition_id",
            "source_snapshot_id",
        ),
    )


def _create_trust_tables() -> None:
    op.create_table(
        "coverage_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("stat_definition_id", sa.Integer(), nullable=True),
        sa.Column("grain", sa.String(length=32), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("first_season", sa.String(length=16), nullable=True),
        sa.Column("last_season", sa.String(length=16), nullable=True),
        sa.Column("completeness", sa.String(length=32), nullable=False),
        sa.Column("known_limitations", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "completeness IN ('complete', 'partial', 'unknown', 'unavailable')",
            name="ck_coverage_window_completeness",
        ),
        sa.CheckConstraint(
            "grain IN ('game', 'season', 'career', 'match', 'heat', 'round', "
            "'meet', 'tournament')",
            name="ck_coverage_window_grain",
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_fact_indexes(
        "coverage_windows",
        ("sport_program_id", "stat_definition_id", "grain", "completeness"),
    )

    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sport_program_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("stat_definition_id", sa.Integer(), nullable=True),
        sa.Column("source_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("details", json_type, nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "issue_type IN ('unresolved_identity', 'reconciliation_mismatch', "
            "'source_conflict', 'parser_failure', 'missing_event', 'coverage_gap')",
            name="ck_data_quality_issue_type",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_data_quality_issue_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_review', 'resolved', 'accepted_gap')",
            name="ck_data_quality_issue_status",
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sport_program_id"], ["sport_programs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stat_definition_id"], ["stat_definitions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_fact_indexes(
        "data_quality_issues",
        (
            "sport_program_id",
            "game_id",
            "player_id",
            "team_id",
            "stat_definition_id",
            "source_snapshot_id",
            "issue_type",
            "status",
        ),
    )


def _create_fact_indexes(table_name: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column])


def _seed_wbb_reference_data() -> None:
    sport_programs = sa.table(
        "sport_programs",
        sa.column("id", sa.Integer()),
        sa.column("slug", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("sport", sa.String()),
        sa.column("gender", sa.String()),
        sa.column("season_format", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    teams = sa.table(
        "teams",
        sa.column("slug", sa.String()),
        sa.column("canonical_name", sa.String()),
        sa.column("short_name", sa.String()),
        sa.column("institution", sa.String()),
        sa.column("is_idaho", sa.Boolean()),
    )
    stat_definitions = sa.table(
        "stat_definitions",
        sa.column("sport_program_id", sa.Integer()),
        sa.column("stat_key", sa.String()),
        sa.column("display_label", sa.String()),
        sa.column("entity_scope", sa.String()),
        sa.column("value_type", sa.String()),
        sa.column("unit", sa.String()),
        sa.column("aggregation_method", sa.String()),
        sa.column("comparison_direction", sa.String()),
        sa.column("display_format", sa.String()),
        sa.column("source_field_aliases", json_type),
        sa.column("record_book_eligible", sa.Boolean()),
        sa.column("notability_eligible", sa.Boolean()),
    )

    op.bulk_insert(
        sport_programs,
        [
            {
                "slug": "womens-basketball",
                "display_name": "Women's Basketball",
                "sport": "basketball",
                "gender": "women",
                "season_format": "academic_year",
                "active": True,
            }
        ],
    )
    op.bulk_insert(
        teams,
        [
            {
                "slug": "idaho",
                "canonical_name": "Idaho",
                "short_name": "Idaho",
                "institution": "University of Idaho",
                "is_idaho": True,
            }
        ],
    )

    program_id = (
        op.get_bind()
        .execute(
            sa.select(sport_programs.c.id).where(
                sport_programs.c.slug == "womens-basketball"
            )
        )
        .scalar_one()
    )
    op.bulk_insert(
        stat_definitions,
        [
            {
                "sport_program_id": program_id,
                "entity_scope": "player",
                "value_type": "integer",
                "aggregation_method": "sum",
                "display_format": "0",
                **definition,
            }
            for definition in _wbb_stat_definitions()
        ],
    )


def _wbb_stat_definitions() -> tuple[dict, ...]:
    return (
        _stat(
            "minutes_played",
            "Minutes",
            "MIN",
            "minute",
            "neutral",
            False,
            False,
            value_type="duration",
        ),
        _stat(
            "field_goals_made", "Field Goals Made", "FG", "count", "higher", True, True
        ),
        _stat(
            "field_goals_attempted",
            "Field Goals Attempted",
            "FG",
            "count",
            "neutral",
            False,
            False,
        ),
        _stat(
            "three_point_field_goals_made",
            "Three-Point Field Goals Made",
            "3PT",
            "count",
            "higher",
            True,
            True,
        ),
        _stat(
            "three_point_field_goals_attempted",
            "Three-Point Field Goals Attempted",
            "3PT",
            "count",
            "neutral",
            False,
            False,
        ),
        _stat(
            "free_throws_made", "Free Throws Made", "FT", "count", "higher", True, True
        ),
        _stat(
            "free_throws_attempted",
            "Free Throws Attempted",
            "FT",
            "count",
            "neutral",
            False,
            False,
        ),
        _stat(
            "offensive_rebounds",
            "Offensive Rebounds",
            "ORB-DRB",
            "count",
            "higher",
            True,
            True,
        ),
        _stat(
            "defensive_rebounds",
            "Defensive Rebounds",
            "ORB-DRB",
            "count",
            "higher",
            True,
            True,
        ),
        _stat("total_rebounds", "Rebounds", "REB", "count", "higher", True, True),
        _stat("personal_fouls", "Personal Fouls", "PF", "count", "lower", False, False),
        _stat("assists", "Assists", "A", "count", "higher", True, True),
        _stat("turnovers", "Turnovers", "TO", "count", "lower", False, False),
        _stat("blocks", "Blocks", "BLK", "count", "higher", True, True),
        _stat("steals", "Steals", "STL", "count", "higher", True, True),
        _stat("points", "Points", "PTS", "count", "higher", True, True),
    )


def _stat(
    stat_key: str,
    display_label: str,
    source_alias: str,
    unit: str,
    comparison_direction: str,
    record_book_eligible: bool,
    notability_eligible: bool,
    value_type: str = "integer",
) -> dict:
    return {
        "stat_key": stat_key,
        "display_label": display_label,
        "source_field_aliases": [source_alias],
        "unit": unit,
        "value_type": value_type,
        "comparison_direction": comparison_direction,
        "record_book_eligible": record_book_eligible,
        "notability_eligible": notability_eligible,
    }


def downgrade() -> None:
    for table_name in (
        "data_quality_issues",
        "coverage_windows",
        "team_season_stats",
        "player_season_stats",
        "team_game_stats",
        "player_game_stats",
        "stat_definitions",
        "player_seasons",
        "player_external_identities",
        "opponent_aliases",
        "players",
        "teams",
        "sport_programs",
    ):
        op.drop_table(table_name)
