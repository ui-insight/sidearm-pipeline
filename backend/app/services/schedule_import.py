"""Persist discovered Sidearm schedule events as canonical games."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.game import EventSource, EventStatusHistory, Game
from app.services.sidearm_schedule import ParsedScheduleEvent
from app.services.source_registry import SportSource, get_source_registry

TEAM_NAME = "Idaho"


async def import_schedule_events(
    db: AsyncSession,
    events: list[ParsedScheduleEvent],
) -> list[Game]:
    """Upsert discovered schedule events into the canonical games table."""
    games: list[Game] = []

    for event in events:
        game = await _load_existing_game(db, event)
        if game is None:
            game = _build_game(event)
            db.add(game)
        else:
            _refresh_game(game, event)
        games.append(game)

    await db.commit()
    for game in games:
        await db.refresh(game)

    return games


async def _load_existing_game(
    db: AsyncSession,
    event: ParsedScheduleEvent,
) -> Game | None:
    options = (
        selectinload(Game.event_sources),
        selectinload(Game.status_history),
    )
    canonical_uid = _canonical_uid(event)
    game = await db.scalar(
        select(Game).where(Game.canonical_uid == canonical_uid).options(*options)
    )
    if game is not None:
        return game

    stmt = select(Game).where(Game.source_url == _primary_source_url(event))
    return await db.scalar(stmt.options(*options))


def _build_game(event: ParsedScheduleEvent) -> Game:
    now = datetime.now(UTC)
    home_team, away_team = _teams(event)
    home_score, away_score = _scores(event)
    source_url = _primary_source_url(event)
    sport = _sport_registry_entry(event)

    game = Game(
        source_url=source_url,
        canonical_uid=_canonical_uid(event),
        source_system=event.source_system,
        source_event_id=event.source_event_id,
        sport=event.sport_slug,
        sport_name=event.sport_name,
        gender=event.gender,
        season=event.season,
        game_date=_game_date(event),
        event_shape=sport.event_shape if sport is not None else "team_contest",
        event_status=event.event_status,
        publish_status="draft",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        title=_title(event),
        location_name=event.location_name,
        venue_name=event.venue_name,
        home_away_neutral=event.home_away_neutral,
        conference_event=event.conference_event,
        first_seen_at=now,
        last_seen_at=now,
        ingested_at=now,
    )
    game.event_sources = _event_sources(event, now, source_url)
    game.status_history = [
        EventStatusHistory(
            from_status=None,
            to_status=event.event_status,
            reason="initial_sidearm_schedule_import",
            changed_at=now,
        )
    ]
    return game


def _refresh_game(game: Game, event: ParsedScheduleEvent) -> None:
    now = datetime.now(UTC)
    previous_status = game.event_status
    home_team, away_team = _teams(event)
    home_score, away_score = _scores(event)
    source_url = _primary_source_url(event)
    sport = _sport_registry_entry(event)

    if event.boxscore_url or not _is_boxscore_url(game.source_url):
        game.source_url = source_url
    game.canonical_uid = _canonical_uid(event)
    game.source_system = event.source_system
    game.source_event_id = event.source_event_id
    game.sport = event.sport_slug
    game.sport_name = event.sport_name
    game.gender = event.gender
    game.season = event.season
    game.game_date = _game_date(event)
    game.event_shape = sport.event_shape if sport is not None else game.event_shape
    game.event_status = event.event_status
    game.home_team = home_team
    game.away_team = away_team
    game.home_score = home_score
    game.away_score = away_score
    game.title = _title(event)
    game.location_name = event.location_name
    game.venue_name = event.venue_name
    game.home_away_neutral = event.home_away_neutral
    game.conference_event = event.conference_event
    game.last_seen_at = now
    game.ingested_at = now

    _upsert_event_sources(game, event, now, source_url)

    if previous_status != event.event_status:
        game.status_history.append(
            EventStatusHistory(
                from_status=previous_status,
                to_status=event.event_status,
                reason="sidearm_schedule_refresh",
                changed_at=now,
            )
        )


def _event_sources(
    event: ParsedScheduleEvent,
    discovered_at: datetime,
    primary_source_url: str,
) -> list[EventSource]:
    sources = [
        EventSource(
            source_type="schedule_html",
            source_url=event.schedule_url,
            source_id=event.source_event_id,
            primary_source=not event.boxscore_url,
            discovered_at=discovered_at,
        )
    ]

    for source_type, source_url in event.source_urls.items():
        sources.append(
            EventSource(
                source_type=source_type,
                source_url=source_url,
                source_id=_source_id_for(source_type, source_url, event),
                primary_source=source_url == primary_source_url,
                discovered_at=discovered_at,
            )
        )

    return sources


def _upsert_event_sources(
    game: Game,
    event: ParsedScheduleEvent,
    discovered_at: datetime,
    primary_source_url: str,
) -> None:
    incoming = _event_sources(event, discovered_at, primary_source_url)
    for source in game.event_sources:
        source.primary_source = False

    for source in incoming:
        existing = next(
            (
                candidate
                for candidate in game.event_sources
                if candidate.source_type == source.source_type
                and candidate.source_url == source.source_url
            ),
            None,
        )
        if existing is None:
            game.event_sources.append(source)
            continue

        existing.source_id = source.source_id
        existing.primary_source = source.primary_source


def _canonical_uid(event: ParsedScheduleEvent) -> str:
    if event.source_event_id:
        season = event.season or "unknown"
        return f"sidearm:{event.sport_slug}:{season}:{event.source_event_id}"

    identity_parts = [
        "sidearm",
        event.sport_slug or "unknown-sport",
        event.season or "unknown-season",
        _slug(_game_date(event) or "unknown-date"),
        _slug(event.opponent_name or "unknown-opponent"),
        event.home_away_neutral or "unknown-site",
    ]
    return ":".join(identity_parts)


def _primary_source_url(event: ParsedScheduleEvent) -> str:
    if event.boxscore_url:
        return event.boxscore_url

    event_key = event.source_event_id or _slug(
        "-".join(
            part
            for part in [
                event.sport_slug,
                event.season or "",
                _game_date(event) or "",
                event.opponent_name or "",
            ]
            if part
        )
    )
    return f"{event.schedule_url}#game-{event_key}"


def _source_id_for(
    source_type: str,
    source_url: str,
    event: ParsedScheduleEvent,
) -> str | None:
    if source_type == "boxscore_html":
        match = re.search(r"/boxscore/(\d+)(?:[/?#]|$)", source_url)
        if match:
            return match.group(1)
    return event.source_event_id


def _teams(event: ParsedScheduleEvent) -> tuple[str | None, str | None]:
    opponent = event.opponent_name
    if event.home_away_neutral == "away":
        return opponent, TEAM_NAME
    return TEAM_NAME, opponent


def _scores(event: ParsedScheduleEvent) -> tuple[int | None, int | None]:
    if event.home_away_neutral == "away":
        return event.opponent_score, event.team_score
    return event.team_score, event.opponent_score


def _title(event: ParsedScheduleEvent) -> str:
    opponent = event.opponent_name or "Opponent TBD"
    if event.home_away_neutral == "away":
        return f"{TEAM_NAME} at {opponent}"
    return f"{TEAM_NAME} vs {opponent}"


def _game_date(event: ParsedScheduleEvent) -> str | None:
    if event.event_date is not None:
        return event.event_date.isoformat()
    return event.date_text


def _sport_registry_entry(event: ParsedScheduleEvent) -> SportSource | None:
    return get_source_registry().get_sport(event.sport_slug)


def _is_boxscore_url(source_url: str) -> bool:
    return "/boxscore/" in source_url


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
