"""Persist parsed WBB player rows as normalized player-game facts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, SourceSnapshot
from app.models.player_game_stat import PlayerGameStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.player_identity import PlayerIdentityRow, resolve_player_identity
from app.services.sidearm_scraper import ParsedBoxscore

WBB_PROGRAM_SLUG = "womens-basketball"
IDAHO_TEAM_SLUG = "idaho"
IDAHO_INSTITUTION = "University of Idaho"


@dataclass(frozen=True)
class PlayerGameStatImportResult:
    """Counts produced by one normalized WBB boxscore replacement."""

    player_rows_seen: int
    player_rows_resolved: int
    player_rows_unresolved: int
    facts_written: int


async def replace_wbb_player_game_stats(
    db: AsyncSession,
    *,
    game: Game,
    snapshot: SourceSnapshot,
    parsed: ParsedBoxscore,
) -> PlayerGameStatImportResult:
    """Replace one WBB game's normalized facts from its latest source snapshot."""
    if parsed.sport != WBB_PROGRAM_SLUG:
        raise ValueError("Normalized player-game import currently supports WBB only")
    if not parsed.season:
        raise ValueError(
            "WBB boxscore season is required for player identity resolution"
        )
    if game.id is None or snapshot.id is None:
        raise ValueError("Game and source snapshot must be flushed before fact import")

    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == WBB_PROGRAM_SLUG)
    )
    if program is None:
        raise ValueError("Women's basketball warehouse reference data is missing")
    idaho_team = await db.scalar(select(Team).where(Team.slug == IDAHO_TEAM_SLUG))
    if idaho_team is None:
        raise ValueError("Idaho team warehouse reference data is missing")

    definitions = {
        definition.stat_key: definition
        for definition in await db.scalars(
            select(StatDefinition).where(
                StatDefinition.sport_program_id == program.id,
                StatDefinition.entity_scope == "player",
            )
        )
    }
    parsed_stat_keys = {
        stat_key
        for source_row in parsed.player_stat_rows
        for stat_key in _stats(source_row)
    }
    missing_definitions = sorted(parsed_stat_keys - definitions.keys())
    if missing_definitions:
        raise ValueError(
            "Missing WBB stat definitions: " + ", ".join(missing_definitions)
        )

    await db.execute(delete(PlayerGameStat).where(PlayerGameStat.game_id == game.id))

    resolved_rows = 0
    unresolved_rows = 0
    facts_written = 0
    for source_row in parsed.player_stat_rows:
        player_name = str(source_row.get("player_name") or "").strip()
        if not player_name:
            raise ValueError("Parsed WBB player row is missing a player name")
        is_idaho = bool(source_row.get("is_idaho"))
        team_name = str(source_row.get("team") or "").strip()
        institution = (
            idaho_team.institution or IDAHO_INSTITUTION
            if is_idaho
            else team_name or "Unknown opponent"
        )
        identity = await resolve_player_identity(
            db,
            PlayerIdentityRow(
                sport_program_id=program.id,
                source_system=game.source_system,
                institution=institution,
                season=parsed.season,
                player_name=player_name,
                jersey_number=_optional_text(source_row.get("jersey_number")),
                source_player_id=_optional_text(source_row.get("source_player_id")),
                source_url=(
                    _optional_text(source_row.get("player_bio_url"))
                    or parsed.source_url
                ),
                game_id=game.id,
                team_id=idaho_team.id if is_idaho else None,
                source_snapshot_id=snapshot.id,
            ),
        )
        if identity.player_id is None:
            unresolved_rows += 1
            continue

        resolved_rows += 1
        source_values = source_row.get("source_values")
        if not isinstance(source_values, dict):
            source_values = {}
        for stat_key, value in _stats(source_row).items():
            definition = definitions[stat_key]
            source_field = _source_field(definition, source_values)
            source_value = source_values.get(source_field) if source_field else value
            db.add(
                PlayerGameStat(
                    game_id=game.id,
                    player_id=identity.player_id,
                    team_id=idaho_team.id if is_idaho else None,
                    stat_definition_id=definition.id,
                    source_snapshot_id=snapshot.id,
                    value=Decimal(str(value)),
                    source_field=source_field,
                    source_value=str(source_value),
                )
            )
            facts_written += 1

    await db.flush()
    return PlayerGameStatImportResult(
        player_rows_seen=len(parsed.player_stat_rows),
        player_rows_resolved=resolved_rows,
        player_rows_unresolved=unresolved_rows,
        facts_written=facts_written,
    )


def _stats(source_row: dict) -> dict[str, int]:
    stats = source_row.get("stats")
    if not isinstance(stats, dict):
        raise ValueError("Parsed WBB player row is missing atomic stats")
    return stats


def _source_field(
    definition: StatDefinition,
    source_values: dict,
) -> str | None:
    return next(
        (alias for alias in definition.source_field_aliases if alias in source_values),
        None,
    )


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
