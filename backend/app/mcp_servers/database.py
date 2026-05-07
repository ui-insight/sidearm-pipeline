# backend/app/mcp_servers/database.py
"""Database MCP server — Tier 2 read-only tools.

Run as a subprocess. Exposes two tools to the nl-query agent:
  describe_schema  — returns table/column listing for all public tables
  execute_read_query(sql) — SELECT-only guard + executes + returns JSON rows
"""
import json
import os
import re

import asyncpg
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("database")
MAX_ROWS = 100


def _dsn() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql://")


@mcp.tool()
async def describe_schema() -> str:
    """Return a compact listing of all tables and their columns."""
    conn = await asyncpg.connect(_dsn())
    rows = await conn.fetch("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)
    await conn.close()
    tables: dict[str, list[str]] = {}
    for r in rows:
        tables.setdefault(r["table_name"], []).append(r["column_name"])
    lines = [f"  {t}({', '.join(c)})" for t, c in sorted(tables.items())]
    return "\n".join(lines)


@mcp.tool()
async def execute_read_query(sql: str) -> str:
    """Execute a SELECT query and return up to 100 rows as JSON.

    Raises ValueError if the statement is not a SELECT.
    """
    if not re.match(r"(?i)^\s*SELECT\b", sql.strip()):
        raise ValueError(
            f"Safety guard: only SELECT statements allowed. Got: {sql[:80]}"
        )
    conn = await asyncpg.connect(_dsn())
    rows = await conn.fetch(sql)
    await conn.close()
    data = [dict(r) for r in rows[:MAX_ROWS]]
    return json.dumps(data, default=str)


if __name__ == "__main__":
    mcp.run()
