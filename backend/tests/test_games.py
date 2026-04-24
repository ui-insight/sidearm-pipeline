"""Tests for game ingestion and canonical event metadata."""

from sqlalchemy import func, select

from app.models.content import GeneratedContent
from app.models.game import Game, SourceSnapshot
from app.services.sidearm_scraper import ParsedBoxscore


async def test_ingest_creates_canonical_event_metadata(
    client,
    db_session,
    monkeypatch,
):
    raw_html = "<html><title>Football vs UC Davis</title></html>"

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        return ParsedBoxscore(
            source_url=url,
            title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
            sport="football",
            season="2025",
            game_date="11/8/2025",
            home_team="Idaho",
            away_team="UC Davis",
            home_score=31,
            away_score=28,
            team_stats=[
                {
                    "stat_name": "First Downs",
                    "home_value": "22",
                    "away_value": "18",
                    "sort_order": 0,
                }
            ],
            scoring_plays=[
                {
                    "period": "4",
                    "clock": "00:00",
                    "team": "IDA",
                    "description": "IDA - field goal",
                    "home_score": 31,
                    "away_score": 28,
                    "sort_order": 0,
                }
            ],
            player_stats=[],
            raw_html=raw_html,
        )

    monkeypatch.setattr("app.api.v1.games.scrape_boxscore", fake_scrape_boxscore)

    response = await client.post(
        "/api/v1/games",
        json={
            "url": "https://govandals.com/sports/football/stats/2025/"
            "uc-davis/boxscore/8467"
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["canonical_uid"] == "sidearm:football:2025:8467"
    assert payload["source_system"] == "sidearm"
    assert payload["source_event_id"] == "8467"
    assert payload["sport_name"] == "Football"
    assert payload["event_shape"] == "team_contest"
    assert payload["event_status"] == "final"
    assert payload["publish_status"] == "draft"
    assert payload["home_away_neutral"] == "home"
    assert payload["event_sources"][0]["source_type"] == "boxscore_html"
    assert payload["event_sources"][0]["source_id"] == "8467"
    assert payload["event_sources"][0]["primary_source"] is True
    assert payload["source_snapshots"][0]["parser_version"] == "sidearm-html-v1"
    assert len(payload["source_snapshots"][0]["content_hash"]) == 64
    assert payload["status_history"][0]["to_status"] == "final"

    game = await db_session.scalar(select(Game))
    assert game is not None
    assert game.canonical_uid == "sidearm:football:2025:8467"

    snapshot = await db_session.scalar(select(SourceSnapshot))
    assert snapshot is not None
    assert snapshot.raw_body == raw_html


async def test_reingest_updates_existing_canonical_event(
    client,
    db_session,
    monkeypatch,
):
    parsed_responses = [
        ParsedBoxscore(
            source_url="https://govandals.com/sports/football/stats/2025/"
            "uc-davis/boxscore/8467",
            title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
            sport="football",
            season="2025",
            game_date="11/8/2025",
            home_team="Idaho",
            away_team="UC Davis",
            home_score=28,
            away_score=28,
            raw_html="<html>first</html>",
        ),
        ParsedBoxscore(
            source_url="https://govandals.com/sports/football/stats/2025/"
            "uc-davis/boxscore/8467",
            title="Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics",
            sport="football",
            season="2025",
            game_date="11/8/2025",
            home_team="Idaho",
            away_team="UC Davis",
            home_score=31,
            away_score=28,
            raw_html="<html>second</html>",
        ),
    ]

    async def fake_scrape_boxscore(url: str) -> ParsedBoxscore:
        parsed = parsed_responses.pop(0)
        parsed.source_url = url
        return parsed

    monkeypatch.setattr("app.api.v1.games.scrape_boxscore", fake_scrape_boxscore)

    ingest_payload = {
        "url": "https://govandals.com/sports/football/stats/2025/uc-davis/boxscore/8467"
    }
    first_response = await client.post("/api/v1/games", json=ingest_payload)
    assert first_response.status_code == 201
    game_id = first_response.json()["id"]

    db_session.add(
        GeneratedContent(
            game_id=game_id,
            headline="Existing recap",
            recap="Existing recap body",
            spotlight_player="Doe, Jane",
            spotlight_body="Existing spotlight",
            social_post="Existing social",
            model="test-model",
        )
    )
    await db_session.commit()

    second_response = await client.post("/api/v1/games", json=ingest_payload)

    assert second_response.status_code == 201
    payload = second_response.json()
    assert payload["id"] == game_id
    assert payload["home_score"] == 31
    assert payload["away_score"] == 28
    assert len(payload["source_snapshots"]) == 2
    assert len(payload["generated_content"]) == 1
    assert payload["generated_content"][0]["headline"] == "Existing recap"

    game_count = await db_session.scalar(select(func.count()).select_from(Game))
    assert game_count == 1
