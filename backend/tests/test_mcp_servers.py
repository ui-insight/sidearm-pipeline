"""Unit tests for MCP server tool functions.

These tests call the underlying async tool functions directly,
bypassing the stdio subprocess transport. They use the test DB session
(SQLite in-memory for CI, or a real Postgres URL via TEST_DATABASE_URL).
"""

from __future__ import annotations

import json
import os

import pytest

# ---------------------------------------------------------------------------
# database.py MCP server tests
# ---------------------------------------------------------------------------


async def test_execute_read_query_select_works():
    """A simple SELECT query should return a list with the expected row."""
    # Override DATABASE_URL to whatever the test DB is
    db_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    # execute_read_query uses asyncpg (postgres). For pure SQLite test envs,
    # skip this test gracefully since asyncpg cannot connect to SQLite.
    if "sqlite" in db_url:
        pytest.skip("execute_read_query requires a PostgreSQL connection")

    os.environ["DATABASE_URL"] = db_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    from app.mcp_servers.database import execute_read_query

    result = await execute_read_query("SELECT 1 AS n")
    data = json.loads(result)
    assert isinstance(data, list)
    assert data[0]["n"] == 1


async def test_execute_read_query_rejects_non_select():
    """The SELECT-only guard should raise ValueError for mutating statements."""
    from app.mcp_servers.database import execute_read_query

    with pytest.raises(ValueError, match="Safety guard"):
        await execute_read_query("DROP TABLE games")

    with pytest.raises(ValueError, match="Safety guard"):
        await execute_read_query("INSERT INTO games VALUES (1)")

    with pytest.raises(ValueError, match="Safety guard"):
        await execute_read_query("UPDATE games SET home_score=0")

    with pytest.raises(ValueError, match="Safety guard"):
        await execute_read_query("DELETE FROM games")


async def test_describe_schema_returns_tables():
    """describe_schema should list known tables when connected to Postgres."""
    db_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    if "sqlite" in db_url:
        pytest.skip("describe_schema requires a PostgreSQL connection")

    os.environ["DATABASE_URL"] = db_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    # Reload to pick up the updated env var
    import importlib

    from app.mcp_servers import database as db_mod

    importlib.reload(db_mod)

    result = await db_mod.describe_schema()
    assert "games" in result
    assert "agent_runs" in result


# ---------------------------------------------------------------------------
# boxscore.py MCP server tests
# ---------------------------------------------------------------------------


async def test_get_game_summary_returns_teams(db_session):
    """get_game_summary should return team fields for a known game_id."""
    db_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    if "sqlite" in db_url:
        pytest.skip("boxscore tools require a PostgreSQL connection")

    # Insert a minimal game row via the ORM session so referential integrity holds
    from app.models.game import Game

    game = Game(
        canonical_uid="test-mcp-001",
        sport="basketball",
        season="2024-25",
        game_date="2025-01-15",
        home_team="Idaho",
        away_team="Montana",
        home_score=75,
        away_score=68,
        title="Idaho vs Montana",
        source_url="https://example.com",
    )
    db_session.add(game)
    await db_session.flush()

    os.environ["DATABASE_URL"] = db_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    from app.mcp_servers.boxscore import get_game_summary

    result = await get_game_summary(game.id)
    data = json.loads(result)
    assert data["home_team"] == "Idaho"
    assert data["away_team"] == "Montana"
    assert data["home_score"] == 75


async def test_get_team_stats_returns_rows(db_session):
    """get_team_stats should return stat rows for a game."""
    db_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    if "sqlite" in db_url:
        pytest.skip("boxscore tools require a PostgreSQL connection")

    from app.models.team_stat import TeamStat

    from app.models.game import Game

    game = Game(
        canonical_uid="test-mcp-002",
        sport="football",
        season="2024",
        game_date="2024-09-07",
        home_team="Idaho",
        away_team="Eastern Washington",
        home_score=28,
        away_score=21,
        title="Idaho vs EWU",
        source_url="https://example.com",
    )
    db_session.add(game)
    await db_session.flush()

    stat = TeamStat(
        game_id=game.id,
        stat_name="Total Yards",
        home_value="350",
        away_value="310",
        sort_order=1,
    )
    db_session.add(stat)
    await db_session.flush()

    os.environ["DATABASE_URL"] = db_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    from app.mcp_servers.boxscore import get_team_stats

    result = await get_team_stats(game.id)
    data = json.loads(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["stat_name"] == "Total Yards"


async def test_get_game_summary_raises_for_missing_game():
    """get_game_summary should raise ValueError for a non-existent game_id."""
    db_url = os.getenv(
        "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
    )
    if "sqlite" in db_url:
        pytest.skip("boxscore tools require a PostgreSQL connection")

    os.environ["DATABASE_URL"] = db_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    from app.mcp_servers.boxscore import get_game_summary

    with pytest.raises(ValueError, match="not found"):
        await get_game_summary(999999)
