"""Verify historical pregame briefs enforce their as-of boundary."""

from pathlib import Path

from sqlalchemy import select

from app.models.game import Game
from app.models.player import PlayerSeason
from tests.test_semantic_queries import seed_semantic_query_facts

FIXTURES = Path(__file__).parent / "fixtures"


async def test_historical_brief_excludes_target_and_future_facts(client, db_session):
    seeded = await seed_semantic_query_facts(db_session)
    alice_roster = await db_session.scalar(
        select(PlayerSeason).where(
            PlayerSeason.player_id == seeded["alice_id"],
            PlayerSeason.season == "2025-26",
        )
    )
    assert alice_roster is not None
    alice_roster.jersey_number = "4"
    alice_roster.position = "Guard"
    alice_roster.class_year = "Jr."
    previous_meeting = await db_session.get(Game, 2)
    assert previous_meeting is not None
    previous_meeting.raw_html = (
        FIXTURES / "womens_basketball_boxscore_2025_26_idaho_state.html"
    ).read_text()
    target = Game(
        source_url="https://govandals.com/game/rematch",
        canonical_uid="pregame:rematch",
        sport="womens-basketball",
        season="2025-26",
        game_date="2026-02-05",
        event_status="final",
        home_team="Idaho",
        away_team="Montana State",
        home_score=73,
        away_score=70,
        home_away_neutral="home",
        conference_event=True,
        exhibition=False,
    )
    future = Game(
        source_url="https://govandals.com/game/future",
        canonical_uid="pregame:future",
        sport="womens-basketball",
        season="2025-26",
        game_date="2026-02-12",
        event_status="final",
        home_team="Idaho",
        away_team="Weber State",
        home_score=90,
        away_score=50,
        home_away_neutral="home",
        conference_event=True,
        exhibition=False,
    )
    db_session.add_all([target, future])
    await db_session.commit()

    response = await client.get(
        "/api/v1/pregame-briefs/historical",
        params={
            "season": "2025-26",
            "opponent": "Montana State",
            "game_date": "2026-02-05",
        },
    )

    assert response.status_code == 200
    brief = response.json()
    assert brief["as_of_date"] == "2026-02-04"
    assert brief["season_record"] == {
        "games_played": 3,
        "wins": 2,
        "losses": 1,
        "ties": 0,
    }
    assert [game["game_id"] for game in brief["recent_form"]] == [3, 2, 1]
    assert [game["opponent"] for game in brief["prior_meetings"]] == ["Montana State"]
    scoring = next(
        group
        for group in brief["vandal_leader_groups"]
        if group["stat_key"] == "points"
    )
    assert scoring["leaders"][0]["player_name"] == "Alice Adams"
    assert scoring["leaders"][0]["team_name"] == "Idaho"
    assert scoring["leaders"][0]["jersey_number"] == "4"
    assert scoring["leaders"][0]["position"] == "Guard"
    assert scoring["leaders"][0]["total"] == "45.000000"
    assert len(brief["previous_matchup_teams"]) == 2
    assert brief["target_game"]["idaho_score"] == 73
    assert brief["target_game"]["opponent_score"] == 70
    assert target.id not in {
        game["game_id"]
        for group in brief["vandal_leader_groups"]
        for leader in group["leaders"]
        for game in leader["evidence"]
    }
    assert future.id not in {game["game_id"] for game in brief["recent_form"]}


async def test_historical_brief_returns_not_found_for_unknown_matchup(client):
    response = await client.get(
        "/api/v1/pregame-briefs/historical",
        params={
            "season": "2025-26",
            "opponent": "Unknown State",
            "game_date": "2026-02-05",
        },
    )

    assert response.status_code == 404
