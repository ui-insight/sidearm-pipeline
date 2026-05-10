"""Eval runner service for agent run evaluation.

Called by POST /api/v1/agent-runs/{id}/evaluate.
Loads the AgentRun and its parent Game, runs all deterministic checks,
optionally runs LLM-as-judge, persists evaluation rows, and updates
AgentRun.eval_score.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentRun, AgentRunEvaluation

logger = logging.getLogger(__name__)

# Path to the eval_metrics module in the agents directory
_EVAL_METRICS_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "agents"
    / "recap-writer"
    / "evals"
    / "eval_metrics.py"
)


def _load_eval_metrics():
    """Dynamically load the eval_metrics module from agents/recap-writer/evals/."""
    if _EVAL_METRICS_PATH.exists():
        spec = importlib.util.spec_from_file_location("recap_eval_metrics", _EVAL_METRICS_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules["recap_eval_metrics"] = module
        spec.loader.exec_module(module)
        return module
    return None


async def run_evaluation(agent_run_id: int, db: AsyncSession) -> AgentRun:
    """Run all eval checks for an agent run and persist results.

    Args:
        agent_run_id: ID of the AgentRun to evaluate
        db: Async database session

    Returns:
        Updated AgentRun with eval_score populated and evaluations persisted
    """
    # Load agent run with evaluations
    stmt = (
        select(AgentRun)
        .where(AgentRun.id == agent_run_id)
        .options(
            selectinload(AgentRun.steps),
            selectinload(AgentRun.evaluations),
        )
    )
    agent_run = await db.scalar(stmt)
    if agent_run is None:
        raise ValueError(f"AgentRun {agent_run_id} not found")

    if agent_run.agent_name != "recap-writer":
        raise ValueError(
            f"Evaluation is only supported for recap-writer runs, "
            f"got agent_name={agent_run.agent_name!r}"
        )

    if agent_run.output_payload is None:
        raise ValueError(
            f"AgentRun {agent_run_id} has no output_payload — cannot evaluate"
        )

    # Try to load eval_metrics module
    eval_module = _load_eval_metrics()
    if eval_module is None:
        logger.warning(
            "eval_metrics.py not found at %s — skipping evaluation", _EVAL_METRICS_PATH
        )
        return agent_run

    coverage = agent_run.output_payload
    game_data = agent_run.input_payload
    results = []

    # Run deterministic checks
    recap = coverage.get("recap", "")
    headline = coverage.get("headline", "")
    social_post = coverage.get("social_post", "")

    results.append(
        eval_module.check_score_present(
            recap,
            game_data.get("home_score"),
            game_data.get("away_score"),
        )
    )
    results.append(
        eval_module.check_teams_mentioned(
            recap,
            game_data.get("home_team"),
            game_data.get("away_team"),
        )
    )
    results.append(eval_module.check_word_count(recap))
    results.append(eval_module.check_headline_length(headline))
    results.append(eval_module.check_social_length(social_post))

    team_stats = game_data.get("team_stats", [])
    # Convert team_stats format: list of {stat, home, away} → {stat_name, home_value, away_value}
    normalized_stats = [
        {
            "stat_name": s.get("stat", s.get("stat_name", "")),
            "home_value": s.get("home", s.get("home_value", "")),
            "away_value": s.get("away", s.get("away_value", "")),
        }
        for s in team_stats
    ]
    results.append(eval_module.check_stats_cited(recap, normalized_stats))

    # Persist evaluation rows
    now = datetime.now(timezone.utc)
    for result in results:
        eval_row = AgentRunEvaluation(
            agent_run_id=agent_run.id,
            eval_type="deterministic",
            metric_name=result.metric,
            passed=result.passed,
            score=result.score,
            detail=result.detail,
            evaluated_at=now,
        )
        db.add(eval_row)

    # Compute composite score
    composite = eval_module.composite_score(results)
    agent_run.eval_score = composite

    await db.commit()

    logger.info(
        "eval completed agent_run_id=%s composite_score=%.3f",
        agent_run.id,
        composite,
    )
    return agent_run
