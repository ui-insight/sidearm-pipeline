"""Idempotent reference-data seeds for local warehouse development."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team

WBB_PROGRAM_SLUG = "womens-basketball"
IDAHO_TEAM_SLUG = "idaho"

WBB_STAT_DEFINITIONS = (
    {
        "stat_key": "minutes_played",
        "display_label": "Minutes",
        "source_field_aliases": ["MIN"],
        "unit": "minute",
        "value_type": "duration",
        "comparison_direction": "neutral",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "field_goals_made",
        "display_label": "Field Goals Made",
        "source_field_aliases": ["FG"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "field_goals_attempted",
        "display_label": "Field Goals Attempted",
        "source_field_aliases": ["FG"],
        "unit": "count",
        "comparison_direction": "neutral",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "three_point_field_goals_made",
        "display_label": "Three-Point Field Goals Made",
        "source_field_aliases": ["3PT"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "three_point_field_goals_attempted",
        "display_label": "Three-Point Field Goals Attempted",
        "source_field_aliases": ["3PT"],
        "unit": "count",
        "comparison_direction": "neutral",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "free_throws_made",
        "display_label": "Free Throws Made",
        "source_field_aliases": ["FT"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "free_throws_attempted",
        "display_label": "Free Throws Attempted",
        "source_field_aliases": ["FT"],
        "unit": "count",
        "comparison_direction": "neutral",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "offensive_rebounds",
        "display_label": "Offensive Rebounds",
        "source_field_aliases": ["ORB-DRB"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "defensive_rebounds",
        "display_label": "Defensive Rebounds",
        "source_field_aliases": ["ORB-DRB"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "total_rebounds",
        "display_label": "Rebounds",
        "source_field_aliases": ["REB"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "personal_fouls",
        "display_label": "Personal Fouls",
        "source_field_aliases": ["PF"],
        "unit": "count",
        "comparison_direction": "lower",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "assists",
        "display_label": "Assists",
        "source_field_aliases": ["A"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "turnovers",
        "display_label": "Turnovers",
        "source_field_aliases": ["TO"],
        "unit": "count",
        "comparison_direction": "lower",
        "record_book_eligible": False,
        "notability_eligible": False,
    },
    {
        "stat_key": "blocks",
        "display_label": "Blocks",
        "source_field_aliases": ["BLK"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "steals",
        "display_label": "Steals",
        "source_field_aliases": ["STL"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
    {
        "stat_key": "points",
        "display_label": "Points",
        "source_field_aliases": ["PTS"],
        "unit": "count",
        "comparison_direction": "higher",
        "record_book_eligible": True,
        "notability_eligible": True,
    },
)


async def seed_warehouse_reference_data(session: AsyncSession) -> None:
    """Create the WBB program, Idaho team, and atomic stat definitions once."""
    program = await session.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    if program is None:
        program = SportProgram(
            slug=WBB_PROGRAM_SLUG,
            display_name="Women's Basketball",
            sport="basketball",
            gender="women",
            season_format="academic_year",
        )
        session.add(program)
        await session.flush()

    idaho = await session.scalar(select(Team).where(Team.slug == IDAHO_TEAM_SLUG))
    if idaho is None:
        session.add(
            Team(
                slug=IDAHO_TEAM_SLUG,
                canonical_name="Idaho",
                short_name="Idaho",
                institution="University of Idaho",
                is_idaho=True,
            )
        )

    existing_keys = set(
        await session.scalars(
            select(StatDefinition.stat_key).where(
                StatDefinition.sport_program_id == program.id,
                StatDefinition.entity_scope == "player",
            )
        )
    )
    for definition in WBB_STAT_DEFINITIONS:
        if definition["stat_key"] in existing_keys:
            continue
        definition_values = {
            "value_type": "integer",
            "aggregation_method": "sum",
            "display_format": "0",
            **definition,
        }
        session.add(
            StatDefinition(
                sport_program_id=program.id,
                entity_scope="player",
                **definition_values,
            )
        )
