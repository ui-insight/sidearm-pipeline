"""Tests for deterministic player matching and the unresolved review queue."""

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.data_quality_issue import DataQualityIssue
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_identity_resolution import PlayerIdentityResolution
from app.models.sport_program import SportProgram
from app.services.player_identity import (
    PlayerIdentityRow,
    resolve_player_identity,
)

INSTITUTION = "University of Idaho"
SEASON = "2025-26"


async def _seed_program(db_session) -> SportProgram:
    await seed_warehouse_reference_data(db_session)
    await db_session.flush()
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    assert program is not None
    return program


async def _add_roster_player(
    db_session,
    program: SportProgram,
    *,
    display_name: str,
    jersey_number: str,
    source_player_id: str | None = None,
) -> Player:
    player = Player(display_name=display_name)
    db_session.add(player)
    await db_session.flush()
    db_session.add(
        PlayerSeason(
            player_id=player.id,
            sport_program_id=program.id,
            season=SEASON,
            jersey_number=jersey_number,
        )
    )
    if source_player_id:
        db_session.add(
            PlayerExternalIdentity(
                player_id=player.id,
                source_system="sidearm",
                institution=INSTITUTION,
                source_player_id=source_player_id,
            )
        )
    await db_session.flush()
    return player


def _source_row(program: SportProgram, **overrides) -> PlayerIdentityRow:
    values = {
        "sport_program_id": program.id,
        "source_system": "sidearm",
        "institution": INSTITUTION,
        "season": SEASON,
        "player_name": "Gardner, Kyra",
        "jersey_number": "03",
        "source_url": "https://govandals.com/boxscore/9968",
    }
    values.update(overrides)
    return PlayerIdentityRow(**values)


async def test_resolver_prefers_namespaced_source_player_id(db_session) -> None:
    program = await _seed_program(db_session)
    player = await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="03",
        source_player_id="8435",
    )

    match = await resolve_player_identity(
        db_session,
        _source_row(
            program,
            player_name="Incorrect Display Name",
            jersey_number="99",
            source_player_id="8435",
        ),
    )

    assert match.player_id == player.id
    assert match.method == "source_player_id"
    assert match.issue_id is None
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 0


async def test_resolver_uses_exact_normalized_name_and_jersey_fallback(
    db_session,
) -> None:
    program = await _seed_program(db_session)
    player = await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="3",
    )

    match = await resolve_player_identity(db_session, _source_row(program))

    assert match.player_id == player.id
    assert match.method == "roster_name_jersey"
    assert match.issue_id is None


async def test_resolver_does_not_fallback_on_name_without_matching_jersey(
    db_session,
) -> None:
    program = await _seed_program(db_session)
    await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="12",
    )

    match = await resolve_player_identity(db_session, _source_row(program))
    issue = await db_session.get(DataQualityIssue, match.issue_id)

    assert match.method == "unresolved"
    assert issue is not None
    assert issue.details["reason"] == "unmatched"


async def test_ambiguous_fallback_is_deduplicated_in_review_queue(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    first = await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="3",
    )
    second = await _add_roster_player(
        db_session,
        program,
        display_name="Gardner, Kyra",
        jersey_number="03",
    )

    first_match = await resolve_player_identity(db_session, _source_row(program))
    second_match = await resolve_player_identity(db_session, _source_row(program))
    issue = await db_session.get(DataQualityIssue, first_match.issue_id)

    assert first_match.method == "unresolved"
    assert first_match.issue_id == second_match.issue_id
    assert issue is not None
    assert issue.details["reason"] == "ambiguous"
    assert issue.details["candidate_player_ids"] == sorted([first.id, second.id])
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 1

    await db_session.commit()
    response = await client.get("/api/v1/identity-resolution/queue")
    assert response.status_code == 200
    assert response.json()[0]["candidate_players"] == [
        {"id": first.id, "display_name": "Kyra Gardner"},
        {"id": second.id, "display_name": "Gardner, Kyra"},
    ]


async def test_queue_api_resolution_is_reused_for_future_signature_rows(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    player = await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="3",
    )
    row = _source_row(program, player_name="K. Gardner")
    unresolved = await resolve_player_identity(db_session, row)
    await db_session.commit()

    queue_response = await client.get("/api/v1/identity-resolution/queue")
    assert queue_response.status_code == 200
    queue = queue_response.json()
    assert len(queue) == 1
    assert queue[0]["id"] == unresolved.issue_id
    assert queue[0]["details"]["reason"] == "unmatched"

    resolution_response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/resolve",
        json={
            "player_id": player.id,
            "resolution_notes": "SID confirmed the abbreviated display name.",
        },
    )
    assert resolution_response.status_code == 200
    assert resolution_response.json()["player_id"] == player.id
    assert resolution_response.json()["status"] == "resolved"

    future_match = await resolve_player_identity(db_session, row)
    assert future_match.player_id == player.id
    assert future_match.method == "manual_resolution"
    assert await db_session.scalar(select(func.count(PlayerIdentityResolution.id))) == 1

    assert (await client.get("/api/v1/identity-resolution/queue")).json() == []
    resolved_queue = await client.get(
        "/api/v1/identity-resolution/queue?status=resolved"
    )
    assert resolved_queue.status_code == 200
    assert resolved_queue.json()[0]["player_id"] == player.id


async def test_manual_source_id_resolution_creates_future_exact_identity(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    player = await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="3",
    )
    row = _source_row(
        program,
        player_name="Unknown Source Label",
        jersey_number=None,
        source_player_id="9999",
    )
    unresolved = await resolve_player_identity(db_session, row)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/resolve",
        json={
            "player_id": player.id,
            "resolution_notes": "SID verified the source bio link.",
        },
    )

    assert response.status_code == 200
    future_match = await resolve_player_identity(db_session, row)
    assert future_match.player_id == player.id
    assert future_match.method == "source_player_id"
    identity = await db_session.scalar(
        select(PlayerExternalIdentity).where(
            PlayerExternalIdentity.source_player_id == "9999"
        )
    )
    assert identity is not None
    assert identity.player_id == player.id


async def test_queue_api_can_create_and_resolve_an_unmatched_player(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    row = _source_row(
        program,
        institution="Idaho State University",
        player_name="Reynolds, Maria",
        jersey_number="12",
        source_player_id="9912",
        source_url="https://isubengals.com/sports/womens-basketball/roster/maria-reynolds/9912",
    )
    unresolved = await resolve_player_identity(db_session, row)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/create-player",
        json={
            "display_name": "Maria Reynolds",
            "resolution_notes": "SID verified the opponent bio and jersey number.",
        },
    )

    assert response.status_code == 201
    player_id = response.json()["player_id"]
    player = await db_session.get(Player, player_id)
    assert player is not None
    assert player.display_name == "Maria Reynolds"

    identity = await db_session.scalar(
        select(PlayerExternalIdentity).where(
            PlayerExternalIdentity.source_system == "sidearm",
            PlayerExternalIdentity.institution == "Idaho State University",
            PlayerExternalIdentity.source_player_id == "9912",
        )
    )
    assert identity is not None
    assert identity.player_id == player_id

    membership = await db_session.scalar(
        select(PlayerSeason).where(PlayerSeason.player_id == player_id)
    )
    assert membership is not None
    assert membership.sport_program_id == program.id
    assert membership.season == SEASON
    assert membership.jersey_number == "12"
    assert membership.bio_url == row.source_url

    future_match = await resolve_player_identity(db_session, row)
    assert future_match.player_id == player_id
    assert future_match.method == "source_player_id"

    assert (await client.get("/api/v1/identity-resolution/queue")).json() == []
    resolved_queue = await client.get(
        "/api/v1/identity-resolution/queue?status=resolved"
    )
    assert resolved_queue.json()[0]["resolved_player_name"] == "Maria Reynolds"


async def test_create_player_rejects_an_already_resolved_issue(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    unresolved = await resolve_player_identity(db_session, _source_row(program))
    await db_session.commit()

    first_response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/create-player",
        json={
            "display_name": "Kyra Gardner",
            "resolution_notes": "SID verified the player.",
        },
    )
    duplicate_response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/create-player",
        json={
            "display_name": "Duplicate Player",
            "resolution_notes": "Stale browser retry.",
        },
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == (
        f"Identity issue {unresolved.issue_id} has already been resolved"
    )
    assert await db_session.scalar(select(func.count(Player.id))) == 1


async def test_create_player_rejects_an_ambiguous_issue_with_candidates(
    client,
    db_session,
) -> None:
    program = await _seed_program(db_session)
    await _add_roster_player(
        db_session,
        program,
        display_name="Kyra Gardner",
        jersey_number="3",
    )
    await _add_roster_player(
        db_session,
        program,
        display_name="Gardner, Kyra",
        jersey_number="03",
    )
    unresolved = await resolve_player_identity(db_session, _source_row(program))
    await db_session.commit()

    response = await client.post(
        f"/api/v1/identity-resolution/queue/{unresolved.issue_id}/create-player",
        json={
            "display_name": "Duplicate Player",
            "resolution_notes": "Attempted to bypass the candidate review.",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "This identity issue has roster candidates and must link to an existing "
        "canonical player"
    )
    assert await db_session.scalar(select(func.count(Player.id))) == 2


async def test_create_player_request_rejects_whitespace_only_fields(
    client,
) -> None:
    response = await client.post(
        "/api/v1/identity-resolution/queue/1/create-player",
        json={"display_name": "   ", "resolution_notes": "  "},
    )

    assert response.status_code == 422
