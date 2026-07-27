"""Verify deterministic, policy-versioned achievement detection."""

from decimal import Decimal

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.achievement import (
    AchievementSuggestion,
    NotabilityPolicy,
    NotabilityPolicyMetric,
)
from app.models.coverage_window import CoverageWindow
from app.models.game import Game, SourceSnapshot
from app.models.player import Player
from app.models.player_game_stat import PlayerGameStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.achievement_detection import detect_achievement_suggestions


async def _seed_achievement_history(db_session):
    await seed_warehouse_reference_data(db_session)
    await db_session.flush()
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    idaho = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    points = await db_session.scalar(
        select(StatDefinition).where(
            StatDefinition.sport_program_id == program.id,
            StatDefinition.stat_key == "points",
        )
    )
    policy = await db_session.scalar(
        select(NotabilityPolicy).where(
            NotabilityPolicy.sport_program_id == program.id,
            NotabilityPolicy.active.is_(True),
        )
    )
    metric_rule = await db_session.scalar(
        select(NotabilityPolicyMetric).where(
            NotabilityPolicyMetric.notability_policy_id == policy.id,
            NotabilityPolicyMetric.stat_definition_id == points.id,
        )
    )
    assert program is not None
    assert idaho is not None
    assert points is not None
    assert policy is not None
    assert metric_rule is not None
    metric_rule.importance_weight = Decimal("1.500")
    metric_rule.thresholds = [100]

    alice = Player(display_name="Alice Adams")
    bob = Player(display_name="Bobbi Brown")
    db_session.add_all([alice, bob])
    await db_session.flush()

    games = []
    for index, (game_date, season) in enumerate(
        (
            ("2024-02-01", "2023-24"),
            ("2025-11-01", "2025-26"),
            ("2025-11-15", "2025-26"),
            ("2025-12-01", "2025-26"),
        ),
        start=1,
    ):
        game = Game(
            source_url=f"https://govandals.com/boxscore/{index}",
            canonical_uid=f"sidearm:womens-basketball:{season}:{index}",
            sport="womens-basketball",
            season=season,
            game_date=game_date,
            event_status="final",
            exhibition=False,
        )
        games.append(game)
        db_session.add(game)
    await db_session.flush()

    current_snapshot = SourceSnapshot(
        game=games[3],
        source_system="sidearm",
        source_type="boxscore_html",
        source_url=games[3].source_url,
        parser_version="test-v1",
        content_hash="current-game-hash",
        http_status=200,
        raw_body="fixture",
    )
    db_session.add(current_snapshot)
    await db_session.flush()
    for game, player, value in (
        (games[0], alice, 20),
        (games[1], alice, 40),
        (games[2], bob, 60),
        (games[3], alice, 50),
    ):
        db_session.add(
            PlayerGameStat(
                game=game,
                player=player,
                team=idaho,
                stat_definition=points,
                source_snapshot=(current_snapshot if game is games[3] else None),
                value=Decimal(value),
                source_field="PTS",
                source_value=str(value),
            )
        )
    coverage = CoverageWindow(
        sport_program=program,
        grain="game",
        source_system="sidearm_html",
        first_season="2023-24",
        last_season="2025-26",
        completeness="partial",
        known_limitations="Earlier seasons are not available.",
    )
    db_session.add(coverage)
    await db_session.commit()
    return games[3], alice, points, policy, coverage, current_snapshot


async def test_detects_all_required_achievement_types_with_policy_scores(
    db_session,
) -> None:
    game, alice, points, policy, coverage, snapshot = await _seed_achievement_history(
        db_session
    )

    result = await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    suggestions = list(
        await db_session.scalars(
            select(AchievementSuggestion)
            .where(AchievementSuggestion.game_id == game.id)
            .order_by(AchievementSuggestion.achievement_type)
        )
    )
    by_type = {row.achievement_type: row for row in suggestions}
    assert result.suggestions_written == 4
    assert result.players_evaluated == 1
    assert result.metrics_evaluated == 1
    assert result.policy_version == policy.version
    assert set(by_type) == {
        "all_time_top_n",
        "career_high",
        "season_high",
        "threshold_crossing",
    }

    assert by_type["career_high"].computed_value == 50
    assert by_type["career_high"].comparison_value == 40
    assert by_type["career_high"].notability_score == Decimal("4.500")
    assert by_type["season_high"].comparison_value == 40
    assert by_type["season_high"].notability_score == Decimal("3.000")

    threshold = by_type["threshold_crossing"]
    assert threshold.computed_value == 110
    assert threshold.comparison_value == 100
    assert threshold.context["career_total_before"] == "60.000000"
    assert threshold.context["career_total_after"] == "110.000000"
    assert threshold.notability_score == Decimal("6.000")

    top_n = by_type["all_time_top_n"]
    assert top_n.rank == 2
    assert top_n.context["tied_at_rank"] == 1
    assert top_n.context["claim_scope"] == "since 2023-24"
    assert top_n.notability_score == Decimal("7.500")

    assert all(row.player_id == alice.id for row in suggestions)
    assert all(row.stat_definition_id == points.id for row in suggestions)
    assert all(row.notability_policy_id == policy.id for row in suggestions)
    assert all(row.coverage_window_id == coverage.id for row in suggestions)
    assert all(row.source_snapshot_id == snapshot.id for row in suggestions)
    assert all(row.state == "pending" for row in suggestions)
    assert all(row.phrasing is None for row in suggestions)
    assert all(
        row.coverage_context["known_limitations"]
        == "Earlier seasons are not available."
        for row in suggestions
    )


async def test_detection_replaces_suggestions_idempotently(db_session) -> None:
    game, *_ = await _seed_achievement_history(db_session)

    first = await detect_achievement_suggestions(db_session, game=game)
    second = await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    assert first.suggestions_written == 4
    assert second.suggestions_written == 4
    assert (
        await db_session.scalar(
            select(func.count(AchievementSuggestion.id)).where(
                AchievementSuggestion.game_id == game.id
            )
        )
        == 4
    )


async def test_detection_preserves_editorial_verdict_on_reingest(db_session) -> None:
    game, *_ = await _seed_achievement_history(db_session)
    await detect_achievement_suggestions(db_session, game=game)
    suggestion = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == game.id,
            AchievementSuggestion.achievement_type == "career_high",
        )
    )
    suggestion.state = "rejected"
    suggestion.reviewed_by = "sid-reviewer"
    suggestion.phrasing = "Alice Adams set a verified career high with 50 points."
    await db_session.commit()

    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()
    preserved = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == game.id,
            AchievementSuggestion.achievement_type == "career_high",
        )
    )

    assert preserved.state == "rejected"
    assert preserved.reviewed_by == "sid-reviewer"
    assert preserved.phrasing == (
        "Alice Adams set a verified career high with 50 points."
    )


async def test_detection_invalidates_editorial_verdict_when_fact_changes(
    db_session,
) -> None:
    game, *_ = await _seed_achievement_history(db_session)
    await detect_achievement_suggestions(db_session, game=game)
    suggestion = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == game.id,
            AchievementSuggestion.achievement_type == "career_high",
        )
    )
    suggestion.state = "approved"
    suggestion.reviewed_by = "sid-reviewer"
    suggestion.phrasing = "Alice Adams set a verified career high with 50 points."
    current_fact = await db_session.scalar(
        select(PlayerGameStat).where(PlayerGameStat.game_id == game.id)
    )
    current_fact.value = Decimal("55")
    await db_session.commit()

    await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()
    refreshed = await db_session.scalar(
        select(AchievementSuggestion).where(
            AchievementSuggestion.game_id == game.id,
            AchievementSuggestion.achievement_type == "career_high",
        )
    )

    assert refreshed.computed_value == 55
    assert refreshed.state == "pending"
    assert refreshed.reviewed_by is None
    assert refreshed.phrasing is None


async def test_detection_skips_nonfinal_and_exhibition_games(db_session) -> None:
    game, *_ = await _seed_achievement_history(db_session)
    await detect_achievement_suggestions(db_session, game=game)
    game.exhibition = True

    result = await detect_achievement_suggestions(db_session, game=game)
    await db_session.commit()

    assert result.suggestions_written == 0
    assert (
        await db_session.scalar(
            select(func.count(AchievementSuggestion.id)).where(
                AchievementSuggestion.game_id == game.id
            )
        )
        == 0
    )
