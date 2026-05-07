# backend/app/agents/_mcp_client.py
"""Shared helper for spawning MCP server subprocesses.

Usage:
    async with mcp_session("database") as session:
        tools = await session.list_tools()
        result = await session.call_tool("describe_schema", {})
"""
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import settings


def _server_params(server_name: str) -> StdioServerParameters:
    """Build subprocess params for a named MCP server module."""
    env = {**os.environ, "DATABASE_URL": settings.DATABASE_URL}
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", f"app.mcp_servers.{server_name}"],
        env=env,
    )


@asynccontextmanager
async def mcp_session(server_name: str) -> AsyncIterator[ClientSession]:
    """Async context manager that spawns an MCP subprocess and yields a session."""
    params = _server_params(server_name)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def mcp_tools_to_anthropic(tools) -> list[dict]:
    """Convert mcp.types.Tool list to Anthropic tool dicts."""
    result = []
    for tool in tools:
        result.append(
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
        )
    return result
