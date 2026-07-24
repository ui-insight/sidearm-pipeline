"""Verify the typed, evidence-backed semantic query catalog."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, SourceSnapshot
from app.models.player import Player, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team


async def seed_semantic_query_facts(db_session) -> dict[str, int]:
    """Create two seasons plus final, conference, and exhibition game facts."""
    program = SportProgram(
        slug="womens-basketball",
        display_name="Women's Basketball",
        sport="basketball",
        gender="women",
        season_format="academic_year",
    )
    idaho = Team(
        slug="idaho",
        canonical_name="Idaho",
        short_name="Idaho",
        institution="University of Idaho",
        is_idaho=True,
    )
    points = StatDefinition(
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
    fouls = StatDefinition(
        sport_program=program,
        stat_key="personal_fouls",
        display_label="Personal Fouls",
        entity_scope="player",
        value_type="integer",
        unit="count",
        aggregation_method="sum",
        comparison_direction="lower",
        display_format="0",
        source_field_aliases=["PF"],
        record_book_eligible=False,
        notability_eligible=False,
    )
    alice = Player(display_name="Alice Adams")
    bob = Player(display_name="Bobbi Brown")
    db_session.add_all([program, idaho, points, fouls, alice, bob])
    await db_session.flush()

    alice_2024 = PlayerSeason(
        player=alice,
        sport_program=program,
        team=idaho,
        season="2024-25",
    )
    alice_2025 = PlayerSeason(
        player=alice,
        sport_program=program,
        team=idaho,
        season="2025-26",
    )
    bob_2025 = PlayerSeason(
        player=bob,
        sport_program=program,
        team=idaho,
        season="2025-26",
    )
    db_session.add_all([alice_2024, alice_2025, bob_2025])

    games = [
        Game(
            source_url="https://govandals.com/game/1",
            canonical_uid="semantic:game:1",
            sport=program.slug,
            season="2025-26",
            game_date="2026-01-02",
            event_status="final",
            home_team="Idaho",
            away_team="Montana",
            home_score=80,
            away_score=70,
            home_away_neutral="home",
            conference_event=True,
            exhibition=False,
        ),
        Game(
            source_url="https://govandals.com/game/2",
            canonical_uid="semantic:game:2",
            sport=program.slug,
            season="2025-26",
            game_date="2026-01-09",
            event_status="final",
            home_team="Montana State",
            away_team="Idaho",
            home_score=60,
            away_score=65,
            home_away_neutral="away",
            conference_event=True,
            exhibition=False,
        ),
        Game(
            source_url="https://govandals.com/game/3",
            canonical_uid="semantic:game:3",
            sport=program.slug,
            season="2025-26",
            game_date="2026-01-16",
            event_status="final",
            home_team="Idaho",
            away_team="Washington State",
            home_score=55,
            away_score=60,
            home_away_neutral="home",
            conference_event=False,
            exhibition=False,
        ),
        Game(
            source_url="https://govandals.com/game/exhibition",
            canonical_uid="semantic:game:exhibition",
            sport=program.slug,
            season="2025-26",
            game_date="2025-11-01",
            event_status="final",
            home_team="Idaho",
            away_team="Exhibition College",
            home_score=99,
            away_score=40,
            home_away_neutral="home",
            conference_event=False,
            exhibition=True,
        ),
    ]
    db_session.add_all(games)
    await db_session.flush()

    season_snapshots = {}
    for season in ("2024-25", "2025-26"):
        snapshot = SourceSnapshot(
            source_system="sidearm",
            source_type="cumulative_stats_html",
            source_url=f"https://govandals.com/stats/wbb/{season}",
            parser_version="semantic-test-v1",
            content_hash=f"semantic-season-{season}",
            http_status=200,
            raw_body=f"season fixture {season}",
        )
        season_snapshots[season] = snapshot
        db_session.add(snapshot)
    game_snapshots = []
    for game in games:
        snapshot = SourceSnapshot(
            game=game,
            source_system="sidearm",
            source_type="boxscore_html",
            source_url=game.source_url,
            parser_version="semantic-test-v1",
            content_hash=f"semantic-game-{game.id}",
            http_status=200,
            raw_body=f"game fixture {game.id}",
        )
        game_snapshots.append(snapshot)
        db_session.add(snapshot)
    await db_session.flush()

    db_session.add_all(
        [
            PlayerSeasonStat(
                player_season=alice_2024,
                stat_definition=points,
                source_snapshot=season_snapshots["2024-25"],
                value=Decimal("100"),
                source_field="PTS",
                source_value="100",
            ),
            PlayerSeasonStat(
                player_season=alice_2025,
                stat_definition=points,
                source_snapshot=season_snapshots["2025-26"],
                value=Decimal("150"),
                source_field="PTS",
                source_value="150",
            ),
            PlayerSeasonStat(
                player_season=bob_2025,
                stat_definition=points,
                source_snapshot=season_snapshots["2025-26"],
                value=Decimal("200"),
                source_field="PTS",
                source_value="200",
            ),
        ]
    )
    for game, snapshot, value in zip(
        games,
        game_snapshots,
        ("20", "15", "10", "99"),
        strict=True,
    ):
        db_session.add(
            PlayerGameStat(
                game=game,
                player=alice,
                team=idaho,
                stat_definition=points,
                source_snapshot=snapshot,
                value=Decimal(value),
                source_field="PTS",
                source_value=value,
            )
        )
    for game, snapshot, value in zip(
        games[:3],
        game_snapshots[:3],
        ("12", "18", "14"),
        strict=True,
    ):
        db_session.add(
            PlayerGameStat(
                game=game,
                player=bob,
                team=idaho,
                stat_definition=points,
                source_snapshot=snapshot,
                value=Decimal(value),
                source_field="PTS",
                source_value=value,
            )
        )

    verified_at = datetime(2026, 7, 17, tzinfo=UTC)
    db_session.add_all(
        [
            CoverageWindow(
                sport_program=program,
                stat_definition=points,
                grain="season",
                source_system="sidearm",
                first_season="2024-25",
                last_season="2025-26",
                completeness="complete",
                verified_at=verified_at,
            ),
            CoverageWindow(
                sport_program=program,
                stat_definition=points,
                grain="game",
                source_system="sidearm",
                first_season="2025-26",
                last_season="2025-26",
                completeness="complete",
                verified_at=verified_at,
            ),
            CoverageWindow(
                sport_program=program,
                grain="game",
                source_system="sidearm",
                first_season="2025-26",
                last_season="2025-26",
                completeness="complete",
                verified_at=verified_at,
            ),
            DataQualityIssue(
                sport_program=program,
                game=games[1],
                player=alice,
                stat_definition=points,
                source_snapshot=game_snapshots[1],
                deduplication_key="semantic-query-points-review",
                issue_type="reconciliation_mismatch",
                status="open",
                severity="warning",
                summary="Fixture points need review",
                details={"season": "2025-26", "stat_key": "points"},
            ),
        ]
    )
    await db_session.commit()
    return {
        "alice_id": alice.id,
        "bob_id": bob.id,
    }


async def test_semantic_catalog_exposes_stable_typed_queries(client) -> None:
    response = await client.get("/api/v1/semantic-queries/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_slug"] == "womens-basketball"
    assert [query["query_id"] for query in payload["queries"]] == [
        "team_season_record",
        "stat_leaders",
        "opponent_stat_leaders",
        "player_career_total",
        "player_game_split",
    ]
    opponent_leaders = payload["queries"][2]
    opponent_properties = opponent_leaders["parameter_schema"]["properties"]
    assert opponent_properties["season"]["pattern"] == r"^\d{4}-\d{2}$"
    assert opponent_properties["opponent"]["maxLength"] == 255
    assert "conference_scope" in opponent_properties
    split = payload["queries"][4]
    properties = split["parameter_schema"]["properties"]
    assert properties["player_id"]["exclusiveMinimum"] == 0
    assert properties["season"]["anyOf"][0]["pattern"] == r"^\d{4}-\d{2}$"
    assert "conference_scope" in properties
    assert "venue_scope" in properties
    assert properties["opponent"]["anyOf"][0]["maxLength"] == 255


async def test_workspace_options_come_from_available_facts_and_metrics(
    client,
    db_session,
) -> None:
    ids = await seed_semantic_query_facts(db_session)

    response = await client.get("/api/v1/semantic-queries/options")

    assert response.status_code == 200
    payload = response.json()
    assert payload["program_slug"] == "womens-basketball"
    assert payload["seasons"] == ["2025-26", "2024-25"]
    assert [metric["stat_key"] for metric in payload["metrics"]] == ["points"]
    assert payload["players"] == [
        {
            "player_id": ids["alice_id"],
            "player_name": "Alice Adams",
            "seasons": ["2025-26"],
        },
        {
            "player_id": ids["bob_id"],
            "player_name": "Bobbi Brown",
            "seasons": ["2025-26"],
        },
    ]
    assert payload["opponents"] == [
        {"opponent_name": "Montana", "seasons": ["2025-26"]},
        {"opponent_name": "Montana State", "seasons": ["2025-26"]},
        {"opponent_name": "Washington State", "seasons": ["2025-26"]},
    ]
    assert payload["leader_limits"] == [5, 10, 15, 25]
    assert payload["default_season"] == "2025-26"
    assert payload["default_stat_key"] == "points"


async def test_team_season_record_counts_final_non_exhibition_games(client, db_session):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "team_season_record",
            "season": "2025-26",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_id"] == "team_season_record"
    result = payload["result"]
    assert (result["games_played"], result["wins"], result["losses"]) == (3, 2, 1)
    assert result["open_quality_issue_count"] == 1
    assert result["coverage"]["completeness"] == "complete"
    assert [game["opponent"] for game in result["games"]] == [
        "Montana",
        "Montana State",
        "Washington State",
    ]


async def test_team_record_supports_conference_only_scope(client, db_session):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "team_season_record",
            "season": "2025-26",
            "conference_scope": "conference",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert (result["games_played"], result["wins"], result["losses"]) == (2, 2, 0)
    assert all(game["conference_event"] for game in result["games"])


async def test_team_record_filters_one_opponent(client, db_session):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "team_season_record",
            "season": "2025-26",
            "opponent": "Washington State",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["opponent"] == "Washington State"
    assert (result["games_played"], result["wins"], result["losses"]) == (1, 0, 1)
    assert result["open_quality_issue_count"] == 0
    assert [game["opponent"] for game in result["games"]] == ["Washington State"]


async def test_stat_leaders_reuses_vetted_record_book_query(client, db_session):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "stat_leaders",
            "stat_key": "points",
            "scope": "season",
            "season": "2025-26",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert [leader["player_name"] for leader in result["leaders"]] == [
        "Bobbi Brown",
        "Alice Adams",
    ]
    assert [Decimal(leader["total"]) for leader in result["leaders"]] == [
        Decimal("200"),
        Decimal("150"),
    ]


async def test_opponent_stat_leaders_ranks_game_facts_with_evidence(
    client,
    db_session,
):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "opponent_stat_leaders",
            "stat_key": "points",
            "season": "2025-26",
            "conference_scope": "conference",
            "opponent": "Montana State",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_id"] == "opponent_stat_leaders"
    result = payload["result"]
    assert result["opponent"] == "Montana State"
    assert result["conference_scope"] == "conference"
    assert result["total_players"] == 2
    assert result["open_quality_issue_count"] == 1
    assert [leader["player_name"] for leader in result["leaders"]] == [
        "Bobbi Brown",
        "Alice Adams",
    ]
    assert [Decimal(leader["total"]) for leader in result["leaders"]] == [
        Decimal("18"),
        Decimal("15"),
    ]
    assert [leader["rank"] for leader in result["leaders"]] == [1, 2]
    assert all(leader["games_count"] == 1 for leader in result["leaders"])
    assert result["leaders"][0]["games"][0]["opponent"] == "Montana State"
    assert result["leaders"][0]["games"][0]["source_url"].endswith("/game/2")


async def test_opponent_stat_leaders_applies_conference_scope(client, db_session):
    await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "opponent_stat_leaders",
            "stat_key": "points",
            "season": "2025-26",
            "conference_scope": "non_conference",
            "opponent": "Montana State",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["total_players"] == 0
    assert result["leaders"] == []


async def test_opponent_stat_leaders_assigns_shared_ranks_for_ties(
    client,
    db_session,
):
    await seed_semantic_query_facts(db_session)
    bob_montana_points = await db_session.scalar(
        select(PlayerGameStat)
        .join(Game, Game.id == PlayerGameStat.game_id)
        .join(Player, Player.id == PlayerGameStat.player_id)
        .where(
            Game.canonical_uid == "semantic:game:1",
            Player.display_name == "Bobbi Brown",
        )
    )
    assert bob_montana_points is not None
    bob_montana_points.value = Decimal("20")
    await db_session.commit()

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "opponent_stat_leaders",
            "stat_key": "points",
            "season": "2025-26",
            "opponent": "Montana",
        },
    )

    assert response.status_code == 200
    leaders = response.json()["result"]["leaders"]
    assert [leader["player_name"] for leader in leaders] == [
        "Alice Adams",
        "Bobbi Brown",
    ]
    assert [leader["rank"] for leader in leaders] == [1, 1]


async def test_player_career_total_returns_season_evidence(client, db_session):
    ids = await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "player_career_total",
            "player_id": ids["alice_id"],
            "stat_key": "points",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["player_name"] == "Alice Adams"
    assert Decimal(result["total"]) == 250
    assert result["seasons_count"] == 2
    assert [row["season"] for row in result["season_breakdown"]] == [
        "2025-26",
        "2024-25",
    ]
    assert result["season_breakdown"][0]["source_url"].endswith("2025-26")
    assert result["coverage"]["first_season"] == "2024-25"
    assert "not all-time history" in result["coverage"]["statement"]


async def test_player_game_split_filters_conference_facts(client, db_session):
    ids = await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "player_game_split",
            "player_id": ids["alice_id"],
            "stat_key": "points",
            "season": "2025-26",
            "conference_scope": "conference",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert Decimal(result["value"]) == 35
    assert result["games_count"] == 2
    assert result["open_quality_issue_count"] == 1
    assert [Decimal(game["value"]) for game in result["games"]] == [
        Decimal("20"),
        Decimal("15"),
    ]
    assert all(game["conference_event"] for game in result["games"])
    assert result["games"][1]["source_url"].endswith("/game/2")


async def test_player_game_split_filters_one_opponent(client, db_session):
    ids = await seed_semantic_query_facts(db_session)

    response = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "player_game_split",
            "player_id": ids["alice_id"],
            "stat_key": "points",
            "season": "2025-26",
            "opponent": "Montana State",
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["opponent"] == "Montana State"
    assert Decimal(result["value"]) == 15
    assert result["games_count"] == 1
    assert [game["opponent"] for game in result["games"]] == ["Montana State"]


async def test_semantic_query_rejects_unknown_query_and_unvetted_metric(
    client,
    db_session,
):
    ids = await seed_semantic_query_facts(db_session)

    unknown = await client.post(
        "/api/v1/semantic-queries/execute",
        json={"query_id": "write_sql", "sql": "select 1"},
    )
    unvetted = await client.post(
        "/api/v1/semantic-queries/execute",
        json={
            "query_id": "player_career_total",
            "player_id": ids["alice_id"],
            "stat_key": "personal_fouls",
        },
    )

    assert unknown.status_code == 422
    assert unvetted.status_code == 404
    assert unvetted.json()["detail"] == (
        "Record Book metric 'personal_fouls' is not available."
    )
