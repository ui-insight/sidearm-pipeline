"""Verify evidence-backed Record Book points leaderboards."""

from datetime import UTC, datetime
from decimal import Decimal

from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import SourceSnapshot
from app.models.player import Player, PlayerSeason
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition


async def seed_points_facts(db_session) -> None:
    program = SportProgram(
        slug="womens-basketball",
        display_name="Women's Basketball",
        sport="basketball",
        gender="women",
        season_format="academic_year",
    )
    definition = StatDefinition(
        sport_program=program,
        stat_key="points",
        display_label="Points",
        entity_scope="player",
        value_type="integer",
        unit="count",
        aggregation_method="sum",
        comparison_direction="higher",
        display_format="0",
        source_field_aliases=["PTS"],
        record_book_eligible=True,
        notability_eligible=True,
    )
    alice = Player(display_name="Alice Adams")
    bob = Player(display_name="Bobbi Brown")
    cara = Player(display_name="Cara Cole")
    db_session.add_all([program, definition, alice, bob, cara])
    await db_session.flush()

    snapshots = {}
    for season in ("2024-25", "2025-26"):
        snapshot = SourceSnapshot(
            source_system="sidearm",
            source_type="cumulative_stats_html",
            source_url=f"https://govandals.com/stats/wbb/{season}",
            parser_version="test-v1",
            content_hash=f"hash-{season}",
            http_status=200,
            raw_body=f"fixture {season}",
        )
        snapshots[season] = snapshot
        db_session.add(snapshot)
    await db_session.flush()

    memberships = {}
    for player, season, points in (
        (alice, "2024-25", "100"),
        (alice, "2025-26", "125"),
        (bob, "2025-26", "225"),
        (cara, "2025-26", "150"),
    ):
        membership = PlayerSeason(
            player=player,
            sport_program=program,
            season=season,
            source_snapshot=snapshots[season],
        )
        db_session.add(membership)
        await db_session.flush()
        memberships[(player.id, season)] = membership
        db_session.add(
            PlayerSeasonStat(
                player_season=membership,
                stat_definition=definition,
                source_snapshot=snapshots[season],
                value=Decimal(points),
                source_field="PTS",
                source_value=points,
            )
        )

    for season in ("2024-25", "2025-26"):
        db_session.add(
            CoverageWindow(
                sport_program=program,
                stat_definition=definition,
                grain="season",
                source_system="sidearm",
                first_season=season,
                last_season=season,
                completeness="complete",
                known_limitations="Public HTML fallback; source authority pending.",
                verified_at=datetime(2026, 7, 15, tzinfo=UTC),
            )
        )
    db_session.add(
        DataQualityIssue(
            sport_program=program,
            deduplication_key="record-book-test-open-identity",
            issue_type="unresolved_identity",
            status="open",
            severity="warning",
            summary="One source row still needs identity review",
            details={"season": "2025-26"},
        )
    )
    await db_session.commit()


async def test_career_points_leaderboard_ranks_ties_and_attaches_evidence(
    client,
    db_session,
) -> None:
    await seed_points_facts(db_session)

    response = await client.get(
        "/api/v1/record-book/leaders/points?scope=career&limit=10"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_name"] == "Women's Basketball"
    assert payload["scope"] == "career"
    assert payload["available_seasons"] == ["2025-26", "2024-25"]
    assert payload["total_players"] == 3
    assert payload["open_quality_issue_count"] == 1
    assert payload["coverage"]["completeness"] == "complete"
    assert payload["coverage"]["first_season"] == "2024-25"
    assert payload["coverage"]["last_season"] == "2025-26"
    assert "not all-time history" in payload["coverage"]["statement"]
    assert [leader["rank"] for leader in payload["leaders"]] == [1, 1, 3]
    assert [leader["player_name"] for leader in payload["leaders"]] == [
        "Alice Adams",
        "Bobbi Brown",
        "Cara Cole",
    ]
    alice = payload["leaders"][0]
    assert Decimal(alice["total"]) == 225
    assert alice["seasons_count"] == 2
    assert [row["season"] for row in alice["season_breakdown"]] == [
        "2025-26",
        "2024-25",
    ]
    assert alice["season_breakdown"][0]["source_url"].endswith("2025-26")

    career_with_ignored_season = await client.get(
        "/api/v1/record-book/leaders/points?scope=career&season=2024-25&limit=10"
    )
    assert career_with_ignored_season.status_code == 200
    assert career_with_ignored_season.json()["season"] is None
    assert Decimal(career_with_ignored_season.json()["leaders"][0]["total"]) == 225


async def test_season_points_leaderboard_defaults_to_latest_or_filters_explicitly(
    client,
    db_session,
) -> None:
    await seed_points_facts(db_session)

    latest = await client.get(
        "/api/v1/record-book/leaders/points?scope=season&limit=10"
    )
    earlier = await client.get(
        "/api/v1/record-book/leaders/points?scope=season&season=2024-25&limit=10"
    )

    assert latest.status_code == 200
    assert latest.json()["season"] == "2025-26"
    assert [row["player_name"] for row in latest.json()["leaders"]] == [
        "Bobbi Brown",
        "Cara Cole",
        "Alice Adams",
    ]
    assert earlier.status_code == 200
    assert earlier.json()["season"] == "2024-25"
    assert [row["player_name"] for row in earlier.json()["leaders"]] == ["Alice Adams"]
    assert Decimal(earlier.json()["leaders"][0]["total"]) == 100
    assert earlier.json()["coverage"]["statement"] == (
        "Verified season source for 2024-25."
    )


async def test_points_leaderboard_has_an_honest_empty_state(client) -> None:
    response = await client.get("/api/v1/record-book/leaders/points")

    assert response.status_code == 200
    assert response.json()["leaders"] == []
    assert response.json()["coverage"] == {
        "first_season": None,
        "last_season": None,
        "completeness": "unknown",
        "source_systems": [],
        "known_limitations": [],
        "verified_at": None,
        "statement": "No verified points coverage is available yet.",
    }
