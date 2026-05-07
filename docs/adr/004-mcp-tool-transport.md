# ADR-004: MCP Tool Transport — stdio subprocess

## Status
Accepted

## Context

Both agentic capabilities (nl-query, recap-writer) were upgraded from fixed
one-shot pipelines to dynamic tool-use loops in which the model drives its own
data access. This required choosing a transport mechanism to connect the FastAPI
process (which runs the agents) to the MCP tool servers (which hold database
capability).

Three options were evaluated:

| Option | Description |
|---|---|
| **stdio subprocess** | Spawn the MCP server as a child process; communicate over stdin/stdout |
| **In-process** | Import the MCP server module directly and call functions without subprocess overhead |
| **HTTP sidecar** | Run the MCP server as a separate long-lived HTTP service |

## Decision

Use **stdio subprocess transport** via `mcp.client.stdio.stdio_client`.

Each agent run spawns a fresh subprocess for its MCP server
(`app.mcp_servers.database` or `app.mcp_servers.boxscore`), communicates
over stdio for the duration of the run, and the subprocess exits when the
context manager closes.

## Consequences

### Why stdio subprocess

**Process isolation**: A crash or hang inside the MCP server (e.g., a runaway
asyncpg query) cannot bring down the FastAPI application process. The subprocess
is an independent OS process.

**Clear capability boundary**: The MCP server is the single authoritative place
where safety guards are enforced (SELECT-only regex in `database.py`). There is no
way for calling code to bypass the guard by importing around it — the transport
boundary enforces it.

**Standard MCP primitive**: stdio is the MCP specification's canonical local
transport. Using it means the servers are independently runnable
(`python -m app.mcp_servers.database`) and testable without a running FastAPI app.

**Fresh state per run**: Each agent run gets a pristine subprocess with no shared
connection pool or cached state from previous runs.

### Why not in-process

Calling the tool functions directly (bypassing subprocess transport) would share
the FastAPI event loop with the tool servers. This creates the risk of:
- Connection pool contention between the app's SQLAlchemy pool and the tool's
  asyncpg connections.
- Errors in tool code propagating into the FastAPI exception handler.
- The safety guard (SELECT-only regex) becoming bypassable by internal callers
  importing the function directly without going through MCP validation.

In-process calling is used only in unit tests (`test_mcp_servers.py`) where the
goal is to verify the tool logic in isolation, not to test the transport.

### Why not HTTP sidecar

An HTTP sidecar would require:
- An additional listening port and port management in docker-compose and production.
- A long-lived service that must be started, health-checked, and restarted
  independently of the FastAPI app.
- Authentication or network policy to prevent external access to the tool endpoints.

For local tool servers accessed only from within the same process tree, stdio
avoids all of this complexity with no meaningful throughput disadvantage (agent
runs are I/O-bound on the Anthropic API, not on tool call latency).

### Trade-offs

**Subprocess startup latency** (~100–300 ms per agent run) is the main cost. This
is acceptable because:
1. Agent runs are already latency-dominated by the Anthropic API round-trips.
2. Agent runs are asynchronous background operations, not synchronous HTTP request
   handlers.
3. The plan plan calls for at most `MAX_TOOL_ITERATIONS=10` model turns per run,
   meaning startup cost is amortized across multiple tool calls within a single
   subprocess lifetime.

**Safety**: The SELECT guard in `database.py` means nl-query can never mutate
data even if the prompt is manipulated (prompt injection). The guard validates
at the transport boundary, not in application code.
