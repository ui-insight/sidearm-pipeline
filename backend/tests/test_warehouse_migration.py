"""End-to-end Alembic coverage for the normalized warehouse migration."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select


def test_normalized_warehouse_migration_upgrades_and_downgrades(tmp_path) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "warehouse-migration.sqlite3"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{database_path}",
    }

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        metadata = MetaData()
        stat_definitions = Table("stat_definitions", metadata, autoload_with=connection)
        sport_programs = Table("sport_programs", metadata, autoload_with=connection)
        source_snapshot_columns = {
            column["name"]: column
            for column in inspect(connection).get_columns("source_snapshots")
        }
        quality_issue_columns = {
            column["name"]
            for column in inspect(connection).get_columns("data_quality_issues")
        }
        identity_resolution_columns = {
            column["name"]
            for column in inspect(connection).get_columns("player_identity_resolutions")
        }
        workspace_view_columns = {
            column["name"]
            for column in inspect(connection).get_columns("workspace_views")
        }
        notability_policy_columns = {
            column["name"]
            for column in inspect(connection).get_columns("notability_policies")
        }
        achievement_columns = {
            column["name"]
            for column in inspect(connection).get_columns("achievement_suggestions")
        }
        policy_count = connection.scalar(
            select(func.count()).select_from(
                Table("notability_policies", metadata, autoload_with=connection)
            )
        )
        definition_count = connection.scalar(
            select(func.count()).select_from(stat_definitions)
        )
        program_slug = connection.scalar(select(sport_programs.c.slug))
    engine.dispose()

    assert {
        "sport_programs",
        "teams",
        "players",
        "player_external_identities",
        "player_seasons",
        "player_identity_resolutions",
        "stat_definitions",
        "player_game_stats",
        "team_game_stats",
        "player_season_stats",
        "team_season_stats",
        "coverage_windows",
        "data_quality_issues",
        "workspace_views",
        "notability_policies",
        "notability_policy_metrics",
        "achievement_suggestions",
    }.issubset(tables)
    assert definition_count == 16
    assert policy_count == 1
    assert program_slug == "womens-basketball"
    assert source_snapshot_columns["game_id"]["nullable"] is True
    assert {
        "source_system",
        "source_type",
        "source_url",
    }.issubset(source_snapshot_columns)
    assert "deduplication_key" in quality_issue_columns
    assert {
        "match_key",
        "source_player_id",
        "normalized_name",
        "created_from_issue_id",
    }.issubset(identity_resolution_columns)
    assert {
        "id",
        "name",
        "view_kind",
        "params",
        "created_by",
        "created_at",
    }.issubset(workspace_view_columns)
    assert {
        "sport_program_id",
        "version",
        "scope_weights",
        "top_n",
        "active",
    }.issubset(notability_policy_columns)
    assert {
        "game_id",
        "player_id",
        "achievement_type",
        "computed_value",
        "notability_score",
        "coverage_context",
        "phrasing",
        "ai_rank",
        "ai_model",
        "ai_prompt_version",
        "ai_output_hash",
        "ai_ranked_at",
    }.issubset(achievement_columns)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0008_deterministic_achievements",
        ],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        achievement_columns = {
            column["name"]
            for column in inspect(connection).get_columns("achievement_suggestions")
        }
    engine.dispose()
    assert "achievement_suggestions" in tables
    assert "phrasing" in achievement_columns
    assert "ai_rank" not in achievement_columns

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0007_shared_workspace_views",
        ],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "achievement_suggestions" not in tables
    assert "notability_policies" not in tables

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0006_player_identity_resolutions",
        ],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "workspace_views" not in tables

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0005_roster_source_provenance",
        ],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert "player_identity_resolutions" not in tables

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "0004_normalized_warehouse_core",
        ],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        source_snapshot_columns = {
            column["name"]: column
            for column in inspect(connection).get_columns("source_snapshots")
        }
    engine.dispose()
    assert source_snapshot_columns["game_id"]["nullable"] is False
    assert "source_url" not in source_snapshot_columns

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0003_ingest_retry_attempts"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(f"sqlite:///{database_path}")
    remaining_tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert "games" in remaining_tables
    assert "stat_definitions" not in remaining_tables


def test_engine_registers_normalized_models_in_a_fresh_process() -> None:
    backend_dir = Path(__file__).parents[1]
    required_tables = {
        "sport_programs",
        "players",
        "player_identity_resolutions",
        "stat_definitions",
        "player_game_stats",
        "team_game_stats",
        "player_season_stats",
        "team_season_stats",
        "coverage_windows",
        "data_quality_issues",
        "workspace_views",
        "notability_policies",
        "achievement_suggestions",
    }
    script = (
        "from app.db.engine import Base; "
        f"required={required_tables!r}; "
        "missing=required-set(Base.metadata.tables); "
        "assert not missing, missing"
    )

    subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_dir,
        check=True,
        capture_output=True,
        text=True,
    )
