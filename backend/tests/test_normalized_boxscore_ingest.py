"""End-to-end coverage for normalized WBB boxscore persistence."""

from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.achievement import AchievementSuggestion
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import IngestRun, PlayerStatGroup, SourceSnapshot
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.sidearm_scraper import ParsedBoxscore, parse_boxscore

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BOXSCORE_URL = (
    "https://govandals.com/sports/womens-basketball/stats/2025-26/"
    "idaho-state/boxscore/9968"
)


async def _seed_idaho_roster(
    db_session,
    parsed: ParsedBoxscore,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.flush()
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    idaho = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    assert program is not None
    assert idaho is not None

    for source_row in parsed.player_stat_rows:
        if not source_row["is_idaho"]:
            continue
        player = Player(display_name=source_row["player_name"])
        player.external_identities.append(
            PlayerExternalIdentity(
                source_system="sidearm",
                institution="University of Idaho",
                source_player_id=source_row["source_player_id"],
                source_url=source_row["player_bio_url"],
            )
        )
        player.seasons.append(
            PlayerSeason(
                sport_program=program,
                team=idaho,
                season="2025-26",
                jersey_number=source_row["jersey_number"],
                bio_url=source_row["player_bio_url"],
            )
        )
        db_session.add(player)
    await db_session.commit()


async def test_wbb_ingest_writes_normalized_facts_and_replays_idempotently(
    client,
    db_session,
    monkeypatch,
) -> None:
    raw_html = (
        FIXTURE_DIR / "womens_basketball_boxscore_2025_26_idaho_state.html"
    ).read_text(encoding="utf-8")
    parsed = parse_boxscore(BOXSCORE_URL, raw_html)
    await _seed_idaho_roster(db_session, parsed)

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        assert url == BOXSCORE_URL
        return parsed

    monkeypatch.setattr("app.api.v1.games.scrape_boxscore", fake_scrape_boxscore)

    first_response = await client.post(
        "/api/v1/games",
        json={"url": BOXSCORE_URL},
    )

    assert first_response.status_code == 201
    first_payload = first_response.json()
    assert first_payload["canonical_uid"] == ("sidearm:womens-basketball:2025-26:9968")
    assert first_payload["player_stats"] == []
    assert len(first_payload["source_snapshots"]) == 1

    assert await db_session.scalar(select(func.count(PlayerGameStat.id))) == 144
    assert await db_session.scalar(select(func.count(PlayerStatGroup.id))) == 0
    assert await db_session.scalar(select(func.count(SourceSnapshot.id))) == 1
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 10
    first_suggestion_count = await db_session.scalar(
        select(func.count(AchievementSuggestion.id))
    )
    assert first_suggestion_count > 0

    kyra = await db_session.scalar(
        select(Player).where(Player.display_name == "Gardner, Kyra")
    )
    points = await db_session.scalar(
        select(StatDefinition).where(
            StatDefinition.stat_key == "points",
            StatDefinition.entity_scope == "player",
        )
    )
    assert kyra is not None
    assert points is not None
    kyra_points = await db_session.scalar(
        select(PlayerGameStat).where(
            PlayerGameStat.player_id == kyra.id,
            PlayerGameStat.stat_definition_id == points.id,
        )
    )
    assert kyra_points is not None
    assert int(kyra_points.value) == 13
    assert kyra_points.source_field == "PTS"
    assert kyra_points.source_value == "13"
    assert kyra_points.team_id is not None
    assert kyra_points.source_snapshot_id is not None

    facts_response = await client.get(
        f"/api/v1/games/{first_payload['id']}/player-stats"
    )
    assert facts_response.status_code == 200
    facts = facts_response.json()
    assert len(facts) == 144
    kyra_points_payload = next(
        fact
        for fact in facts
        if fact["player_name"] == "Gardner, Kyra" and fact["stat_key"] == "points"
    )
    assert Decimal(kyra_points_payload["value"]) == 13
    assert kyra_points_payload["display_label"] == "Points"
    assert kyra_points_payload["team_name"] == "Idaho"
    assert kyra_points_payload["source_field"] == "PTS"
    assert kyra_points_payload["source_value"] == "13"
    assert kyra_points_payload["source_snapshot_id"] is not None

    first_snapshot = await db_session.get(
        SourceSnapshot,
        kyra_points.source_snapshot_id,
    )
    assert first_snapshot is not None
    assert first_snapshot.raw_body == raw_html

    ingest_run = await db_session.scalar(select(IngestRun))
    assert ingest_run is not None
    assert ingest_run.run_metadata["normalized_player_rows_seen"] == 19
    assert ingest_run.run_metadata["normalized_player_rows_resolved"] == 9
    assert ingest_run.run_metadata["normalized_player_rows_unresolved"] == 10
    assert ingest_run.run_metadata["normalized_player_game_stats_written"] == 144
    assert ingest_run.run_metadata["achievement_suggestions_written"] == (
        first_suggestion_count
    )
    assert ingest_run.run_metadata["achievement_policy_version"] == 1

    queue_response = await client.get("/api/v1/identity-resolution/queue")
    assert queue_response.status_code == 200
    assert len(queue_response.json()) == 10
    assert {item["details"]["player_name"] for item in queue_response.json()} == {
        source_row["player_name"]
        for source_row in parsed.player_stat_rows
        if not source_row["is_idaho"]
    }

    second_response = await client.post(
        "/api/v1/games",
        json={"url": BOXSCORE_URL},
    )

    assert second_response.status_code == 201
    second_payload = second_response.json()
    assert second_payload["id"] == first_payload["id"]
    assert second_payload["player_stats"] == []
    assert len(second_payload["source_snapshots"]) == 2
    assert await db_session.scalar(select(func.count(PlayerGameStat.id))) == 144
    assert await db_session.scalar(select(func.count(PlayerStatGroup.id))) == 0
    assert await db_session.scalar(select(func.count(SourceSnapshot.id))) == 2
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 10
    assert (
        await db_session.scalar(select(func.count(AchievementSuggestion.id)))
        == first_suggestion_count
    )

    latest_snapshot_id = await db_session.scalar(select(func.max(SourceSnapshot.id)))
    fact_snapshot_ids = set(
        await db_session.scalars(select(PlayerGameStat.source_snapshot_id))
    )
    assert fact_snapshot_ids == {latest_snapshot_id}


async def test_normalized_player_stats_returns_not_found_for_unknown_game(
    client,
) -> None:
    response = await client.get("/api/v1/games/999999/player-stats")

    assert response.status_code == 404
