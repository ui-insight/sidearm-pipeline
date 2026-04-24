"""Game ingestion and retrieval endpoints."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.engine import get_db
from app.models.content import GeneratedContent
from app.models.game import (
    EventSource,
    EventStatusHistory,
    Game,
    PlayerStatGroup,
    ScoringPlay,
    SourceSnapshot,
    TeamStat,
)
from app.schemas.content import GeneratedContentRead
from app.schemas.game import GameDetail, GameSummary, IngestRequest
from app.services.content_generator import generate_coverage
from app.services.sidearm_scraper import ParsedBoxscore, scrape_boxscore
from app.services.source_registry import SportSource, get_source_registry

router = APIRouter()
PARSER_VERSION = "sidearm-html-v1"


@router.post(
    "",
    response_model=GameDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a Sidearm boxscore URL",
)
async def ingest_game(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Fetch a Sidearm boxscore page, parse it, and store the structured data.

    If the same canonical event has already been ingested, the existing record
    is updated in place and a new source snapshot is retained.
    """
    url = str(payload.url)

    try:
        parsed = await scrape_boxscore(url)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch Sidearm page: {exc}",
        ) from exc
    registry_entry = _registry_entry_for(parsed)

    game = await _load_existing_game(db, parsed)
    if game is None:
        game = _build_game(parsed, registry_entry)
        db.add(game)
    else:
        _refresh_game(game, parsed, registry_entry)

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

    return GameDetail.model_validate(game)


@router.get(
    "",
    response_model=list[GameSummary],
    summary="List ingested games",
)
async def list_games(db: AsyncSession = Depends(get_db)) -> list[GameSummary]:
    """Return every ingested game, newest first."""
    result = await db.scalars(select(Game).order_by(Game.ingested_at.desc()))
    return [GameSummary.model_validate(row) for row in result.all()]


@router.get(
    "/{game_id}",
    response_model=GameDetail,
    summary="Get a single game with full boxscore",
)
async def get_game(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GameDetail:
    """Return one game plus its team stats, player stats, and scoring plays."""
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )
    return GameDetail.model_validate(game)


@router.delete(
    "/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an ingested game",
)
async def delete_game(game_id: int, db: AsyncSession = Depends(get_db)) -> None:
    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )
    await db.delete(game)
    await db.commit()


@router.post(
    "/{game_id}/generate",
    response_model=GeneratedContentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI coverage (recap + spotlight + social) for a game",
)
async def generate_game_content(
    game_id: int,
    db: AsyncSession = Depends(get_db),
) -> GeneratedContentRead:
    """Call the content generator and persist the result."""
    game = await _load_game(db, game_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    try:
        coverage = await generate_coverage(game)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    from app.config import settings

    record = GeneratedContent(
        game_id=game.id,
        headline=coverage.headline,
        recap=coverage.recap,
        spotlight_player=coverage.spotlight_player,
        spotlight_body=coverage.spotlight_body,
        social_post=coverage.social_post,
        model=settings.CONTENT_MODEL,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return GeneratedContentRead.model_validate(record)


async def _load_game(db: AsyncSession, game_id: int) -> Game | None:
    stmt = (
        select(Game)
        .where(Game.id == game_id)
        .options(
            selectinload(Game.team_stats),
            selectinload(Game.player_stats),
            selectinload(Game.scoring_plays),
            selectinload(Game.event_sources),
            selectinload(Game.source_snapshots),
            selectinload(Game.status_history),
            selectinload(Game.generated_content),
        )
    )
    return await db.scalar(stmt)


async def _load_existing_game(db: AsyncSession, parsed: ParsedBoxscore) -> Game | None:
    """Find an existing event by canonical identity, falling back to source URL."""
    options = (
        selectinload(Game.team_stats),
        selectinload(Game.player_stats),
        selectinload(Game.scoring_plays),
        selectinload(Game.event_sources),
        selectinload(Game.source_snapshots),
        selectinload(Game.status_history),
        selectinload(Game.generated_content),
    )
    canonical_uid = _canonical_uid(parsed)
    game = await db.scalar(
        select(Game).where(Game.canonical_uid == canonical_uid).options(*options)
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
    game.player_stats = [PlayerStatGroup(**row) for row in parsed.player_stats]
    game.event_sources = [source]
    game.source_snapshots = [
        SourceSnapshot(
            event_source=source,
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
) -> None:
    """Refresh normalized event data while preserving identity and history."""
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
    game.game_date = parsed.game_date
    game.event_shape = _event_shape(parsed.sport, registry_entry)
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
    game.player_stats = [PlayerStatGroup(**row) for row in parsed.player_stats]

    source = _upsert_boxscore_source(game, parsed, source_event_id, now)
    game.source_snapshots.append(
        SourceSnapshot(
            event_source=source,
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


def _canonical_uid(parsed: ParsedBoxscore) -> str:
    """Build a stable event key from source identity and parsed metadata."""
    source_event_id = _source_event_id(parsed.source_url)
    if source_event_id:
        sport = parsed.sport or "unknown"
        season = parsed.season or "unknown"
        return f"sidearm:{sport}:{season}:{source_event_id}"

    identity_parts = [
        "sidearm",
        parsed.sport or "unknown-sport",
        parsed.season or "unknown-season",
        _slug(parsed.game_date or "unknown-date"),
        _slug(parsed.away_team or "unknown-away"),
        _slug(parsed.home_team or "unknown-home"),
    ]
    return ":".join(identity_parts)


def _source_event_id(source_url: str) -> str | None:
    match = re.search(r"/boxscore/(\d+)(?:[/?#]|$)", source_url)
    return match.group(1) if match else None


def _content_hash(raw_body: str) -> str:
    return hashlib.sha256(raw_body.encode("utf-8")).hexdigest()


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
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
