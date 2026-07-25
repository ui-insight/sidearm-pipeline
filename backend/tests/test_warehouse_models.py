"""Tests for the normalized athletics warehouse core."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.seed import seed_warehouse_reference_data
from app.models.achievement import NotabilityPolicy, NotabilityPolicyMetric
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.models.team_game_stat import TeamGameStat
from app.models.team_season_stat import TeamSeasonStat


async def test_reference_seed_is_idempotent(db_session) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()
    await seed_warehouse_reference_data(db_session)
    await db_session.commit()

    program_count = await db_session.scalar(select(func.count(SportProgram.id)))
    idaho_count = await db_session.scalar(
        select(func.count(Team.id)).where(Team.slug == "idaho")
    )
    definition_count = await db_session.scalar(select(func.count(StatDefinition.id)))
    policy_count = await db_session.scalar(select(func.count(NotabilityPolicy.id)))
    policy_metric_count = await db_session.scalar(
        select(func.count(NotabilityPolicyMetric.id))
    )
    points = await db_session.scalar(
        select(StatDefinition).where(StatDefinition.stat_key == "points")
    )
    minutes = await db_session.scalar(
        select(StatDefinition).where(StatDefinition.stat_key == "minutes_played")
    )

    assert program_count == 1
    assert idaho_count == 1
    assert definition_count == 16
    assert policy_count == 1
    assert policy_metric_count == 10
    assert points is not None
    assert points.aggregation_method == "sum"
    assert points.record_book_eligible is True
    assert points.notability_eligible is True
    assert not hasattr(points, "importance_weight")
    assert minutes is not None
    assert minutes.value_type == "duration"


async def test_player_external_identity_is_namespaced(db_session) -> None:
    idaho_player = Player(display_name="Example, Idaho")
    opponent_player = Player(display_name="Example, Opponent")
    idaho_player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="8435",
        )
    )
    opponent_player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="Idaho State University",
            source_player_id="8435",
        )
    )
    db_session.add_all([idaho_player, opponent_player])
    await db_session.commit()

    identity_count = await db_session.scalar(
        select(func.count(PlayerExternalIdentity.id)).where(
            PlayerExternalIdentity.source_player_id == "8435"
        )
    )
    assert identity_count == 2

    duplicate = Player(display_name="Duplicate")
    duplicate.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="8435",
        )
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.parametrize(
    ("aggregation_method", "numerator", "denominator"),
    [
        ("median", None, None),
        ("ratio_from_components", None, None),
    ],
)
async def test_stat_definition_rejects_invalid_aggregation_semantics(
    db_session,
    aggregation_method: str,
    numerator: str | None,
    denominator: str | None,
) -> None:
    program = SportProgram(
        slug="test-program",
        display_name="Test Program",
        sport="basketball",
    )
    db_session.add(program)
    await db_session.flush()
    db_session.add(
        StatDefinition(
            sport_program_id=program.id,
            stat_key="invalid_metric",
            display_label="Invalid Metric",
            entity_scope="player",
            value_type="decimal",
            aggregation_method=aggregation_method,
            comparison_direction="neutral",
            source_field_aliases=[],
            ratio_numerator_stat_key=numerator,
            ratio_denominator_stat_key=denominator,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_can_persist_all_normalized_fact_grains_and_trust_records(
    db_session,
) -> None:
    await seed_warehouse_reference_data(db_session)
    await db_session.flush()
    program = await db_session.scalar(
        select(SportProgram).where(SportProgram.slug == "womens-basketball")
    )
    idaho = await db_session.scalar(select(Team).where(Team.slug == "idaho"))
    player_points = await db_session.scalar(
        select(StatDefinition).where(
            StatDefinition.sport_program_id == program.id,
            StatDefinition.entity_scope == "player",
            StatDefinition.stat_key == "points",
        )
    )
    assert program is not None
    assert idaho is not None
    assert player_points is not None

    team_points = StatDefinition(
        sport_program_id=program.id,
        stat_key="points",
        display_label="Points",
        entity_scope="team",
        value_type="integer",
        unit="count",
        aggregation_method="sum",
        comparison_direction="higher",
        source_field_aliases=["PTS"],
        record_book_eligible=True,
        notability_eligible=True,
    )
    player = Player(display_name="Gardner, Kyra")
    player.external_identities.append(
        PlayerExternalIdentity(
            source_system="sidearm",
            institution="University of Idaho",
            source_player_id="8435",
            source_url=(
                "https://govandals.com/sports/womens-basketball/roster/"
                "kyra-gardner/8435"
            ),
        )
    )
    player_season = PlayerSeason(
        sport_program=program,
        team=idaho,
        season="2025-26",
        jersey_number="03",
        bio_url=player.external_identities[0].source_url,
    )
    player.seasons.append(player_season)
    game = Game(
        source_url=(
            "https://govandals.com/sports/womens-basketball/stats/2025-26/"
            "idaho-state/boxscore/9968"
        ),
        canonical_uid="sidearm:womens-basketball:2025-26:9968",
        sport="womens-basketball",
        season="2025-26",
        home_team="Idaho",
        away_team="Idaho State",
        home_score=81,
        away_score=68,
    )
    db_session.add_all([team_points, player, game])
    await db_session.flush()

    db_session.add_all(
        [
            PlayerGameStat(
                game=game,
                player=player,
                team=idaho,
                stat_definition=player_points,
                value=Decimal("13"),
                source_field="PTS",
                source_value="13",
            ),
            TeamGameStat(
                game=game,
                team=idaho,
                stat_definition=team_points,
                value=Decimal("81"),
                source_field="PTS",
                source_value="81",
            ),
            PlayerSeasonStat(
                player_season=player_season,
                stat_definition=player_points,
                value=Decimal("275"),
                source_field="PTS",
                source_value="275",
            ),
            TeamSeasonStat(
                sport_program=program,
                season="2025-26",
                team=idaho,
                stat_definition=team_points,
                value=Decimal("1388"),
                source_field="PTS",
                source_value="1388",
            ),
            CoverageWindow(
                sport_program=program,
                stat_definition=player_points,
                grain="game",
                source_system="sidearm_html",
                first_season="2017-18",
                last_season="2025-26",
                completeness="partial",
                known_limitations="Pre-2017-18 markup is not yet supported.",
            ),
            DataQualityIssue(
                sport_program=program,
                game=game,
                player=player,
                stat_definition=player_points,
                issue_type="reconciliation_mismatch",
                status="open",
                severity="error",
                summary="Season points do not reconcile",
                details={"game_sum": 274, "season_total": 275},
            ),
        ]
    )
    await db_session.commit()

    assert await db_session.scalar(select(func.count(PlayerGameStat.id))) == 1
    assert await db_session.scalar(select(func.count(TeamGameStat.id))) == 1
    assert await db_session.scalar(select(func.count(PlayerSeasonStat.id))) == 1
    assert await db_session.scalar(select(func.count(TeamSeasonStat.id))) == 1
    assert await db_session.scalar(select(func.count(CoverageWindow.id))) == 1
    assert await db_session.scalar(select(func.count(DataQualityIssue.id))) == 1
