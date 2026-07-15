"""Tests for canonical roster identity persistence."""

from sqlalchemy import func, select

from app.db.seed import seed_warehouse_reference_data
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import SourceSnapshot
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.team import Team
from app.services.roster_import import import_roster
from app.services.sidearm_roster import ParsedRoster, ParsedRosterPlayer


def _roster(
    *,
    season: str,
    institution: str = "University of Idaho",
    team_slug: str = "idaho",
    source_player_id: str | None,
    canonical_source_player_id: str | None = None,
) -> ParsedRoster:
    bio_url = (
        "https://govandals.com/sports/womens-basketball/roster/"
        f"sarah-brans/{source_player_id}"
        if source_player_id
        else None
    )
    canonical_bio_url = (
        "https://govandals.com/sports/womens-basketball/roster/"
        f"sarah-brans/{canonical_source_player_id}"
        if canonical_source_player_id
        else bio_url
    )
    return ParsedRoster(
        sport_program_slug="womens-basketball",
        season=season,
        source_system="sidearm",
        institution=institution,
        team_slug=team_slug,
        source_url=("https://govandals.com/sports/womens-basketball/roster/" + season),
        raw_html=f"<html>{season}</html>",
        players=[
            ParsedRosterPlayer(
                display_name="Sarah Brans",
                jersey_number="2",
                class_year="Sr." if season == "2025-26" else "Jr.",
                position="F",
                bio_url=bio_url,
                source_player_id=source_player_id,
                canonical_bio_url=canonical_bio_url,
            )
        ],
    )


async def test_redirect_aliases_join_multiple_seasons_to_one_player(
    db_session,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()

    first_result = await import_roster(
        db_session,
        _roster(
            season="2024-25",
            source_player_id="7988",
            canonical_source_player_id="8428",
        ),
    )
    second_result = await import_roster(
        db_session,
        _roster(season="2025-26", source_player_id="8428"),
    )

    assert first_result.players_created == 1
    assert first_result.identities_created == 2
    assert second_result.players_created == 0
    assert second_result.identities_created == 0
    assert await db_session.scalar(select(func.count(Player.id))) == 1
    assert await db_session.scalar(select(func.count(PlayerExternalIdentity.id))) == 2
    assert await db_session.scalar(select(func.count(PlayerSeason.id))) == 2
    seasons = (
        await db_session.scalars(select(PlayerSeason).order_by(PlayerSeason.season))
    ).all()
    assert [season.season for season in seasons] == ["2024-25", "2025-26"]
    assert [season.class_year for season in seasons] == ["Jr.", "Sr."]


async def test_replay_is_idempotent_for_players_seasons_and_quality_issues(
    db_session,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    unresolved = _roster(season="2025-26", source_player_id=None)

    first_result = await import_roster(db_session, unresolved)
    second_result = await import_roster(db_session, unresolved)

    assert first_result.quality_issues_created == 1
    assert second_result.quality_issues_created == 0
    assert await db_session.scalar(select(func.count(Player.id))) == 0
    assert await db_session.scalar(select(func.count(PlayerSeason.id))) == 0
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 1
    assert await db_session.scalar(select(func.count(SourceSnapshot.id))) == 2
    issue = await db_session.scalar(select(DataQualityIssue))
    assert issue is not None
    assert issue.issue_type == "unresolved_identity"
    assert issue.deduplication_key is not None
    assert issue.source_snapshot_id == second_result.source_snapshot_id


async def test_external_ids_remain_isolated_by_institution(db_session) -> None:
    await seed_warehouse_reference_data(db_session)
    db_session.add(
        Team(
            slug="idaho-state",
            canonical_name="Idaho State",
            institution="Idaho State University",
        )
    )
    await db_session.commit()

    await import_roster(
        db_session,
        _roster(season="2025-26", source_player_id="8428"),
    )
    await import_roster(
        db_session,
        _roster(
            season="2025-26",
            institution="Idaho State University",
            team_slug="idaho-state",
            source_player_id="8428",
        ),
    )

    assert await db_session.scalar(select(func.count(Player.id))) == 2
    identities = (
        await db_session.scalars(
            select(PlayerExternalIdentity).order_by(PlayerExternalIdentity.institution)
        )
    ).all()
    assert [identity.institution for identity in identities] == [
        "Idaho State University",
        "University of Idaho",
    ]
    assert {identity.source_player_id for identity in identities} == {"8428"}


async def test_same_name_without_exact_alias_evidence_is_not_merged(
    db_session,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()

    await import_roster(
        db_session,
        _roster(season="2024-25", source_player_id="7988"),
    )
    await import_roster(
        db_session,
        _roster(season="2025-26", source_player_id="8428"),
    )

    assert await db_session.scalar(select(func.count(Player.id))) == 2
    assert await db_session.scalar(select(func.count(PlayerSeason.id))) == 2


async def test_conflicting_redirect_aliases_create_quality_issue(
    db_session,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    first_player = Player(display_name="Historical Sarah")
    first_player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="7988",
        )
    )
    second_player = Player(display_name="Current Sarah")
    second_player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="8428",
        )
    )
    db_session.add_all([first_player, second_player])
    await db_session.commit()

    result = await import_roster(
        db_session,
        _roster(
            season="2024-25",
            source_player_id="7988",
            canonical_source_player_id="8428",
        ),
    )

    assert result.quality_issues_created == 1
    assert await db_session.scalar(select(func.count(Player.id))) == 2
    assert await db_session.scalar(select(func.count(PlayerSeason.id))) == 0
    issue = await db_session.scalar(select(DataQualityIssue))
    assert issue is not None
    assert issue.issue_type == "source_conflict"
