"""Reusable Sidearm boxscore ingestion for manual and scheduled workflows."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import (
    EventSource,
    EventStatusHistory,
    Game,
    IngestRun,
    PlayerStatGroup,
    ScoringPlay,
    SourceSnapshot,
    TeamStat,
)
from app.services.player_game_stat_import import replace_wbb_player_game_stats
from app.services.sidearm_scraper import (
    ParsedBoxscore,
    fetch_attempt_count,
    fetch_max_attempts,
    http_status_from_fetch_error,
    is_retryable_fetch_error,
    original_fetch_error_type,
    scrape_boxscore,
)
from app.services.source_registry import SportSource, get_source_registry

PARSER_VERSION = "sidearm-html-v2"
BoxscoreScraper = Callable[[str], Awaitable[ParsedBoxscore]]


async def ingest_boxscore(
    db: AsyncSession,
    url: str,
    *,
    trigger_type: str = "manual",
    scraper: BoxscoreScraper | None = None,
    preserve_schedule_metadata: bool = False,
) -> Game:
    """Fetch and idempotently persist one boxscore plus its ingest history."""
    started_at = datetime.now(UTC)
    ingest_run = IngestRun(
        trigger_type=trigger_type,
        source_system="sidearm",
        source_type="boxscore_html",
        source_url=url,
        status="running",
        started_at=started_at,
        run_metadata={"request_url": url},
    )
    db.add(ingest_run)
    await db.flush()

    fetch = scraper or scrape_boxscore
    try:
        parsed = await fetch(url)
    except httpx.HTTPError as exc:
        _finish_failed_ingest_run(ingest_run, started_at, exc)
        await db.commit()
        raise
    except Exception as exc:
        await _record_processing_failure(
            db,
            url=url,
            trigger_type=trigger_type,
            started_at=started_at,
            exc=exc,
        )
        raise

    registry_entry = _registry_entry_for(parsed)
    game = await _load_existing_game(db, parsed)
    if game is None:
        game = _build_game(parsed, registry_entry)
        db.add(game)
    else:
        _refresh_game(
            game,
            parsed,
            registry_entry,
            preserve_schedule_metadata=preserve_schedule_metadata,
        )

    await db.flush()
    normalized_result = None
    if parsed.sport == "womens-basketball":
        normalized_result = await replace_wbb_player_game_stats(
            db,
            game=game,
            snapshot=game.source_snapshots[-1],
            parsed=parsed,
        )

    _finish_successful_ingest_run(ingest_run, game, parsed, started_at)
    if normalized_result is not None:
        ingest_run.run_metadata = {
            **ingest_run.run_metadata,
            "normalized_player_rows_seen": normalized_result.player_rows_seen,
            "normalized_player_rows_resolved": normalized_result.player_rows_resolved,
            "normalized_player_rows_unresolved": (
                normalized_result.player_rows_unresolved
            ),
            "normalized_player_game_stats_written": normalized_result.facts_written,
        }
    await db.commit()
    await db.refresh(
        game,
        attribute_names=[
            "team_stats",
            "player_stats",
            "scoring_plays",
            "event_sources",
            "source_snapshots",
            "status_history",
            "generated_content",
        ],
    )
    return game


def _finish_successful_ingest_run(
    ingest_run: IngestRun,
    game: Game,
    parsed: ParsedBoxscore,
    started_at: datetime,
) -> None:
    finished_at = datetime.now(UTC)
    ingest_run.game = game
    ingest_run.source_event_id = _source_event_id(parsed.source_url)
    ingest_run.sport = parsed.sport
    ingest_run.season = parsed.season
    ingest_run.status = "succeeded"
    ingest_run.finished_at = finished_at
    ingest_run.duration_ms = _duration_ms(started_at, finished_at)
    ingest_run.attempt_count = parsed.fetch_attempt_count
    ingest_run.max_attempts = parsed.fetch_max_attempts
    ingest_run.http_status = 200
    ingest_run.retryable = False
    ingest_run.run_metadata = {
        "canonical_uid": _canonical_uid(parsed),
        "event_status": _event_status(parsed),
        "retryable_failures": parsed.fetch_retryable_failures,
        "parser_version": PARSER_VERSION,
        "publish_status": game.publish_status,
        "request_url": ingest_run.source_url,
    }


def _finish_failed_ingest_run(
    ingest_run: IngestRun,
    started_at: datetime,
    exc: httpx.HTTPError,
) -> None:
    finished_at = datetime.now(UTC)
    ingest_run.status = "failed"
    ingest_run.finished_at = finished_at
    ingest_run.duration_ms = _duration_ms(started_at, finished_at)
    ingest_run.attempt_count = fetch_attempt_count(exc)
    ingest_run.max_attempts = fetch_max_attempts(exc)
    ingest_run.http_status = http_status_from_fetch_error(exc)
    ingest_run.retryable = is_retryable_fetch_error(exc)
    ingest_run.error_type = original_fetch_error_type(exc)
    ingest_run.error_message = str(exc)
    ingest_run.run_metadata = {
        "request_url": ingest_run.source_url,
        "failure_phase": "fetch_boxscore",
        "retry_exhausted": (
            ingest_run.retryable and ingest_run.attempt_count >= ingest_run.max_attempts
        ),
    }


async def _record_processing_failure(
    db: AsyncSession,
    *,
    url: str,
    trigger_type: str,
    started_at: datetime,
    exc: Exception,
) -> None:
    await db.rollback()
    finished_at = datetime.now(UTC)
    db.add(
        IngestRun(
            trigger_type=trigger_type,
            source_system="sidearm",
            source_type="boxscore_html",
            source_url=url,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            error_type=type(exc).__name__,
            error_message=str(exc),
            run_metadata={
                "request_url": url,
                "failure_phase": "parse_boxscore",
            },
        )
    )
    await db.commit()


async def _load_existing_game(db: AsyncSession, parsed: ParsedBoxscore) -> Game | None:
    options = (
        selectinload(Game.team_stats),
        selectinload(Game.player_stats),
        selectinload(Game.scoring_plays),
        selectinload(Game.event_sources),
        selectinload(Game.source_snapshots),
        selectinload(Game.status_history),
        selectinload(Game.generated_content),
    )
    game = await db.scalar(
        select(Game)
        .where(Game.canonical_uid == _canonical_uid(parsed))
        .options(*options)
    )
    if game is not None:
        return game
    return await db.scalar(
        select(Game).where(Game.source_url == parsed.source_url).options(*options)
    )


def _build_game(
    parsed: ParsedBoxscore,
    registry_entry: SportSource | None = None,
) -> Game:
    now = datetime.now(UTC)
    source_event_id = _source_event_id(parsed.source_url)
    source = EventSource(
        source_type="boxscore_html",
        source_url=parsed.source_url,
        source_id=source_event_id,
        primary_source=True,
        last_fetched_at=now,
    )
    game = Game(
        source_url=parsed.source_url,
        canonical_uid=_canonical_uid(parsed),
        source_system="sidearm",
        source_event_id=source_event_id,
        sport=parsed.sport,
        sport_name=_sport_name(parsed.sport, registry_entry),
        gender=_sport_gender(parsed.sport, registry_entry),
        season=parsed.season,
        game_date=parsed.game_date,
        event_shape=_event_shape(parsed.sport, registry_entry),
        event_status=_event_status(parsed),
        publish_status="draft",
        home_team=parsed.home_team,
        away_team=parsed.away_team,
        home_score=parsed.home_score,
        away_score=parsed.away_score,
        title=parsed.title,
        home_away_neutral=_home_away_neutral(parsed),
        exhibition=_is_exhibition(parsed),
        first_seen_at=now,
        last_seen_at=now,
        last_successful_ingest_at=now,
        raw_html=parsed.raw_html,
    )
    game.team_stats = [TeamStat(**row) for row in parsed.team_stats]
    game.scoring_plays = [ScoringPlay(**row) for row in parsed.scoring_plays]
    game.player_stats = _legacy_player_stat_groups(parsed)
    game.event_sources = [source]
    game.source_snapshots = [
        SourceSnapshot(
            event_source=source,
            source_system="sidearm",
            source_type="boxscore_html",
            source_url=parsed.source_url,
            parser_version=PARSER_VERSION,
            content_hash=_content_hash(parsed.raw_html),
            http_status=200,
            fetched_at=now,
            raw_body=parsed.raw_html,
        )
    ]
    game.status_history = [
        EventStatusHistory(
            from_status=None,
            to_status=game.event_status,
            reason="initial_sidearm_boxscore_ingest",
            changed_at=now,
        )
    ]
    return game


def _refresh_game(
    game: Game,
    parsed: ParsedBoxscore,
    registry_entry: SportSource | None = None,
    *,
    preserve_schedule_metadata: bool = False,
) -> None:
    now = datetime.now(UTC)
    previous_status = game.event_status
    source_event_id = _source_event_id(parsed.source_url)

    game.source_url = parsed.source_url
    game.canonical_uid = _canonical_uid(parsed)
    game.source_system = "sidearm"
    game.source_event_id = source_event_id
    game.sport = parsed.sport
    game.sport_name = _sport_name(parsed.sport, registry_entry)
    game.gender = _sport_gender(parsed.sport, registry_entry)
    game.season = parsed.season
    game.event_shape = _event_shape(parsed.sport, registry_entry)
    if not preserve_schedule_metadata:
        game.game_date = parsed.game_date
        game.event_status = _event_status(parsed)
        game.home_team = parsed.home_team
        game.away_team = parsed.away_team
        game.home_score = parsed.home_score
        game.away_score = parsed.away_score
        game.title = parsed.title
        game.home_away_neutral = _home_away_neutral(parsed)
    game.exhibition = _is_exhibition(parsed)
    game.last_seen_at = now
    game.last_successful_ingest_at = now
    game.raw_html = parsed.raw_html

    game.team_stats = [TeamStat(**row) for row in parsed.team_stats]
    game.scoring_plays = [ScoringPlay(**row) for row in parsed.scoring_plays]
    game.player_stats = _legacy_player_stat_groups(parsed)

    source = _upsert_boxscore_source(game, parsed, source_event_id, now)
    game.source_snapshots.append(
        SourceSnapshot(
            event_source=source,
            source_system="sidearm",
            source_type="boxscore_html",
            source_url=parsed.source_url,
            parser_version=PARSER_VERSION,
            content_hash=_content_hash(parsed.raw_html),
            http_status=200,
            fetched_at=now,
            raw_body=parsed.raw_html,
        )
    )

    if previous_status != game.event_status:
        game.status_history.append(
            EventStatusHistory(
                from_status=previous_status,
                to_status=game.event_status,
                reason="sidearm_boxscore_refresh",
                changed_at=now,
            )
        )


def _upsert_boxscore_source(
    game: Game,
    parsed: ParsedBoxscore,
    source_event_id: str | None,
    fetched_at: datetime,
) -> EventSource:
    for source in game.event_sources:
        if (
            source.source_type == "boxscore_html"
            and source.source_url == parsed.source_url
        ):
            source.source_id = source_event_id
            source.primary_source = True
            source.last_fetched_at = fetched_at
            return source

    source = EventSource(
        source_type="boxscore_html",
        source_url=parsed.source_url,
        source_id=source_event_id,
        primary_source=True,
        last_fetched_at=fetched_at,
    )
    game.event_sources.append(source)
    return source


def _legacy_player_stat_groups(parsed: ParsedBoxscore) -> list[PlayerStatGroup]:
    if parsed.sport == "womens-basketball":
        return []
    return [PlayerStatGroup(**row) for row in parsed.player_stats]


def _canonical_uid(parsed: ParsedBoxscore) -> str:
    source_event_id = _source_event_id(parsed.source_url)
    if source_event_id:
        sport = parsed.sport or "unknown"
        season = parsed.season or "unknown"
        return f"sidearm:{sport}:{season}:{source_event_id}"
    return ":".join(
        [
            "sidearm",
            parsed.sport or "unknown-sport",
            parsed.season or "unknown-season",
            _slug(parsed.game_date or "unknown-date"),
            _slug(parsed.away_team or "unknown-away"),
            _slug(parsed.home_team or "unknown-home"),
        ]
    )


def _source_event_id(source_url: str) -> str | None:
    match = re.search(r"/boxscore/(\d+)(?:[/?#]|$)", source_url)
    return match.group(1) if match else None


def _content_hash(raw_body: str) -> str:
    return hashlib.sha256(raw_body.encode("utf-8")).hexdigest()


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _event_status(parsed: ParsedBoxscore) -> str:
    if parsed.home_score is not None and parsed.away_score is not None:
        return "final"
    return "unknown"


def _registry_entry_for(parsed: ParsedBoxscore) -> SportSource | None:
    if not parsed.sport:
        return None
    return get_source_registry().get_sport(parsed.sport)


def _event_shape(
    sport_slug: str | None,
    registry_entry: SportSource | None = None,
) -> str:
    if registry_entry is not None:
        return registry_entry.event_shape
    sport = sport_slug or ""
    if sport in {"mens-tennis", "womens-tennis"}:
        return "team_match"
    if sport in {"mens-golf", "womens-golf"}:
        return "tournament_event"
    if "cross-country" in sport or "track" in sport:
        return "multi_team_meet"
    if "swimming" in sport or "diving" in sport:
        return "dual_meet"
    return "team_contest"


def _sport_name(
    sport_slug: str | None,
    registry_entry: SportSource | None = None,
) -> str | None:
    if registry_entry is not None:
        return registry_entry.sport_name
    if not sport_slug:
        return None
    cleaned = sport_slug.replace("mens-", "").replace("womens-", "")
    return cleaned.replace("-", " ").title()


def _sport_gender(
    sport_slug: str | None,
    registry_entry: SportSource | None = None,
) -> str | None:
    if registry_entry is not None:
        return registry_entry.gender
    if not sport_slug:
        return None
    if sport_slug.startswith("mens-"):
        return "men"
    if sport_slug.startswith("womens-"):
        return "women"
    return None


def _home_away_neutral(parsed: ParsedBoxscore) -> str | None:
    if parsed.home_team and parsed.home_team.casefold() == "idaho":
        return "home"
    if parsed.away_team and parsed.away_team.casefold() == "idaho":
        return "away"
    if not parsed.title:
        return None
    if re.search(r"\bvs\.?\b", parsed.title, flags=re.IGNORECASE):
        return "home"
    if re.search(r"\bat\b", parsed.title, flags=re.IGNORECASE):
        return "away"
    return None


def _is_exhibition(parsed: ParsedBoxscore) -> bool:
    text = " ".join(
        part or "" for part in [parsed.title, parsed.away_team, parsed.home_team]
    )
    return bool(re.search(r"\bexh(?:ibition)?\.?\b", text, flags=re.IGNORECASE))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"
