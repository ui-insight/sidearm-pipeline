# Vandals Stats Pipeline — Walkthrough

This guide covers everything from first-time setup through running the full
agentic workflow: ingest → generate → evaluate → approve. It also explains how
to run tests, use the Natural Language Query agent, and tune the eval harness.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [First-Time Setup](#2-first-time-setup)
3. [Running the Application](#3-running-the-application)
4. [Core Workflow: Ingest → Generate → Evaluate → Approve](#4-core-workflow)
5. [Scheduler (Automated Ingestion)](#5-scheduler-automated-ingestion)
6. [Natural Language Query Agent](#6-natural-language-query-agent)
7. [Agent Runs Provenance Log](#7-agent-runs-provenance-log)
8. [Running Tests](#8-running-tests)
9. [Eval Harness (Local)](#9-eval-harness-local)
10. [Database Migrations](#10-database-migrations)
11. [Docker Deployment](#11-docker-deployment)
12. [Environment Reference](#12-environment-reference)

---

## 1. Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11 |
| Node.js | 18 |
| Docker + Docker Compose | any recent version |
| PostgreSQL | 16 (via Docker is fine) |

You will also need an **Anthropic API key** (or a University of Idaho
[MindRouter](https://mindrouter.uidaho.edu/documentation) key) for the
AI coverage generation and NL-query features. Without a key the backend
starts normally; only the `/generate` and `/nl-query` endpoints will return
errors.

---

## 2. First-Time Setup

### 2a. Clone and configure environment

```bash
git clone <repo-url>
cd sidearm-pipeline

cp .env.example .env
# Open .env and set at minimum:
#   ANTHROPIC_API_KEY=sk-ant-...   (or MindRouter key + ANTHROPIC_BASE_URL)
#   CONTENT_MODEL=claude-opus-4-7  (or whichever model you have access to)
```

### 2b. Install dependencies (all at once)

```bash
make setup
```

This creates `backend/.venv`, installs Python packages, and runs `npm ci` for
both the frontend and e2e directories.

Or install manually:

```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 2c. Start PostgreSQL

```bash
docker compose up -d postgres
```

Wait until the container is healthy (roughly 5–10 seconds):

```bash
docker compose ps   # STATUS should show "(healthy)"
```

### 2d. Run database migrations

```bash
cd backend
.venv/bin/alembic upgrade head
cd ..
```

This applies all four migrations:

| Revision | Description |
|----------|-------------|
| `0001_initial` | Games, team stats, player stats, scoring plays |
| `0002_ingest_run_history` | Ingest run audit table |
| `0003_ingest_retry_attempts` | Retry-attempt tracking |
| `0004_agent_runs_provenance` | AgentRun, AgentRunStep, AgentRunEvaluation |

---

## 3. Running the Application

### Backend (development)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### Frontend (development)

In a separate terminal:

```bash
cd frontend
npm run dev
```

The UI is now at `http://localhost:5173`.

### Verify both are running

```bash
curl http://localhost:8000/api/v1/health
# {"status":"healthy"}

curl http://localhost:8000/api/v1/ready
# {"status":"ready"}
```

---

## 4. Core Workflow

The full agentic loop is:
**Ingest boxscore → Generate AI coverage → (Optional) Run eval checks →
Approve or Reject → View published content**

### Step 1 — Ingest a boxscore

**UI:** Open `http://localhost:5173`, paste a Sidearm boxscore URL into the
"Ingest a boxscore" form, and click **Ingest**.

**API:**
```bash
curl -s -X POST http://localhost:8000/api/v1/games \
  -H "Content-Type: application/json" \
  -d '{"url":"https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"}' \
  | python3 -m json.tool
```

The response is a `GameDetail` object. Note the `id` field — you will need it
in the next steps.

```json
{
  "id": 1,
  "sport": "football",
  "home_team": "Idaho",
  "away_team": "UC Davis",
  "home_score": 31,
  "away_score": 28,
  ...
}
```

### Step 2 — Generate AI coverage

**UI:** Navigate to the game's detail page (`/games/1`). Click
**Generate Coverage**. The panel shows a spinner while the agent runs, then
displays the headline, recap, spotlight, and social post for review.

**API:**
```bash
GAME_ID=1

curl -s -X POST http://localhost:8000/api/v1/games/$GAME_ID/generate \
  | python3 -m json.tool
```

The response is an `AgentRunRead` object (not `GeneratedContent` — content is
not persisted yet). Note the `id` field — this is the agent run ID.

```json
{
  "id": 1,
  "agent_name": "recap-writer",
  "status": "succeeded",
  "output_payload": {
    "headline": "Idaho Edges UC Davis 31-28 in Thriller",
    "recap": "...",
    "spotlight_player": "...",
    "spotlight_body": "...",
    "social_post": "..."
  },
  "human_verdict": null,
  ...
}
```

> **Breaking change note:** This endpoint previously returned
> `GeneratedContentRead`. It now returns `AgentRunRead`. Content is only
> created after an explicit approval (Step 4).

### Step 3 — Run eval checks (optional but recommended)

**UI:** In the AI Coverage panel, click **Run eval checks**. Colored chips
appear for each metric (score_present, teams_mentioned, word_count,
headline_length, social_length, stats_cited).

**API:**
```bash
RUN_ID=1

curl -s -X POST http://localhost:8000/api/v1/agent-runs/$RUN_ID/evaluate \
  | python3 -m json.tool
```

The response is the updated `AgentRunRead` with `eval_score` (0.0–1.0) and a
populated `evaluations` array:

```json
{
  "eval_score": 0.833,
  "evaluations": [
    {"metric_name": "score_present",    "passed": true,  "score": 1.0},
    {"metric_name": "teams_mentioned",  "passed": true,  "score": 1.0},
    {"metric_name": "word_count",       "passed": true,  "score": 1.0},
    {"metric_name": "headline_length",  "passed": true,  "score": 1.0},
    {"metric_name": "social_length",    "passed": true,  "score": 1.0},
    {"metric_name": "stats_cited",      "passed": false, "score": 0.0}
  ]
}
```

### Step 4 — Approve or Reject

**UI:** Click **Approve** to publish or **Reject** to discard.

**API — Approve:**
```bash
curl -s -X POST http://localhost:8000/api/v1/agent-runs/$RUN_ID/verdict \
  -H "Content-Type: application/json" \
  -d '{"verdict":"approved"}' \
  | python3 -m json.tool
```

An `approved` verdict creates a `GeneratedContent` row linked to the game.
The response is `GeneratedContentRead`:

```json
{
  "id": 1,
  "game_id": 1,
  "headline": "Idaho Edges UC Davis 31-28 in Thriller",
  "recap": "...",
  "spotlight_player": "...",
  "spotlight_body": "...",
  "social_post": "...",
  "generated_at": "2026-05-07T18:00:00Z"
}
```

**API — Reject:**
```bash
curl -s -X POST http://localhost:8000/api/v1/agent-runs/$RUN_ID/verdict \
  -H "Content-Type: application/json" \
  -d '{"verdict":"rejected"}' \
  | python3 -m json.tool
```

A `rejected` verdict marks the run as rejected; no `GeneratedContent` is
created. You can regenerate at any time (Step 2) to produce a new run.

### Step 5 — Verify published content

```bash
curl -s http://localhost:8000/api/v1/games/$GAME_ID \
  | python3 -m json.tool | python3 -c \
  "import sys,json; d=json.load(sys.stdin); [print(c['headline']) for c in d['generated_content']]"
```

---

## 5. Scheduler (Automated Ingestion)

The scheduler polls all registered Sidearm schedule pages every N seconds and
ingests any games that have reached `event_status=final`.

Enable it in `.env`:

```
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=900   # 15 minutes; minimum is 60
```

Restart the backend. On startup you will see:

```
INFO  [app.services.scheduler] scheduler started interval_seconds=900
```

Each cycle logs:

```
INFO  [app.services.scheduler] ingest cycle started
INFO  [app.services.scheduler] ingested game_id=3 url=https://govandals.com/...
INFO  [app.services.scheduler] ingest cycle complete ingested=1 skipped=4 errors=0
```

**To discover or bulk-import a schedule manually** (without waiting for the
scheduler):

- **UI:** Use the "Discover schedule" panel on the home page — pick a sport and
  season, click **Load schedule**, then **Import schedule**.
- **API:**
  ```bash
  # Preview (no DB writes)
  curl "http://localhost:8000/api/v1/sources/schedule?sport=football&season=2025"

  # Import all final games found
  curl -X POST "http://localhost:8000/api/v1/sources/schedule/import?sport=football&season=2025"
  ```

---

## 6. Natural Language Query Agent

Ask plain-English questions about the games database. The agent uses a
**MCP tool-use loop**: the model calls `describe_schema` to inspect the
database, then calls `execute_read_query` with a `SELECT` statement, then
answers in plain English. Each tool call is recorded as an `AgentRunStep` for
full provenance.

**UI:** Navigate to `/query` (linked from the home page header as **Query →**).
Type a question and click **Ask**.

**API:**
```bash
curl -s -X POST http://localhost:8000/api/v1/nl-query \
  -H "Content-Type: application/json" \
  -d '{"question":"How many games have been ingested?"}' \
  | python3 -m json.tool
```

Response:
```json
{
  "question": "How many games have been ingested?",
  "sql": "SELECT COUNT(*) AS total FROM games",
  "rows": [{"total": 3}],
  "answer": "There are 3 games ingested.",
  "agent_run_id": 5
}
```

More example questions:
- `"Which sport has the most games?"`
- `"List all football games from the 2025 season"`
- `"What was the highest scoring game?"`
- `"Show me all games where Idaho won"`

**MCP tools available to the nl-query agent:**

| Tool | Description |
|------|-------------|
| `describe_schema` | Returns a compact listing of all public tables and their columns |
| `execute_read_query(sql)` | Executes a `SELECT` query and returns up to 100 rows as JSON |

**Constraints:** The `execute_read_query` MCP server enforces a `SELECT`-only
guard — any non-`SELECT` statement raises an error before it reaches the
database. The loop is also capped at `MAX_TOOL_ITERATIONS` model turns (default
10) to bound cost.

---

## 7. Agent Runs Provenance Log

Every agent invocation — whether it succeeds or fails — creates an `AgentRun`
record with full step-by-step provenance.

**UI:** Navigate to `/agent-runs` (linked from the home page as **Agent runs →**).
The table shows agent name, linked game, status, eval score bar, verdict badge,
timestamp, and duration.

**API — List recent runs:**
```bash
# All runs (newest first, up to 50)
curl http://localhost:8000/api/v1/agent-runs

# Filter by agent
curl "http://localhost:8000/api/v1/agent-runs?agent_name=recap-writer"

# Filter by status
curl "http://localhost:8000/api/v1/agent-runs?status=succeeded"

# Combined
curl "http://localhost:8000/api/v1/agent-runs?agent_name=nl-query&status=failed&limit=10"
```

**API — Get a single run with full step detail:**
```bash
curl http://localhost:8000/api/v1/agent-runs/1 | python3 -m json.tool
```

The `steps` array records each phase of the agent. Both agents now use a
**MCP tool-use loop**, so the step names reflect the tools the model chose to
call rather than a fixed pipeline:

**recap-writer steps** (order depends on which tools the model calls):

| Step name | Description |
|-----------|-------------|
| `tool:get_game_summary` | Fetched core game info (teams, score, date) |
| `tool:get_team_stats` | Fetched team-level stats |
| `tool:get_player_stats` | Fetched player stat groups |
| `tool:get_scoring_plays` | Fetched scoring plays in order |
| `parse_output` | Validated the final JSON against the coverage schema |

**nl-query steps** (order depends on model behavior):

| Step name | Description |
|-----------|-------------|
| `tool:describe_schema` | Fetched the database schema listing |
| `tool:execute_read_query` | Executed the generated SELECT query |

Each step captures `input_snapshot`, `output_snapshot`, `status`, timing, and
any `error_message`. Tool steps record the tool input and output byte length;
`parse_output` records the full validated coverage object.

---

## 8. Running Tests

### Backend tests

```bash
cd backend
.venv/bin/pytest -v --tb=short
```

65 tests pass; 5 are skipped. The skipped tests exercise the MCP server tool
functions directly against a live PostgreSQL connection — they auto-skip when
using the default SQLite in-memory backend. The test suite is otherwise
self-contained with no Postgres connection required.

To run against a real Postgres database:

```bash
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_app" \
  .venv/bin/pytest -v --tb=short
```

Run a specific test file:

```bash
.venv/bin/pytest tests/test_agent_runs.py -v
.venv/bin/pytest tests/test_nl_query.py -v
.venv/bin/pytest tests/test_games.py -v
```

Run a single test by name:

```bash
.venv/bin/pytest tests/test_agent_runs.py::test_approve_verdict_creates_generated_content -v
```

### Frontend tests

```bash
cd frontend
npm run build    # TypeScript compile + Vite bundle
npm test         # Vitest unit tests
```

### All checks at once

```bash
make check-all
```

---

## 9. Eval Harness (Local)

The eval harness can be run locally with pytest against pre-built fixtures,
without requiring an API key or a running server.

### recap-writer evals

```bash
cd agents/recap-writer/evals
python3 -m pytest test_evals.py -v
```

Expected output:

```
PASSED test_score_present_with_fixture[football_uc_davis_2025.json]
PASSED test_score_present_with_fixture[mens_basketball_idaho_2026.json]
PASSED test_word_count_in_range[football_uc_davis_2025.json]
PASSED test_word_count_in_range[mens_basketball_idaho_2026.json]
PASSED test_all_deterministic_checks_pass[football_uc_davis_2025.json]
PASSED test_all_deterministic_checks_pass[mens_basketball_idaho_2026.json]
```

### Adding a new eval fixture

1. Ingest a real game and generate approved coverage.
2. Export it as JSON matching the fixture schema:

```json
{
  "game_data": {
    "sport": "football",
    "season": "2025",
    "game_date": "11/8/2025",
    "home_team": "Idaho",
    "away_team": "UC Davis",
    "home_score": 31,
    "away_score": 28,
    "team_stats": [
      {"stat_name": "First Downs", "home_value": "22", "away_value": "18", "sort_order": 0}
    ],
    "scoring_plays": []
  },
  "coverage": {
    "headline": "Idaho Edges UC Davis 31-28",
    "recap": "...",
    "spotlight_player": "Last, First",
    "spotlight_body": "...",
    "social_post": "..."
  },
  "expected_pass": {
    "score_present": true,
    "teams_mentioned": true,
    "word_count": true,
    "headline_length": true,
    "social_length": true,
    "stats_cited": true
  }
}
```

3. Save it as `agents/recap-writer/evals/fixtures/<name>.json`.
4. Re-run `pytest test_evals.py -v` — it auto-discovers all `.json` files in
   `fixtures/`.

### Eval metrics reference

| Check | Source function | Pass condition |
|-------|----------------|----------------|
| `score_present` | `check_score_present` | Both final scores appear verbatim in the recap |
| `teams_mentioned` | `check_teams_mentioned` | Both team names appear in the recap |
| `word_count` | `check_word_count` | Recap is 250–350 words |
| `headline_length` | `check_headline_length` | Headline ≤ 90 characters |
| `social_length` | `check_social_length` | Social post ≤ 280 characters |
| `stats_cited` | `check_stats_cited` | At least one stat from team_stats is cited |

The `composite_score` is the mean of all individual scores (each check
contributes equally).

### Customizing eval thresholds

Edit `agents/recap-writer/evals/eval_metrics.py`:

```python
# Change word count bounds
def check_word_count(recap: str, min_words: int = 250, max_words: int = 350) -> EvalResult:
    ...

# Change headline character limit
def check_headline_length(headline: str, max_chars: int = 90) -> EvalResult:
    ...
```

---

## 10. Database Migrations

### Apply pending migrations

```bash
cd backend
.venv/bin/alembic upgrade head
```

### Roll back one step

```bash
.venv/bin/alembic downgrade -1
```

### Check current revision

```bash
.venv/bin/alembic current
```

### Create a new migration after changing a model

```bash
.venv/bin/alembic revision --autogenerate -m "describe your change"
.venv/bin/alembic upgrade head
```

Always review the generated file in `backend/migrations/versions/` before
applying — Alembic's autogenerate can miss certain schema details.

---

## 11. Docker Deployment

### Full stack

```bash
docker compose up --build
```

- **Frontend + API proxy:** `http://localhost:9200`
- **Backend API directly:** `http://localhost:9200/api/`

On first run, migrations do not run automatically. Exec into the backend
container to apply them:

```bash
docker compose exec backend alembic upgrade head
```

### Individual services

```bash
# Start only the database
docker compose up -d postgres

# Build and start only the backend (uses host Postgres)
docker compose up --build backend
```

### Logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Smoke test

```bash
make docker-smoke
```

This builds the stack, waits for health checks, and verifies both the frontend
and the `/api/v1/health` endpoint respond correctly.

---

## 12. Environment Reference

All variables live in `.env` (copy from `.env.example`).

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/app` | Primary database |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **must** change in production |
| `DEV_MODE` | `true` | Set `false` in production to enforce CORS and secret-key checks |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:9200"]` | Allowed CORS origins |
| `ANTHROPIC_API_KEY` | _(unset)_ | Anthropic or MindRouter API key |
| `ANTHROPIC_BASE_URL` | _(unset)_ | Override for MindRouter: `https://mindrouter.uidaho.edu/anthropic` |
| `CONTENT_MODEL` | _(unset)_ | Model ID, e.g. `claude-opus-4-7` |
| `SCHEDULER_ENABLED` | `false` | Enable background ingestion scheduler |
| `SCHEDULER_INTERVAL_SECONDS` | `900` | Polling interval (minimum 60) |
| `SIDEARM_REQUEST_TIMEOUT_SECONDS` | `20` | HTTP timeout for Sidearm fetches |
| `SIDEARM_FETCH_MAX_ATTEMPTS` | `3` | Max retry attempts per fetch |
| `SIDEARM_FETCH_BACKOFF_SECONDS` | `0.5` | Base backoff between retries |
| `RATE_LIMIT_ENABLED` | `false` | Enable per-IP rate limiting middleware |
| `RATE_LIMIT_REQUESTS` | `60` | Max requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window size |
| `MAX_TOOL_ITERATIONS` | `10` | Maximum MCP tool-call turns per agent run (1–50) |

### MindRouter configuration

If you are using the University of Idaho MindRouter gateway instead of
Anthropic directly:

```env
ANTHROPIC_API_KEY=<your MindRouter key>
ANTHROPIC_BASE_URL=https://mindrouter.uidaho.edu/anthropic
CONTENT_MODEL=<model listed at GET /v1/models on MindRouter>
```

MindRouter speaks the Anthropic Messages API, so no code changes are needed —
only these environment variables.
