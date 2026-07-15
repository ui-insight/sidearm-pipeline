"""Deterministic player identity resolution with a human review fallback."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_quality_issue import DataQualityIssue
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_identity_resolution import PlayerIdentityResolution

ResolutionMethod = Literal[
    "source_player_id",
    "manual_resolution",
    "roster_name_jersey",
    "unresolved",
]


@dataclass(frozen=True)
class PlayerIdentityRow:
    """Identity-bearing fields from one parsed player-stat source row."""

    sport_program_id: int
    source_system: str
    institution: str
    season: str
    player_name: str
    jersey_number: str | None = None
    source_player_id: str | None = None
    source_url: str | None = None
    game_id: int | None = None
    team_id: int | None = None
    source_snapshot_id: int | None = None


@dataclass(frozen=True)
class PlayerIdentityMatch:
    """The canonical result or review-queue item for one source row."""

    player_id: int | None
    method: ResolutionMethod
    issue_id: int | None = None


async def resolve_player_identity(
    db: AsyncSession,
    row: PlayerIdentityRow,
) -> PlayerIdentityMatch:
    """Resolve a source row without guessing when identity evidence is ambiguous."""
    source_system = row.source_system.strip().casefold()
    institution = row.institution.strip()
    source_player_id = _clean_optional(row.source_player_id)
    normalized_name = normalize_player_name(row.player_name)
    jersey_number = normalize_jersey_number(row.jersey_number)
    match_key = identity_match_key(
        sport_program_id=row.sport_program_id,
        source_system=source_system,
        institution=institution,
        season=row.season,
        source_player_id=source_player_id,
        normalized_name=normalized_name,
        jersey_number=jersey_number,
    )

    if source_player_id:
        external_identity = await db.scalar(
            select(PlayerExternalIdentity).where(
                PlayerExternalIdentity.source_system == source_system,
                PlayerExternalIdentity.institution == institution,
                PlayerExternalIdentity.source_player_id == source_player_id,
            )
        )
        if external_identity is not None:
            return PlayerIdentityMatch(
                player_id=external_identity.player_id,
                method="source_player_id",
            )

    manual_resolution = await db.scalar(
        select(PlayerIdentityResolution).where(
            PlayerIdentityResolution.match_key == match_key
        )
    )
    if manual_resolution is not None:
        return PlayerIdentityMatch(
            player_id=manual_resolution.player_id,
            method="manual_resolution",
        )

    candidates = await _roster_candidates(
        db,
        sport_program_id=row.sport_program_id,
        season=row.season,
        normalized_name=normalized_name,
        jersey_number=jersey_number,
    )
    if len(candidates) == 1:
        return PlayerIdentityMatch(
            player_id=candidates[0],
            method="roster_name_jersey",
        )

    reason = "ambiguous" if candidates else "unmatched"
    issue = await _upsert_unresolved_issue(
        db,
        row=row,
        source_system=source_system,
        institution=institution,
        source_player_id=source_player_id,
        normalized_name=normalized_name,
        jersey_number=jersey_number,
        match_key=match_key,
        reason=reason,
        candidate_player_ids=candidates,
    )
    return PlayerIdentityMatch(
        player_id=None,
        method="unresolved",
        issue_id=issue.id,
    )


async def resolve_identity_issue(
    db: AsyncSession,
    *,
    issue_id: int,
    player_id: int,
    resolution_notes: str,
) -> PlayerIdentityResolution:
    """Apply a human queue decision and persist it for future source rows."""
    issue = await db.get(DataQualityIssue, issue_id)
    if issue is None or issue.issue_type != "unresolved_identity":
        raise LookupError(f"Unresolved identity issue {issue_id} was not found")
    player = await db.get(Player, player_id)
    if player is None:
        raise LookupError(f"Player {player_id} was not found")

    details = issue.details or {}
    source_system = str(details.get("source_system") or "sidearm").strip().casefold()
    institution = str(details.get("institution") or "").strip()
    season = str(details.get("season") or "").strip()
    player_name = str(details.get("player_name") or details.get("display_name") or "")
    source_player_id = _clean_optional(details.get("source_player_id"))
    normalized_name = str(details.get("normalized_name") or "")
    normalized_name = normalized_name or normalize_player_name(player_name)
    jersey_number = normalize_jersey_number(details.get("jersey_number"))
    match_key = str(details.get("match_key") or "")
    match_key = match_key or identity_match_key(
        sport_program_id=issue.sport_program_id,
        source_system=source_system,
        institution=institution,
        season=season,
        source_player_id=source_player_id,
        normalized_name=normalized_name,
        jersey_number=jersey_number,
    )

    if source_player_id:
        external_identity = await db.scalar(
            select(PlayerExternalIdentity).where(
                PlayerExternalIdentity.source_system == source_system,
                PlayerExternalIdentity.institution == institution,
                PlayerExternalIdentity.source_player_id == source_player_id,
            )
        )
        if external_identity is not None and external_identity.player_id != player.id:
            raise ValueError(
                "The source player id already belongs to a different canonical player"
            )
        if external_identity is None:
            db.add(
                PlayerExternalIdentity(
                    player_id=player.id,
                    source_system=source_system,
                    institution=institution,
                    source_player_id=source_player_id,
                    source_url=_clean_optional(details.get("source_url")),
                )
            )

    resolution = await db.scalar(
        select(PlayerIdentityResolution).where(
            PlayerIdentityResolution.match_key == match_key
        )
    )
    now = datetime.now(UTC)
    if resolution is None:
        resolution = PlayerIdentityResolution(
            match_key=match_key,
            sport_program_id=issue.sport_program_id,
            player_id=player.id,
            source_system=source_system,
            institution=institution,
            season=season,
            source_player_id=source_player_id,
            normalized_name=normalized_name,
            jersey_number=jersey_number,
            created_from_issue_id=issue.id,
            resolution_notes=resolution_notes,
            created_at=now,
            updated_at=now,
        )
        db.add(resolution)
    else:
        resolution.player_id = player.id
        resolution.created_from_issue_id = issue.id
        resolution.resolution_notes = resolution_notes
        resolution.updated_at = now

    issue.player_id = player.id
    issue.status = "resolved"
    issue.resolved_at = now
    issue.resolution_notes = resolution_notes
    await db.flush()
    return resolution


def normalize_player_name(value: str) -> str:
    """Normalize exact display-name variants without fuzzy similarity matching."""
    text = value.strip()
    if "," in text:
        last_name, remainder = text.split(",", maxsplit=1)
        text = f"{remainder.strip()} {last_name.strip()}"
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_marks.casefold()))


def normalize_jersey_number(value: object | None) -> str | None:
    """Normalize numeric jersey padding while retaining non-numeric labels."""
    cleaned = _clean_optional(value)
    if cleaned is None:
        return None
    return str(int(cleaned)) if cleaned.isdigit() else cleaned.casefold()


def identity_match_key(
    *,
    sport_program_id: int,
    source_system: str,
    institution: str,
    season: str,
    source_player_id: str | None,
    normalized_name: str,
    jersey_number: str | None,
) -> str:
    """Build a stable key for exact source-id or season-signature decisions."""
    if source_player_id:
        values = ("source-id", source_system, institution, source_player_id)
    else:
        values = (
            "season-signature",
            source_system,
            institution,
            str(sport_program_id),
            season,
            normalized_name,
            jersey_number or "",
        )
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()


async def _roster_candidates(
    db: AsyncSession,
    *,
    sport_program_id: int,
    season: str,
    normalized_name: str,
    jersey_number: str | None,
) -> list[int]:
    if not normalized_name or jersey_number is None:
        return []
    rows = (
        await db.execute(
            select(PlayerSeason, Player)
            .join(Player, Player.id == PlayerSeason.player_id)
            .where(
                PlayerSeason.sport_program_id == sport_program_id,
                PlayerSeason.season == season,
            )
        )
    ).all()
    return sorted(
        player.id
        for player_season, player in rows
        if normalize_player_name(player.display_name) == normalized_name
        and normalize_jersey_number(player_season.jersey_number) == jersey_number
    )


async def _upsert_unresolved_issue(
    db: AsyncSession,
    *,
    row: PlayerIdentityRow,
    source_system: str,
    institution: str,
    source_player_id: str | None,
    normalized_name: str,
    jersey_number: str | None,
    match_key: str,
    reason: str,
    candidate_player_ids: list[int],
) -> DataQualityIssue:
    deduplication_key = f"identity:{match_key}"
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    details = {
        "reason": reason,
        "match_key": match_key,
        "source_system": source_system,
        "institution": institution,
        "season": row.season,
        "source_player_id": source_player_id,
        "player_name": row.player_name,
        "normalized_name": normalized_name,
        "jersey_number": jersey_number,
        "source_url": row.source_url,
        "candidate_player_ids": candidate_player_ids,
    }
    summary = (
        f"Player row {row.player_name!r} is ambiguous within the {row.season} roster"
        if reason == "ambiguous"
        else f"Player row {row.player_name!r} did not match the {row.season} roster"
    )
    if issue is None:
        issue = DataQualityIssue(
            sport_program_id=row.sport_program_id,
            game_id=row.game_id,
            team_id=row.team_id,
            source_snapshot_id=row.source_snapshot_id,
            deduplication_key=deduplication_key,
            issue_type="unresolved_identity",
            status="open",
            severity="warning",
            summary=summary,
            details=details,
        )
        db.add(issue)
    else:
        issue.game_id = row.game_id
        issue.team_id = row.team_id
        issue.source_snapshot_id = row.source_snapshot_id
        issue.status = "open"
        issue.player_id = None
        issue.summary = summary
        issue.details = details
        issue.resolved_at = None
        issue.resolution_notes = None
    await db.flush()
    return issue


def _clean_optional(value: object | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
