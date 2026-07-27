"""Detect explainable achievement candidates from verified warehouse facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import IDAHO_TEAM_SLUG, WBB_PROGRAM_SLUG
from app.models.achievement import (
    AchievementSuggestion,
    NotabilityPolicy,
    NotabilityPolicyMetric,
)
from app.models.coverage_window import CoverageWindow
from app.models.game import Game
from app.models.player_game_stat import PlayerGameStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team

SUPPORTED_ACHIEVEMENT_TYPES = (
    "career_high",
    "season_high",
    "threshold_crossing",
    "all_time_top_n",
)


@dataclass(frozen=True)
class AchievementDetectionResult:
    """Counts produced by one deterministic detection pass."""

    suggestions_written: int
    players_evaluated: int
    metrics_evaluated: int
    policy_version: int | None


@dataclass(frozen=True)
class _FeedbackSummary:
    """Prior SID verdict counts for one metric and achievement pattern."""

    approved: int = 0
    rejected: int = 0

    @property
    def multiplier(self) -> Decimal:
        """Return a conservative Bayesian down-weight, never an up-weight."""
        reviewed = self.approved + self.rejected
        if reviewed == 0:
            return Decimal("1")
        return (Decimal(self.approved + 2) / Decimal(reviewed + 2)).quantize(
            Decimal("0.001")
        )


async def detect_achievement_suggestions(
    db: AsyncSession,
    *,
    game: Game,
) -> AchievementDetectionResult:
    """Replace deterministic achievement suggestions for one finalized WBB game."""
    if game.id is None:
        raise ValueError("Game must be flushed before achievement detection")

    existing_editorial = {
        suggestion.suggestion_key: {
            "facts": (
                suggestion.computed_value,
                suggestion.comparison_value,
                suggestion.rank,
                suggestion.coverage_context,
            ),
            "fields": {
                "phrasing": suggestion.phrasing,
                "ai_rank": suggestion.ai_rank,
                "ai_model": suggestion.ai_model,
                "ai_prompt_version": suggestion.ai_prompt_version,
                "ai_output_hash": suggestion.ai_output_hash,
                "ai_ranked_at": suggestion.ai_ranked_at,
                "state": suggestion.state,
                "reviewed_at": suggestion.reviewed_at,
                "reviewed_by": suggestion.reviewed_by,
                "reviewed_fact_hash": suggestion.reviewed_fact_hash,
            },
        }
        for suggestion in await db.scalars(
            select(AchievementSuggestion).where(
                AchievementSuggestion.game_id == game.id
            )
        )
    }
    await db.execute(
        delete(AchievementSuggestion).where(AchievementSuggestion.game_id == game.id)
    )
    if (
        game.sport != WBB_PROGRAM_SLUG
        or game.event_status != "final"
        or game.exhibition
    ):
        return AchievementDetectionResult(0, 0, 0, None)

    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    idaho = await db.scalar(select(Team).where(Team.slug == IDAHO_TEAM_SLUG))
    if program is None or idaho is None:
        raise ValueError("Women's basketball warehouse reference data is missing")

    policy = await db.scalar(
        select(NotabilityPolicy)
        .where(
            NotabilityPolicy.sport_program_id == program.id,
            NotabilityPolicy.active.is_(True),
        )
        .order_by(NotabilityPolicy.version.desc())
        .limit(1)
    )
    if policy is None:
        return AchievementDetectionResult(0, 0, 0, None)

    current_rows = (
        await db.execute(
            select(PlayerGameStat, StatDefinition, NotabilityPolicyMetric)
            .join(
                StatDefinition,
                StatDefinition.id == PlayerGameStat.stat_definition_id,
            )
            .join(
                NotabilityPolicyMetric,
                and_(
                    NotabilityPolicyMetric.stat_definition_id == StatDefinition.id,
                    NotabilityPolicyMetric.notability_policy_id == policy.id,
                ),
            )
            .where(
                PlayerGameStat.game_id == game.id,
                PlayerGameStat.team_id == idaho.id,
                StatDefinition.notability_eligible.is_(True),
                StatDefinition.comparison_direction == "higher",
                NotabilityPolicyMetric.suppressed.is_(False),
                NotabilityPolicyMetric.importance_weight > 0,
            )
            .order_by(PlayerGameStat.player_id, StatDefinition.stat_key)
        )
    ).all()

    players: set[int] = set()
    metrics: set[int] = set()
    suggestions: list[AchievementSuggestion] = []
    feedback = await _feedback_by_pattern(db, policy_id=policy.id, game_id=game.id)
    prior_game = _prior_game_condition(game)
    for fact, definition, metric_rule in current_rows:
        players.add(fact.player_id)
        metrics.add(definition.id)
        history = await _history_context(
            db,
            game=game,
            fact=fact,
            prior_game=prior_game,
            top_n=policy.top_n,
        )
        coverage = await _coverage_window(
            db,
            program_id=program.id,
            definition_id=definition.id,
            season=game.season,
        )
        coverage_context = _coverage_context(coverage, game.season)
        detected = _suggestions_for_fact(
            game=game,
            fact=fact,
            definition=definition,
            metric_rule=metric_rule,
            policy=policy,
            history=history,
            coverage=coverage,
            coverage_context=coverage_context,
            feedback=feedback,
        )
        for suggestion in detected:
            editorial = existing_editorial.get(suggestion.suggestion_key)
            current_facts = (
                suggestion.computed_value,
                suggestion.comparison_value,
                suggestion.rank,
                suggestion.coverage_context,
            )
            if editorial is not None and editorial["facts"] == current_facts:
                for field, value in editorial["fields"].items():
                    setattr(suggestion, field, value)
        suggestions.extend(detected)

    db.add_all(suggestions)
    await db.flush()
    return AchievementDetectionResult(
        suggestions_written=len(suggestions),
        players_evaluated=len(players),
        metrics_evaluated=len(metrics),
        policy_version=policy.version,
    )


@dataclass(frozen=True)
class _HistoryContext:
    career_high: Decimal | None
    season_high: Decimal | None
    career_total_before: Decimal
    program_rank: int
    tied_at_rank: int


async def _feedback_by_pattern(
    db: AsyncSession,
    *,
    policy_id: int,
    game_id: int,
) -> dict[tuple[int, str], _FeedbackSummary]:
    """Aggregate earlier SID verdicts for deterministic notability tuning."""
    rows = (
        await db.execute(
            select(
                AchievementSuggestion.stat_definition_id,
                AchievementSuggestion.achievement_type,
                AchievementSuggestion.state,
                func.count(AchievementSuggestion.id),
            )
            .where(
                AchievementSuggestion.notability_policy_id == policy_id,
                AchievementSuggestion.game_id != game_id,
                AchievementSuggestion.state.in_(("approved", "rejected")),
            )
            .group_by(
                AchievementSuggestion.stat_definition_id,
                AchievementSuggestion.achievement_type,
                AchievementSuggestion.state,
            )
        )
    ).all()
    counts: dict[tuple[int, str], dict[str, int]] = {}
    for definition_id, achievement_type, state, count in rows:
        pattern = counts.setdefault((definition_id, achievement_type), {})
        pattern[state] = int(count)
    return {
        key: _FeedbackSummary(
            approved=values.get("approved", 0),
            rejected=values.get("rejected", 0),
        )
        for key, values in counts.items()
    }


async def _history_context(
    db: AsyncSession,
    *,
    game: Game,
    fact: PlayerGameStat,
    prior_game,
    top_n: int,
) -> _HistoryContext:
    prior_base = (
        select(PlayerGameStat.value)
        .join(Game, Game.id == PlayerGameStat.game_id)
        .where(
            PlayerGameStat.player_id == fact.player_id,
            PlayerGameStat.stat_definition_id == fact.stat_definition_id,
            PlayerGameStat.team_id == fact.team_id,
            PlayerGameStat.game_id != game.id,
            Game.event_status == "final",
            Game.exhibition.is_(False),
            prior_game,
        )
    )
    career_high = await db.scalar(select(func.max(prior_base.subquery().c.value)))
    season_high = await db.scalar(
        select(func.max(PlayerGameStat.value))
        .join(Game, Game.id == PlayerGameStat.game_id)
        .where(
            PlayerGameStat.player_id == fact.player_id,
            PlayerGameStat.stat_definition_id == fact.stat_definition_id,
            PlayerGameStat.team_id == fact.team_id,
            PlayerGameStat.game_id != game.id,
            Game.event_status == "final",
            Game.exhibition.is_(False),
            Game.season == game.season,
            prior_game,
        )
    )
    career_total = await db.scalar(select(func.sum(prior_base.subquery().c.value)))
    eligible_history = or_(PlayerGameStat.game_id == game.id, prior_game)
    better_count = await db.scalar(
        select(func.count(PlayerGameStat.id))
        .join(Game, Game.id == PlayerGameStat.game_id)
        .where(
            PlayerGameStat.stat_definition_id == fact.stat_definition_id,
            PlayerGameStat.team_id == fact.team_id,
            Game.sport == WBB_PROGRAM_SLUG,
            Game.event_status == "final",
            Game.exhibition.is_(False),
            eligible_history,
            PlayerGameStat.value > fact.value,
        )
    )
    rank = int(better_count or 0) + 1
    tied_count = 1
    if rank <= top_n:
        tied_count = int(
            await db.scalar(
                select(func.count(PlayerGameStat.id))
                .join(Game, Game.id == PlayerGameStat.game_id)
                .where(
                    PlayerGameStat.stat_definition_id == fact.stat_definition_id,
                    PlayerGameStat.team_id == fact.team_id,
                    Game.sport == WBB_PROGRAM_SLUG,
                    Game.event_status == "final",
                    Game.exhibition.is_(False),
                    eligible_history,
                    PlayerGameStat.value == fact.value,
                )
            )
            or 1
        )
    return _HistoryContext(
        career_high=(Decimal(career_high) if career_high is not None else None),
        season_high=(Decimal(season_high) if season_high is not None else None),
        career_total_before=Decimal(career_total or 0),
        program_rank=rank,
        tied_at_rank=tied_count,
    )


def _suggestions_for_fact(
    *,
    game: Game,
    fact: PlayerGameStat,
    definition: StatDefinition,
    metric_rule: NotabilityPolicyMetric,
    policy: NotabilityPolicy,
    history: _HistoryContext,
    coverage: CoverageWindow | None,
    coverage_context: dict,
    feedback: dict[tuple[int, str], _FeedbackSummary],
) -> list[AchievementSuggestion]:
    suggestions: list[AchievementSuggestion] = []
    if history.career_high is not None and fact.value > history.career_high:
        suggestions.append(
            _suggestion(
                game=game,
                fact=fact,
                definition=definition,
                metric_rule=metric_rule,
                policy=policy,
                coverage=coverage,
                coverage_context=coverage_context,
                achievement_type="career_high",
                scope="career",
                computed_value=fact.value,
                comparison_value=history.career_high,
                context={"previous_high": str(history.career_high)},
                feedback=feedback,
            )
        )
    if history.season_high is not None and fact.value > history.season_high:
        suggestions.append(
            _suggestion(
                game=game,
                fact=fact,
                definition=definition,
                metric_rule=metric_rule,
                policy=policy,
                coverage=coverage,
                coverage_context=coverage_context,
                achievement_type="season_high",
                scope="season",
                computed_value=fact.value,
                comparison_value=history.season_high,
                context={
                    "season": game.season,
                    "previous_high": str(history.season_high),
                },
                feedback=feedback,
            )
        )

    career_total_after = history.career_total_before + fact.value
    for threshold in sorted(Decimal(str(value)) for value in metric_rule.thresholds):
        if history.career_total_before < threshold <= career_total_after:
            suggestions.append(
                _suggestion(
                    game=game,
                    fact=fact,
                    definition=definition,
                    metric_rule=metric_rule,
                    policy=policy,
                    coverage=coverage,
                    coverage_context=coverage_context,
                    achievement_type="threshold_crossing",
                    scope="career",
                    computed_value=career_total_after,
                    comparison_value=threshold,
                    key_suffix=str(threshold),
                    context={
                        "threshold": str(threshold),
                        "career_total_before": str(history.career_total_before),
                        "career_total_after": str(career_total_after),
                    },
                    feedback=feedback,
                )
            )

    if history.program_rank <= policy.top_n:
        suggestions.append(
            _suggestion(
                game=game,
                fact=fact,
                definition=definition,
                metric_rule=metric_rule,
                policy=policy,
                coverage=coverage,
                coverage_context=coverage_context,
                achievement_type="all_time_top_n",
                scope="program",
                computed_value=fact.value,
                comparison_value=None,
                rank=history.program_rank,
                context={
                    "rank": history.program_rank,
                    "top_n": policy.top_n,
                    "tied_at_rank": history.tied_at_rank,
                    "claim_scope": coverage_context["claim_scope"],
                },
                feedback=feedback,
            )
        )
    return suggestions


def _suggestion(
    *,
    game: Game,
    fact: PlayerGameStat,
    definition: StatDefinition,
    metric_rule: NotabilityPolicyMetric,
    policy: NotabilityPolicy,
    coverage: CoverageWindow | None,
    coverage_context: dict,
    achievement_type: str,
    scope: str,
    computed_value: Decimal,
    comparison_value: Decimal | None,
    context: dict,
    feedback: dict[tuple[int, str], _FeedbackSummary],
    key_suffix: str | None = None,
    rank: int | None = None,
) -> AchievementSuggestion:
    scope_weight = Decimal(str(policy.scope_weights[achievement_type]))
    base_score = scope_weight * Decimal(metric_rule.importance_weight)
    feedback_summary = feedback.get(
        (definition.id, achievement_type), _FeedbackSummary()
    )
    score = base_score * feedback_summary.multiplier
    key_parts = [achievement_type, str(fact.player_id), definition.stat_key]
    if key_suffix is not None:
        key_parts.append(key_suffix)
    return AchievementSuggestion(
        game_id=game.id,
        player_id=fact.player_id,
        stat_definition_id=definition.id,
        notability_policy_id=policy.id,
        coverage_window_id=coverage.id if coverage else None,
        source_snapshot_id=fact.source_snapshot_id,
        suggestion_key=":".join(key_parts),
        achievement_type=achievement_type,
        scope=scope,
        computed_value=computed_value,
        comparison_value=comparison_value,
        rank=rank,
        notability_score=score,
        context={
            "stat_key": definition.stat_key,
            "stat_label": definition.display_label,
            "game_value": str(fact.value),
            "scope_weight": str(scope_weight),
            "importance_weight": str(metric_rule.importance_weight),
            "base_notability_score": str(base_score),
            "feedback_multiplier": str(feedback_summary.multiplier),
            "prior_approved": feedback_summary.approved,
            "prior_rejected": feedback_summary.rejected,
            "policy_version": policy.version,
            **context,
        },
        coverage_context=coverage_context,
        state="pending",
    )


async def _coverage_window(
    db: AsyncSession,
    *,
    program_id: int,
    definition_id: int,
    season: str | None,
) -> CoverageWindow | None:
    statement = select(CoverageWindow).where(
        CoverageWindow.sport_program_id == program_id,
        CoverageWindow.grain == "game",
        or_(
            CoverageWindow.stat_definition_id == definition_id,
            CoverageWindow.stat_definition_id.is_(None),
        ),
    )
    if season is not None:
        statement = statement.where(
            or_(
                CoverageWindow.first_season.is_(None),
                CoverageWindow.first_season <= season,
            ),
            or_(
                CoverageWindow.last_season.is_(None),
                CoverageWindow.last_season >= season,
            ),
        )
    return await db.scalar(
        statement.order_by(
            case((CoverageWindow.stat_definition_id == definition_id, 0), else_=1),
            case((CoverageWindow.completeness == "complete", 0), else_=1),
            CoverageWindow.verified_at.desc(),
            CoverageWindow.id.desc(),
        ).limit(1)
    )


def _coverage_context(
    coverage: CoverageWindow | None,
    season: str | None,
) -> dict:
    if coverage is None:
        return {
            "coverage_window_id": None,
            "grain": "game",
            "first_season": season,
            "last_season": season,
            "completeness": "unknown",
            "known_limitations": "No verified game-grain Coverage Window.",
            "claim_scope": "in available warehouse history",
        }
    all_time = coverage.completeness == "complete" and coverage.first_season is None
    first_season = coverage.first_season
    claim_scope = (
        "all-time"
        if all_time
        else (
            f"since {first_season}"
            if first_season is not None
            else "in available warehouse history"
        )
    )
    return {
        "coverage_window_id": coverage.id,
        "grain": coverage.grain,
        "first_season": first_season,
        "last_season": coverage.last_season,
        "completeness": coverage.completeness,
        "known_limitations": coverage.known_limitations,
        "claim_scope": claim_scope,
    }


def _prior_game_condition(game: Game):
    if game.game_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", game.game_date):
        is_iso_date = and_(
            func.length(Game.game_date) == 10,
            func.substr(Game.game_date, 5, 1) == "-",
            func.substr(Game.game_date, 8, 1) == "-",
        )
        return or_(
            and_(is_iso_date, Game.game_date < game.game_date),
            and_(
                is_iso_date,
                Game.game_date == game.game_date,
                Game.id < game.id,
            ),
            and_(~is_iso_date, Game.id < game.id),
        )
    return Game.id < game.id
