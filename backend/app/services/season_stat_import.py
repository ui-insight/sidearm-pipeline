"""Persist cumulative season facts and reconcile them to game-grain facts."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import Game, SourceSnapshot
from app.models.player import PlayerExternalIdentity, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import Team
from app.services.sidearm_cumulative_stats import (
    CUMULATIVE_STATS_PARSER_VERSION,
    ParsedCumulativePlayer,
    ParsedCumulativeStats,
)


@dataclass(frozen=True)
class CumulativeStatsImportResult:
    """Counts, provenance, and trust state produced by one season import."""

    source_url: str
    season: str
    source_snapshot_id: int
    players_seen: int
    players_resolved: int
    players_unresolved: int
    source_conflicts: int
    facts_written: int
    comparisons_run: int
    facts_matched: int
    facts_mismatched: int
    coverage_gaps: int
    quality_issues_created: int
    quality_issues_resolved: int
    coverage_completeness: str
    coverage_window_ids: list[int]


@dataclass(frozen=True)
class ParserFailureResult:
    """Persisted evidence for one cumulative-source parser failure."""

    source_snapshot_id: int
    quality_issue_id: int


async def import_cumulative_stats(
    db: AsyncSession,
    source: ParsedCumulativeStats,
) -> CumulativeStatsImportResult:
    """Replace resolved season facts and reconcile complete player coverage."""
    program, team = await _warehouse_context(db, source)
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
        stat_key for player in source.players for stat_key in player.stats
    }
    missing_definitions = sorted(parsed_stat_keys - definitions.keys())
    if missing_definitions:
        raise ValueError(
            "Missing cumulative stat definitions: " + ", ".join(missing_definitions)
        )

    snapshot = SourceSnapshot(
        game_id=None,
        source_system=source.source_system,
        source_type="cumulative_stats_html",
        source_url=source.source_url,
        parser_version=CUMULATIVE_STATS_PARSER_VERSION,
        content_hash=hashlib.sha256(source.raw_html.encode("utf-8")).hexdigest(),
        http_status=source.http_status,
        raw_body=source.raw_html,
    )
    db.add(snapshot)
    await db.flush()

    issue_counts = {"created": 0, "resolved": 0}
    unresolved = 0
    source_conflicts = 0
    grouped_rows: dict[str, list[ParsedCumulativePlayer]] = defaultdict(list)
    for player_row in source.players:
        if player_row.source_player_id is None:
            unresolved += 1
            issue_counts["created"] += await _upsert_source_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                source=source,
                player_row=player_row,
                issue_type="unresolved_identity",
                stable_identity=player_row.display_name.casefold(),
                summary=(
                    f"Cumulative row for {player_row.display_name} has no "
                    "Sidearm player identity"
                ),
            )
            continue
        grouped_rows[player_row.source_player_id].append(player_row)

    resolved: list[tuple[ParsedCumulativePlayer, PlayerSeason]] = []
    for source_player_id, rows in grouped_rows.items():
        if len(rows) > 1:
            source_conflicts += 1
            issue_counts["created"] += await _upsert_source_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                source=source,
                player_row=rows[0],
                issue_type="source_conflict",
                stable_identity=source_player_id,
                summary=(
                    f"Cumulative source contains {len(rows)} rows for Sidearm "
                    f"player {source_player_id}"
                ),
                rows=rows,
            )
            continue

        player_row = rows[0]
        identity = await db.scalar(
            select(PlayerExternalIdentity).where(
                PlayerExternalIdentity.source_system == source.identity_source_system,
                PlayerExternalIdentity.institution == source.institution,
                PlayerExternalIdentity.source_player_id == source_player_id,
            )
        )
        if identity is None:
            unresolved += 1
            issue_counts["created"] += await _upsert_source_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                source=source,
                player_row=player_row,
                issue_type="unresolved_identity",
                stable_identity=source_player_id,
                summary=(
                    f"Cumulative player {player_row.display_name} has no canonical "
                    "Sidearm identity"
                ),
            )
            continue

        player_season = await db.scalar(
            select(PlayerSeason).where(
                PlayerSeason.player_id == identity.player_id,
                PlayerSeason.sport_program_id == program.id,
                PlayerSeason.season == source.season,
            )
        )
        if player_season is None:
            unresolved += 1
            issue_counts["created"] += await _upsert_source_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                source=source,
                player_row=player_row,
                issue_type="unresolved_identity",
                stable_identity=source_player_id,
                player_id=identity.player_id,
                summary=(
                    f"Cumulative player {player_row.display_name} has no canonical "
                    f"PlayerSeason for {source.season}"
                ),
            )
            continue

        resolved.append((player_row, player_season))

    resolved_season_ids = [player_season.id for _, player_season in resolved]
    if resolved_season_ids:
        await db.execute(
            delete(PlayerSeasonStat).where(
                PlayerSeasonStat.player_season_id.in_(resolved_season_ids)
            )
        )

    facts_written = 0
    for player_row, player_season in resolved:
        for stat_key, value in player_row.stats.items():
            definition = definitions[stat_key]
            source_field = player_row.source_fields[stat_key]
            db.add(
                PlayerSeasonStat(
                    player_season_id=player_season.id,
                    stat_definition_id=definition.id,
                    source_snapshot_id=snapshot.id,
                    value=value,
                    source_field=source_field,
                    source_value=player_row.source_values.get(source_field),
                )
            )
            facts_written += 1
    await db.flush()

    reconciliation = await _reconcile(
        db,
        program=program,
        team=team,
        snapshot=snapshot,
        source=source,
        definitions=definitions,
        resolved=resolved,
    )
    issue_counts["created"] += reconciliation.quality_issues_created
    issue_counts["resolved"] += reconciliation.quality_issues_resolved

    coverage_completeness = (
        "complete"
        if unresolved == 0
        and source_conflicts == 0
        and reconciliation.coverage_gaps == 0
        else "partial"
    )
    coverage_windows = await _upsert_coverage_windows(
        db,
        program=program,
        source=source,
        definitions=definitions,
        parsed_stat_keys=parsed_stat_keys,
        completeness=coverage_completeness,
    )
    await db.commit()
    return CumulativeStatsImportResult(
        source_url=source.source_url,
        season=source.season,
        source_snapshot_id=snapshot.id,
        players_seen=len(source.players),
        players_resolved=len(resolved),
        players_unresolved=unresolved,
        source_conflicts=source_conflicts,
        facts_written=facts_written,
        comparisons_run=reconciliation.comparisons_run,
        facts_matched=reconciliation.facts_matched,
        facts_mismatched=reconciliation.facts_mismatched,
        coverage_gaps=reconciliation.coverage_gaps,
        quality_issues_created=issue_counts["created"],
        quality_issues_resolved=issue_counts["resolved"],
        coverage_completeness=coverage_completeness,
        coverage_window_ids=[window.id for window in coverage_windows],
    )


async def record_cumulative_parser_failure(
    db: AsyncSession,
    *,
    sport_program_slug: str,
    season: str,
    source_url: str,
    raw_html: str,
    http_status: int,
    error: str,
) -> ParserFailureResult:
    """Persist upstream markup drift as replayable, reviewable evidence."""
    source = ParsedCumulativeStats(
        sport_program_slug=sport_program_slug,
        season=season,
        source_system="govandals_public_html",
        identity_source_system="sidearm",
        institution="University of Idaho",
        team_slug="idaho",
        source_url=source_url,
        raw_html=raw_html,
        http_status=http_status,
    )
    program, team = await _warehouse_context(db, source)
    snapshot = SourceSnapshot(
        game_id=None,
        source_system=source.source_system,
        source_type="cumulative_stats_html",
        source_url=source_url,
        parser_version=CUMULATIVE_STATS_PARSER_VERSION,
        content_hash=hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
        http_status=http_status,
        raw_body=raw_html,
    )
    db.add(snapshot)
    await db.flush()
    key = f"cumulative-parser:{program.slug}:{season}"
    issue = await db.scalar(
        select(DataQualityIssue).where(DataQualityIssue.deduplication_key == key)
    )
    details = {
        "season": season,
        "source_url": source_url,
        "http_status": http_status,
        "parser_version": CUMULATIVE_STATS_PARSER_VERSION,
        "error": error,
    }
    if issue is None:
        issue = DataQualityIssue(
            sport_program_id=program.id,
            team_id=team.id,
            source_snapshot_id=snapshot.id,
            deduplication_key=key,
            issue_type="parser_failure",
            status="open",
            severity="error",
            summary=f"Cumulative stats parser failed for {season}",
            details=details,
        )
        db.add(issue)
    else:
        issue.source_snapshot_id = snapshot.id
        issue.status = "open"
        issue.resolved_at = None
        issue.details = details
    await db.commit()
    return ParserFailureResult(
        source_snapshot_id=snapshot.id,
        quality_issue_id=issue.id,
    )


@dataclass(frozen=True)
class _ReconciliationResult:
    comparisons_run: int = 0
    facts_matched: int = 0
    facts_mismatched: int = 0
    coverage_gaps: int = 0
    quality_issues_created: int = 0
    quality_issues_resolved: int = 0


async def _reconcile(
    db: AsyncSession,
    *,
    program: SportProgram,
    team: Team,
    snapshot: SourceSnapshot,
    source: ParsedCumulativeStats,
    definitions: dict[str, StatDefinition],
    resolved: list[tuple[ParsedCumulativePlayer, PlayerSeason]],
) -> _ReconciliationResult:
    if not resolved:
        return _ReconciliationResult()
    player_ids = [player_season.player_id for _, player_season in resolved]
    game_counts = dict(
        (
            await db.execute(
                select(
                    PlayerGameStat.player_id,
                    func.count(func.distinct(PlayerGameStat.game_id)),
                )
                .join(Game, Game.id == PlayerGameStat.game_id)
                .where(
                    PlayerGameStat.player_id.in_(player_ids),
                    Game.sport == program.slug,
                    Game.season == source.season,
                    Game.event_status == "final",
                )
                .group_by(PlayerGameStat.player_id)
            )
        ).all()
    )
    game_sums = {
        (player_id, definition_id): total
        for player_id, definition_id, total in (
            await db.execute(
                select(
                    PlayerGameStat.player_id,
                    PlayerGameStat.stat_definition_id,
                    func.sum(PlayerGameStat.value),
                )
                .join(Game, Game.id == PlayerGameStat.game_id)
                .where(
                    PlayerGameStat.player_id.in_(player_ids),
                    Game.sport == program.slug,
                    Game.season == source.season,
                    Game.event_status == "final",
                )
                .group_by(
                    PlayerGameStat.player_id,
                    PlayerGameStat.stat_definition_id,
                )
            )
        ).all()
    }

    comparisons = 0
    matched = 0
    mismatched = 0
    coverage_gaps = 0
    created = 0
    resolved_count = 0
    for player_row, player_season in resolved:
        observed_games = int(game_counts.get(player_season.player_id, 0))
        coverage_key = _coverage_gap_key(program, source, player_season)
        if observed_games < player_row.games_played:
            coverage_gaps += 1
            created += await _upsert_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                player_season=player_season,
                deduplication_key=coverage_key,
                issue_type="coverage_gap",
                severity="warning",
                summary=(
                    f"{player_row.display_name} has {observed_games} of "
                    f"{player_row.games_played} season games in warehouse history"
                ),
                details={
                    "player": player_row.display_name,
                    "season": source.season,
                    "expected_games": player_row.games_played,
                    "observed_games": observed_games,
                    "source_url": source.source_url,
                    "source_snapshot_id": snapshot.id,
                },
            )
            resolved_count += await _resolve_player_mismatches(
                db,
                program=program,
                source=source,
                player_season=player_season,
            )
            continue

        resolved_count += await _resolve_issue(db, coverage_key)
        for stat_key, season_total in player_row.stats.items():
            definition = definitions[stat_key]
            if definition.aggregation_method != "sum":
                continue
            comparisons += 1
            game_sum = game_sums.get(
                (player_season.player_id, definition.id), Decimal("0")
            )
            mismatch_key = _mismatch_key(program, source, player_season, definition)
            difference = season_total - game_sum
            if difference == 0:
                matched += 1
                resolved_count += await _resolve_issue(db, mismatch_key)
                continue

            mismatched += 1
            created += await _upsert_issue(
                db,
                program=program,
                team=team,
                snapshot=snapshot,
                player_season=player_season,
                definition=definition,
                deduplication_key=mismatch_key,
                issue_type="reconciliation_mismatch",
                severity="error",
                summary=(
                    f"{player_row.display_name} {definition.display_label} does "
                    f"not reconcile for {source.season}"
                ),
                details={
                    "player": player_row.display_name,
                    "season": source.season,
                    "stat_key": definition.stat_key,
                    "season_total": str(season_total),
                    "game_sum": str(game_sum),
                    "difference": str(difference),
                    "source_field": player_row.source_fields[stat_key],
                    "source_value": player_row.source_values.get(
                        player_row.source_fields[stat_key]
                    ),
                    "source_url": source.source_url,
                    "source_snapshot_id": snapshot.id,
                },
            )

    return _ReconciliationResult(
        comparisons_run=comparisons,
        facts_matched=matched,
        facts_mismatched=mismatched,
        coverage_gaps=coverage_gaps,
        quality_issues_created=created,
        quality_issues_resolved=resolved_count,
    )


async def _upsert_coverage_windows(
    db: AsyncSession,
    *,
    program: SportProgram,
    source: ParsedCumulativeStats,
    definitions: dict[str, StatDefinition],
    parsed_stat_keys: set[str],
    completeness: str,
) -> list[CoverageWindow]:
    now = datetime.now(UTC)
    limitations = "public HTML fallback; source authority pending."
    if completeness == "partial":
        limitations += " Some identities or game-grain coverage remain unresolved."
    windows: list[CoverageWindow] = []
    for stat_key in sorted(parsed_stat_keys):
        definition = definitions[stat_key]
        window = await db.scalar(
            select(CoverageWindow).where(
                CoverageWindow.sport_program_id == program.id,
                CoverageWindow.stat_definition_id == definition.id,
                CoverageWindow.grain == "season",
                CoverageWindow.source_system == source.source_system,
                CoverageWindow.first_season == source.season,
                CoverageWindow.last_season == source.season,
            )
        )
        if window is None:
            window = CoverageWindow(
                sport_program_id=program.id,
                stat_definition_id=definition.id,
                grain="season",
                source_system=source.source_system,
                first_season=source.season,
                last_season=source.season,
                completeness=completeness,
            )
            db.add(window)
        else:
            window.completeness = completeness
        window.known_limitations = limitations
        window.verified_at = now if window.completeness == "complete" else None
        window.updated_at = now
        windows.append(window)
    await db.flush()
    return windows


async def _warehouse_context(
    db: AsyncSession,
    source: ParsedCumulativeStats,
) -> tuple[SportProgram, Team]:
    program = await db.scalar(
        select(SportProgram).where(SportProgram.slug == source.sport_program_slug)
    )
    if program is None:
        raise ValueError(f"Unknown sport program '{source.sport_program_slug}'")
    team = await db.scalar(select(Team).where(Team.slug == source.team_slug))
    if team is None:
        raise ValueError(f"Unknown team '{source.team_slug}'")
    return program, team


async def _upsert_source_issue(
    db: AsyncSession,
    *,
    program: SportProgram,
    team: Team,
    snapshot: SourceSnapshot,
    source: ParsedCumulativeStats,
    player_row: ParsedCumulativePlayer,
    issue_type: str,
    stable_identity: str,
    summary: str,
    player_id: int | None = None,
    rows: list[ParsedCumulativePlayer] | None = None,
) -> int:
    digest = hashlib.sha256(
        "|".join(
            (
                issue_type,
                program.slug,
                source.season,
                stable_identity,
            )
        ).encode("utf-8")
    ).hexdigest()
    details = {
        "season": source.season,
        "source_url": source.source_url,
        "source_snapshot_id": snapshot.id,
        "player": player_row.display_name,
        "jersey_number": player_row.jersey_number,
        "source_player_id": player_row.source_player_id,
        "bio_url": player_row.bio_url,
        "rows": [_row_details(row) for row in rows or [player_row]],
    }
    return await _upsert_issue(
        db,
        program=program,
        team=team,
        snapshot=snapshot,
        player_id=player_id,
        deduplication_key=f"cumulative-source:{digest}",
        issue_type=issue_type,
        severity="error" if issue_type == "source_conflict" else "warning",
        summary=summary,
        details=details,
    )


async def _upsert_issue(
    db: AsyncSession,
    *,
    program: SportProgram,
    team: Team,
    snapshot: SourceSnapshot,
    deduplication_key: str,
    issue_type: str,
    severity: str,
    summary: str,
    details: dict,
    player_season: PlayerSeason | None = None,
    player_id: int | None = None,
    definition: StatDefinition | None = None,
) -> int:
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    if issue is None:
        issue = DataQualityIssue(
            sport_program_id=program.id,
            team_id=team.id,
            player_id=(player_season.player_id if player_season else player_id),
            stat_definition_id=definition.id if definition else None,
            source_snapshot_id=snapshot.id,
            deduplication_key=deduplication_key,
            issue_type=issue_type,
            status="open",
            severity=severity,
            summary=summary,
            details=details,
        )
        db.add(issue)
        return 1

    issue.source_snapshot_id = snapshot.id
    issue.summary = summary
    issue.details = details
    issue.severity = severity
    if issue.status == "resolved":
        issue.status = "open"
        issue.resolved_at = None
        issue.resolution_notes = None
    return 0


async def _resolve_issue(db: AsyncSession, deduplication_key: str) -> int:
    issue = await db.scalar(
        select(DataQualityIssue).where(
            DataQualityIssue.deduplication_key == deduplication_key
        )
    )
    if issue is None or issue.status not in {"open", "in_review"}:
        return 0
    issue.status = "resolved"
    issue.resolved_at = datetime.now(UTC)
    issue.resolution_notes = "Resolved by a clean cumulative-season import."
    return 1


async def _resolve_player_mismatches(
    db: AsyncSession,
    *,
    program: SportProgram,
    source: ParsedCumulativeStats,
    player_season: PlayerSeason,
) -> int:
    issues = list(
        await db.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.sport_program_id == program.id,
                DataQualityIssue.player_id == player_season.player_id,
                DataQualityIssue.issue_type == "reconciliation_mismatch",
                DataQualityIssue.status.in_(("open", "in_review")),
            )
        )
    )
    now = datetime.now(UTC)
    for issue in issues:
        if issue.details.get("season") != source.season:
            continue
        issue.status = "resolved"
        issue.resolved_at = now
        issue.resolution_notes = (
            "Deferred because game-grain coverage is currently incomplete."
        )
    return sum(issue.details.get("season") == source.season for issue in issues)


def _coverage_gap_key(
    program: SportProgram,
    source: ParsedCumulativeStats,
    player_season: PlayerSeason,
) -> str:
    return f"season-coverage:{program.id}:{source.season}:{player_season.player_id}"


def _mismatch_key(
    program: SportProgram,
    source: ParsedCumulativeStats,
    player_season: PlayerSeason,
    definition: StatDefinition,
) -> str:
    return (
        f"season-reconcile:{program.id}:{source.season}:"
        f"{player_season.player_id}:{definition.id}"
    )


def _row_details(player_row: ParsedCumulativePlayer) -> dict:
    return {
        "games_played": player_row.games_played,
        "games_started": player_row.games_started,
        "stats": {key: str(value) for key, value in player_row.stats.items()},
        "source_values": player_row.source_values,
    }
