"""Persist Sidearm roster identities into the normalized warehouse."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_quality_issue import DataQualityIssue
from app.models.game import SourceSnapshot
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.sport_program import SportProgram
from app.models.team import Team
from app.services.sidearm_roster import (
    ROSTER_PARSER_VERSION,
    ParsedRoster,
    ParsedRosterPlayer,
)


@dataclass(frozen=True)
class RosterImportResult:
    """Counts and provenance produced by one roster import."""

    source_url: str
    season: str
    source_snapshot_id: int
    players_seen: int
    players_created: int
    identities_created: int
    player_seasons_created: int
    player_seasons_updated: int
    quality_issues_created: int


async def import_roster(
    db: AsyncSession,
    roster: ParsedRoster,
) -> RosterImportResult:
    """Idempotently import exact roster identities and season memberships."""
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == roster.sport_program_slug)
    )
    if program is None:
        raise ValueError(f"Unknown sport program '{roster.sport_program_slug}'")
    team = await db.scalar(select(Team).where(Team.slug == roster.team_slug))
    if team is None:
        raise ValueError(f"Unknown team '{roster.team_slug}'")

    snapshot = SourceSnapshot(
        game_id=None,
        source_system=roster.source_system,
        source_type="roster_html",
        source_url=roster.source_url,
        parser_version=ROSTER_PARSER_VERSION,
        content_hash=hashlib.sha256(roster.raw_html.encode("utf-8")).hexdigest(),
        http_status=roster.http_status,
        raw_body=roster.raw_html,
    )
    db.add(snapshot)
    await db.flush()

    players_created = 0
    identities_created = 0
    seasons_created = 0
    seasons_updated = 0
    issues_created = 0
    now = datetime.now(UTC)

    for roster_player in roster.players:
        identity_ids = _identity_ids(roster_player)
        if not identity_ids:
            issues_created += await _upsert_quality_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                roster=roster,
                roster_player=roster_player,
                issue_type="unresolved_identity",
                summary=(
                    f"Roster player {roster_player.display_name} has no usable "
                    "Sidearm identity"
                ),
            )
            continue

        identities = (
            await db.scalars(
                select(PlayerExternalIdentity).where(
                    PlayerExternalIdentity.source_system == roster.source_system,
                    PlayerExternalIdentity.institution == roster.institution,
                    PlayerExternalIdentity.source_player_id.in_(identity_ids),
                )
            )
        ).all()
        player_ids = {identity.player_id for identity in identities}
        if len(player_ids) > 1:
            issues_created += await _upsert_quality_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                roster=roster,
                roster_player=roster_player,
                issue_type="source_conflict",
                summary=(
                    f"Sidearm redirect identities for {roster_player.display_name} "
                    "map to different canonical players"
                ),
            )
            continue

        if player_ids:
            player = await db.get(Player, next(iter(player_ids)))
            assert player is not None
            player.display_name = roster_player.display_name
        else:
            player = Player(display_name=roster_player.display_name)
            db.add(player)
            await db.flush()
            players_created += 1

        identity_by_id = {
            identity.source_player_id: identity for identity in identities
        }
        for source_player_id, source_url in _identity_sources(roster_player):
            identity = identity_by_id.get(source_player_id)
            if identity is None:
                db.add(
                    PlayerExternalIdentity(
                        player_id=player.id,
                        source_system=roster.source_system,
                        institution=roster.institution,
                        source_player_id=source_player_id,
                        source_url=source_url,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
                identities_created += 1
            else:
                identity.source_url = source_url or identity.source_url
                identity.last_seen_at = now

        player_season = await db.scalar(
            select(PlayerSeason).where(
                PlayerSeason.player_id == player.id,
                PlayerSeason.sport_program_id == program.id,
                PlayerSeason.season == roster.season,
            )
        )
        if player_season is None:
            player_season = PlayerSeason(
                player_id=player.id,
                sport_program_id=program.id,
                season=roster.season,
            )
            db.add(player_season)
            seasons_created += 1
        else:
            seasons_updated += 1

        player_season.team_id = team.id
        player_season.source_snapshot_id = snapshot.id
        player_season.jersey_number = roster_player.jersey_number
        player_season.class_year = roster_player.class_year
        player_season.position = roster_player.position
        player_season.bio_url = roster_player.canonical_bio_url or roster_player.bio_url

    await db.commit()
    return RosterImportResult(
        source_url=roster.source_url,
        season=roster.season,
        source_snapshot_id=snapshot.id,
        players_seen=len(roster.players),
        players_created=players_created,
        identities_created=identities_created,
        player_seasons_created=seasons_created,
        player_seasons_updated=seasons_updated,
        quality_issues_created=issues_created,
    )


def _identity_ids(roster_player: ParsedRosterPlayer) -> list[str]:
    return list(
        dict.fromkeys(
            source_player_id
            for source_player_id in (
                roster_player.source_player_id,
                roster_player.canonical_source_player_id,
            )
            if source_player_id
        )
    )


def _identity_sources(
    roster_player: ParsedRosterPlayer,
) -> list[tuple[str, str | None]]:
    sources: dict[str, str | None] = {}
    if roster_player.source_player_id:
        sources[roster_player.source_player_id] = roster_player.bio_url
    if roster_player.canonical_source_player_id:
        sources[roster_player.canonical_source_player_id] = (
            roster_player.canonical_bio_url
        )
    return list(sources.items())


async def _upsert_quality_issue(
    db: AsyncSession,
    *,
    program: SportProgram,
    team: Team,
    snapshot: SourceSnapshot,
    roster: ParsedRoster,
    roster_player: ParsedRosterPlayer,
    issue_type: str,
    summary: str,
) -> int:
    deduplication_key = _quality_issue_key(issue_type, roster, roster_player)
    details = {
        "source_url": roster.source_url,
        "season": roster.season,
        "institution": roster.institution,
        "display_name": roster_player.display_name,
        "jersey_number": roster_player.jersey_number,
        "bio_url": roster_player.bio_url,
        "canonical_bio_url": roster_player.canonical_bio_url,
        "identity_resolution_error": roster_player.identity_resolution_error,
    }
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    if issue is not None:
        issue.source_snapshot_id = snapshot.id
        issue.summary = summary
        issue.details = details
        return 0

    db.add(
        DataQualityIssue(
            sport_program_id=program.id,
            team_id=team.id,
            source_snapshot_id=snapshot.id,
            deduplication_key=deduplication_key,
            issue_type=issue_type,
            status="open",
            severity="warning",
            summary=summary,
            details=details,
        )
    )
    return 1


def _quality_issue_key(
    issue_type: str,
    roster: ParsedRoster,
    roster_player: ParsedRosterPlayer,
) -> str:
    stable_identity = "|".join(
        (
            issue_type,
            roster.source_system,
            roster.institution,
            roster.sport_program_slug,
            roster.season,
            roster.source_url,
            roster_player.display_name.casefold(),
            roster_player.jersey_number or "",
        )
    )
    digest = hashlib.sha256(stable_identity.encode("utf-8")).hexdigest()
    return f"roster:{digest}"
