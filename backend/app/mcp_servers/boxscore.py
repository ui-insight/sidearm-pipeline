# backend/app/mcp_servers/boxscore.py
"""Boxscore MCP server — Tier 1 read-only tools.

Exposes four selective-fetch tools to the recap-writer agent.
Never writes to the database.
"""
import json
import os

import asyncpg
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("boxscore")


def _dsn() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql://")


@mcp.tool()
async def get_game_summary(game_id: int) -> str:
    """Return core game info: teams, score, date, sport, season."""
    conn = await asyncpg.connect(_dsn())
    row = await conn.fetchrow(
        "SELECT title, sport, season, game_date, home_team, away_team, "
        "home_score, away_score FROM games WHERE id = $1",
        game_id,
    )
    await conn.close()
    if row is None:
        raise ValueError(f"Game {game_id} not found")
    return json.dumps(dict(row), default=str)


@mcp.tool()
async def get_team_stats(game_id: int) -> str:
    """Return team-level stats for a game as JSON."""
    conn = await asyncpg.connect(_dsn())
    rows = await conn.fetch(
        "SELECT stat_name, home_value, away_value FROM team_stats "
        "WHERE game_id = $1 ORDER BY sort_order",
        game_id,
    )
    await conn.close()
    return json.dumps([dict(r) for r in rows])


@mcp.tool()
async def get_player_stats(game_id: int) -> str:
    """Return player stat groups for a game as JSON."""
    conn = await asyncpg.connect(_dsn())
    rows = await conn.fetch(
        "SELECT category, team, columns, rows FROM player_stats "
        "WHERE game_id = $1",
        game_id,
    )
    await conn.close()
    return json.dumps([dict(r) for r in rows], default=str)


@mcp.tool()
async def get_scoring_plays(game_id: int) -> str:
    """Return scoring plays for a game as JSON."""
    conn = await asyncpg.connect(_dsn())
    rows = await conn.fetch(
        "SELECT period, clock, team, description, away_score, home_score "
        "FROM scoring_plays WHERE game_id = $1 ORDER BY sort_order",
        game_id,
    )
    await conn.close()
    return json.dumps([dict(r) for r in rows])


if __name__ == "__main__":
    mcp.run()
