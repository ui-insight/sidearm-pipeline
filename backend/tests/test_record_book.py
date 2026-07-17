"""Verify evidence-backed multi-stat Record Book leaderboards."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import SourceSnapshot
from app.models.player import Player, PlayerSeason
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition

STAT_CONFIG = {
    "points": ("Points", "PTS"),
    "total_rebounds": ("Rebounds", "REB"),
    "assists": ("Assists", "A"),
}


async def seed_record_book_facts(db_session) -> None:
    program = SportProgram(
        slug="womens-basketball",
        display_name="Women's Basketball",
        sport="basketball",
        gender="women",
        season_format="academic_year",
    )
    definitions = {
        stat_key: StatDefinition(
            sport_program=program,
            stat_key=stat_key,
            display_label=label,
            entity_scope="player",
            value_type="integer",
            unit="count",
            aggregation_method="sum",
            comparison_direction="higher",
            display_format="0",
            source_field_aliases=[source_field],
            record_book_eligible=True,
            notability_eligible=True,
        )
        for stat_key, (label, source_field) in STAT_CONFIG.items()
    }
    alice = Player(display_name="Alice Adams")
    bob = Player(display_name="Bobbi Brown")
    cara = Player(display_name="Cara Cole")
    db_session.add_all([program, *definitions.values(), alice, bob, cara])
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
    game_snapshot = SourceSnapshot(
        source_system="sidearm",
        source_type="boxscore_html",
        source_url="https://govandals.com/game/fixture",
        parser_version="test-v1",
        content_hash="hash-game",
        http_status=200,
        raw_body="game fixture",
    )
    db_session.add(game_snapshot)
    await db_session.flush()

    memberships = {}
    for player, season, values in (
        (
            alice,
            "2024-25",
            {"points": "100", "total_rebounds": "50", "assists": "30"},
        ),
        (
            alice,
            "2025-26",
            {"points": "125", "total_rebounds": "75", "assists": "40"},
        ),
        (
            bob,
            "2025-26",
            {"points": "225", "total_rebounds": "160", "assists": "20"},
        ),
        (
            cara,
            "2025-26",
            {"points": "150", "total_rebounds": "120", "assists": "90"},
        ),
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
        for stat_key, value in values.items():
            db_session.add(
                PlayerSeasonStat(
                    player_season=membership,
                    stat_definition=definitions[stat_key],
                    source_snapshot=snapshots[season],
                    value=Decimal(value),
                    source_field=STAT_CONFIG[stat_key][1],
                    source_value=value,
                )
            )

    for definition in definitions.values():
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
                    known_limitations=(
                        "Public HTML fallback; source authority pending."
                    ),
                    verified_at=datetime(2026, 7, 15, tzinfo=UTC),
                )
            )

    db_session.add_all(
        [
            DataQualityIssue(
                sport_program=program,
                source_snapshot=game_snapshot,
                deduplication_key="record-book-unrelated-game-identity",
                issue_type="unresolved_identity",
                status="open",
                severity="warning",
                summary="A game row needs identity review",
                details={"season": "2025-26"},
            ),
            DataQualityIssue(
                sport_program=program,
                source_snapshot=snapshots["2024-25"],
                deduplication_key="record-book-cumulative-source-conflict",
                issue_type="source_conflict",
                status="open",
                severity="warning",
                summary="A cumulative source row needs review",
                details={"season": "2024-25"},
            ),
            DataQualityIssue(
                sport_program=program,
                player=alice,
                stat_definition=definitions["assists"],
                source_snapshot=snapshots["2025-26"],
                deduplication_key="record-book-assists-mismatch",
                issue_type="reconciliation_mismatch",
                status="in_review",
                severity="error",
                summary="Assists do not reconcile",
                details={"season": "2025-26", "stat_key": "assists"},
            ),
        ]
    )
    await db_session.commit()


async def test_career_points_leaderboard_ranks_ties_and_attaches_evidence(
    client,
    db_session,
) -> None:
    await seed_record_book_facts(db_session)

    response = await client.get(
        "/api/v1/record-book/leaders/points?scope=career&limit=10"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_name"] == "Women's Basketball"
    assert payload["stat_key"] == "points"
    assert payload["stat_label"] == "Points"
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


async def test_season_leaderboard_scopes_quality_review_to_selected_window(
    client,
    db_session,
) -> None:
    await seed_record_book_facts(db_session)

    latest = await client.get(
        "/api/v1/record-book/leaders/points?scope=season&limit=10"
    )
    earlier = await client.get(
        "/api/v1/record-book/leaders/points?scope=season&season=2024-25&limit=10"
    )

    assert latest.status_code == 200
    assert latest.json()["season"] == "2025-26"
    assert latest.json()["open_quality_issue_count"] == 0
    assert [row["player_name"] for row in latest.json()["leaders"]] == [
        "Bobbi Brown",
        "Cara Cole",
        "Alice Adams",
    ]
    assert earlier.status_code == 200
    assert earlier.json()["season"] == "2024-25"
    assert earlier.json()["open_quality_issue_count"] == 1
    assert [row["player_name"] for row in earlier.json()["leaders"]] == ["Alice Adams"]
    assert Decimal(earlier.json()["leaders"][0]["total"]) == 100
    assert earlier.json()["coverage"]["statement"] == (
        "Verified season source for 2024-25."
    )


async def test_record_book_supports_rebounds_and_assists(client, db_session) -> None:
    await seed_record_book_facts(db_session)

    rebounds = await client.get(
        "/api/v1/record-book/leaders/total_rebounds?scope=career"
    )
    assists = await client.get("/api/v1/record-book/leaders/assists?scope=career")

    assert rebounds.status_code == 200
    assert rebounds.json()["stat_label"] == "Rebounds"
    assert rebounds.json()["leaders"][0]["player_name"] == "Bobbi Brown"
    assert Decimal(rebounds.json()["leaders"][0]["total"]) == 160
    assert rebounds.json()["open_quality_issue_count"] == 1

    assert assists.status_code == 200
    assert assists.json()["stat_label"] == "Assists"
    assert [row["player_name"] for row in assists.json()["leaders"]] == [
        "Cara Cole",
        "Alice Adams",
        "Bobbi Brown",
    ]
    assert Decimal(assists.json()["leaders"][0]["total"]) == 90
    assert assists.json()["open_quality_issue_count"] == 2


async def test_record_book_rejects_unsupported_metrics(client) -> None:
    response = await client.get("/api/v1/record-book/leaders/steals")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("stat_key", "statement"),
    [
        ("points", "No verified points coverage is available yet."),
        ("total_rebounds", "No verified rebounds coverage is available yet."),
        ("assists", "No verified assists coverage is available yet."),
    ],
)
async def test_leaderboards_have_metric_specific_empty_states(
    client,
    stat_key,
    statement,
) -> None:
    response = await client.get(f"/api/v1/record-book/leaders/{stat_key}")

    assert response.status_code == 200
    assert response.json()["leaders"] == []
    assert response.json()["coverage"] == {
        "first_season": None,
        "last_season": None,
        "completeness": "unknown",
        "source_systems": [],
        "known_limitations": [],
        "verified_at": None,
        "statement": statement,
    }
