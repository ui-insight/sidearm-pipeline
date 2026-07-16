"""Tests for cumulative season facts and game-to-season reconciliation."""

from decimal import Decimal

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, SourceSnapshot
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.season_stat_import import import_cumulative_stats
from app.services.sidearm_cumulative_stats import (
    ParsedCumulativePlayer,
    ParsedCumulativeStats,
)

SOURCE_URL = "https://govandals.com/sports/womens-basketball/stats/2025-26"


def _parsed_source(*players: ParsedCumulativePlayer) -> ParsedCumulativeStats:
    return ParsedCumulativeStats(
        sport_program_slug="womens-basketball",
        season="2025-26",
        source_system="govandals_public_html",
        identity_source_system="sidearm",
        institution="University of Idaho",
        team_slug="idaho",
        source_url=SOURCE_URL,
        raw_html="<html>season facts</html>",
        players=list(players),
    )


def _player_row(
    *,
    source_player_id: str | None = "8430",
    games_played: int = 2,
    points: str = "25",
) -> ParsedCumulativePlayer:
    return ParsedCumulativePlayer(
        display_name="Hassmann, Hope",
        jersey_number="04",
        source_player_id=source_player_id,
        bio_url=(
            "https://govandals.com/sports/womens-basketball/roster/"
            f"hope-hassmann/{source_player_id}"
            if source_player_id
            else None
        ),
        games_played=games_played,
        games_started=games_played,
        stats={"points": Decimal(points)},
        source_fields={"points": "PTS"},
        source_values={"GP": str(games_played), "PTS": points},
    )


async def _seed_player_with_games(db_session, *game_points: str) -> None:
    await seed_warehouse_reference_data(db_session)
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    team = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    points = await db_session.scalar(
        select(StatDefinition).where(
            StatDefinition.sport_program_id == program.id,
            StatDefinition.stat_key == "points",
        )
    )
    assert program is not None
    assert team is not None
    assert points is not None
    player = Player(display_name="Hassmann, Hope")
    player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="8430",
            source_url=(
                "https://govandals.com/sports/womens-basketball/roster/"
                "hope-hassmann/8430"
            ),
        )
    )
    player.seasons.append(
        PlayerSeason(
            sport_program=program,
            team=team,
            season="2025-26",
            jersey_number="04",
        )
    )
    db_session.add(player)
    await db_session.flush()

    for index, value in enumerate(game_points, start=1):
        game = Game(
            source_url=f"https://govandals.com/wbb/boxscore/{index}",
            canonical_uid=f"sidearm:womens-basketball:2025-26:{index}",
            sport="womens-basketball",
            season="2025-26",
            event_status="final",
        )
        db_session.add(game)
        await db_session.flush()
        db_session.add(
            PlayerGameStat(
                game=game,
                player=player,
                team=team,
                stat_definition=points,
                value=Decimal(value),
                source_field="PTS",
                source_value=value,
            )
        )
    await db_session.commit()


async def test_import_is_idempotent_and_clean_facts_reconcile(db_session) -> None:
    await _seed_player_with_games(db_session, "10", "15")
    source = _parsed_source(_player_row())

    first = await import_cumulative_stats(db_session, source)
    second = await import_cumulative_stats(db_session, source)

    assert first.facts_written == 1
    assert first.comparisons_run == 1
    assert first.facts_matched == 1
    assert first.facts_mismatched == 0
    assert first.coverage_completeness == "complete"
    assert second.facts_matched == 1
    assert await db_session.scalar(select(func.count(PlayerSeasonStat.id))) == 1
    assert await db_session.scalar(select(func.count(SourceSnapshot.id))) == 2
    assert await db_session.scalar(select(func.count(CoverageWindow.id))) == 1
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 0
    fact = await db_session.scalar(select(PlayerSeasonStat))
    assert fact is not None
    assert fact.value == Decimal("25")
    assert fact.source_field == "PTS"
    assert fact.source_snapshot_id == second.source_snapshot_id


async def test_mismatch_issue_is_deduplicated_then_resolved(db_session) -> None:
    await _seed_player_with_games(db_session, "10", "15")

    mismatch = await import_cumulative_stats(
        db_session,
        _parsed_source(_player_row(points="26")),
    )

    assert mismatch.facts_mismatched == 1
    assert mismatch.quality_issues_created == 1
    issue = await db_session.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.issue_type == "reconciliation_mismatch"
        )
    )
    assert issue is not None
    assert issue.status == "open"
    assert issue.details["season_total"] == "26"
    assert issue.details["game_sum"] == "25.000000"
    assert issue.details["difference"] == "1.000000"

    clean = await import_cumulative_stats(
        db_session,
        _parsed_source(_player_row(points="25")),
    )

    await db_session.refresh(issue)
    assert clean.quality_issues_resolved == 1
    assert issue.status == "resolved"
    assert issue.resolved_at is not None
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 1


async def test_incomplete_game_coverage_creates_one_gap_not_false_mismatches(
    db_session,
) -> None:
    await _seed_player_with_games(db_session, "10", "15")

    result = await import_cumulative_stats(
        db_session,
        _parsed_source(_player_row(games_played=3, points="40")),
    )

    assert result.comparisons_run == 0
    assert result.facts_mismatched == 0
    assert result.coverage_gaps == 1
    assert result.coverage_completeness == "partial"
    issue = await db_session.scalar(select(DataQualityIssue))
    assert issue is not None
    assert issue.issue_type == "coverage_gap"
    assert issue.details["expected_games"] == 3
    assert issue.details["observed_games"] == 2
    coverage = await db_session.scalar(select(CoverageWindow))
    assert coverage is not None
    assert coverage.completeness == "partial"
    assert "public HTML fallback" in (coverage.known_limitations or "")

    clean = await import_cumulative_stats(
        db_session,
        _parsed_source(_player_row(games_played=2, points="25")),
    )

    await db_session.refresh(coverage)
    assert clean.coverage_completeness == "complete"
    assert clean.quality_issues_resolved == 1
    assert coverage.completeness == "complete"
    assert coverage.verified_at is not None


async def test_duplicate_and_missing_source_ids_remain_actionable(db_session) -> None:
    await _seed_player_with_games(db_session, "25")
    duplicate = _player_row(games_played=1, points="25")
    missing = _player_row(source_player_id=None, games_played=1, points="5")

    result = await import_cumulative_stats(
        db_session,
        _parsed_source(duplicate, duplicate, missing),
    )

    assert result.players_resolved == 0
    assert result.players_unresolved == 1
    assert result.source_conflicts == 1
    assert result.facts_written == 0
    issues = list(
        await db_session.scalars(
            select(DataQualityIssue).order_by(DataQualityIssue.issue_type)
        )
    )
    assert [issue.issue_type for issue in issues] == [
        "source_conflict",
        "unresolved_identity",
    ]
