"""Parser and discovery client for cumulative Sidearm season statistics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.services.sidearm_scraper import USER_AGENT
from app.services.source_registry import get_source_registry

CUMULATIVE_STATS_PARSER_VERSION = "govandals-cumulative-html-v1"
PUBLICATION_SOURCE_SYSTEM = "govandals_public_html"
IDENTITY_SOURCE_SYSTEM = "sidearm"
IDAHO_INSTITUTION = "University of Idaho"
IDAHO_TEAM_SLUG = "idaho"

ATOMIC_SOURCE_FIELDS = {
    "MIN": "minutes_played",
    "FGM": "field_goals_made",
    "FGA": "field_goals_attempted",
    "3PT": "three_point_field_goals_made",
    "3PTA": "three_point_field_goals_attempted",
    "FT": "free_throws_made",
    "FTA": "free_throws_attempted",
    "OFF REB": "offensive_rebounds",
    "DEF REB": "defensive_rebounds",
    "REB": "total_rebounds",
    "PF": "personal_fouls",
    "AST": "assists",
    "TO": "turnovers",
    "STL": "steals",
    "BLK": "blocks",
    "PTS": "points",
}


@dataclass(frozen=True)
class ParsedCumulativePlayer:
    """One overall player row from a cumulative season source."""

    display_name: str
    jersey_number: str | None
    source_player_id: str | None
    bio_url: str | None
    games_played: int
    games_started: int | None
    stats: dict[str, Decimal] = field(default_factory=dict)
    source_fields: dict[str, str] = field(default_factory=dict)
    source_values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedCumulativeStats:
    """A parsed cumulative source plus its replayable raw payload."""

    sport_program_slug: str
    season: str
    source_system: str
    identity_source_system: str
    institution: str
    team_slug: str
    source_url: str
    raw_html: str
    players: list[ParsedCumulativePlayer] = field(default_factory=list)
    http_status: int = 200


class CumulativeStatsParseError(ValueError):
    """Markup failure retaining the fetched payload for review and replay."""

    def __init__(
        self,
        message: str,
        *,
        source_url: str,
        raw_html: str,
        http_status: int,
    ) -> None:
        super().__init__(message)
        self.source_url = source_url
        self.raw_html = raw_html
        self.http_status = http_status


async def discover_cumulative_stats(
    sport_slug: str,
    season: str,
) -> ParsedCumulativeStats:
    """Fetch and parse a registered cumulative-season statistics page."""
    _validate_season(season)
    registry = get_source_registry()
    sport = registry.require_sport(sport_slug)
    path_template = sport.source_patterns.cumulative_stats_url
    if path_template is None:
        raise ValueError(
            f"No cumulative statistics source configured for sport '{sport_slug}'"
        )
    source_url = urljoin(
        str(registry.base_url),
        path_template.format(season=season).lstrip("/"),
    )
    async with httpx.AsyncClient(
        timeout=settings.SIDEARM_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = await client.get(source_url)
        response.raise_for_status()

    try:
        return parse_cumulative_stats(
            response.text,
            sport_program_slug=sport_slug,
            source_url=str(response.url),
            http_status=response.status_code,
        )
    except ValueError as exc:
        raise CumulativeStatsParseError(
            str(exc),
            source_url=str(response.url),
            raw_html=response.text,
            http_status=response.status_code,
        ) from exc


def parse_cumulative_stats(
    html: str,
    *,
    sport_program_slug: str,
    source_url: str,
    http_status: int = 200,
) -> ParsedCumulativeStats:
    """Parse the overall Sidearm table while retaining only atomic totals."""
    soup = BeautifulSoup(html, "lxml")
    season = _extract_season(soup, source_url)
    if season is None:
        raise ValueError("Unable to determine cumulative statistics season")
    table = _overall_individual_table(soup)
    if table is None:
        raise ValueError("Overall Individual Statistics table was not found")

    body = table.find("tbody")
    if not isinstance(body, Tag):
        raise ValueError("Overall Individual Statistics table has no body")
    players = [
        _parse_player_row(row, source_url)
        for row in body.find_all("tr", recursive=False)
        if isinstance(row, Tag) and not _is_team_row(row)
    ]
    if not players:
        raise ValueError("Overall Individual Statistics table has no player rows")

    return ParsedCumulativeStats(
        sport_program_slug=sport_program_slug,
        season=season,
        source_system=PUBLICATION_SOURCE_SYSTEM,
        identity_source_system=IDENTITY_SOURCE_SYSTEM,
        institution=IDAHO_INSTITUTION,
        team_slug=IDAHO_TEAM_SLUG,
        source_url=source_url,
        raw_html=html,
        players=players,
        http_status=http_status,
    )


def _overall_individual_table(soup: BeautifulSoup) -> Tag | None:
    for caption in soup.find_all("caption"):
        if "Overall Individual Statistics" not in caption.get_text(" ", strip=True):
            continue
        table = caption.find_parent("table")
        if isinstance(table, Tag):
            return table
    return None


def _parse_player_row(row: Tag, source_url: str) -> ParsedCumulativePlayer:
    identity_link = row.select_one("a[data-player-id]")
    player_cells = row.find_all("td", recursive=False)
    player_cell = player_cells[1] if len(player_cells) > 1 else None
    name_link = player_cell.find("a") if isinstance(player_cell, Tag) else identity_link
    display_name = (
        name_link.get_text(" ", strip=True)
        if isinstance(name_link, Tag)
        else player_cell.get_text(" ", strip=True)
        if isinstance(player_cell, Tag)
        else ""
    )
    if not display_name:
        raise ValueError("Cumulative player row has an empty player name")

    cells = {
        str(cell.get("data-label")): cell.get_text(" ", strip=True)
        for cell in row.find_all("td")
        if cell.get("data-label")
    }
    games_played = _required_integer(cells.get("GP"), "GP", display_name)
    games_started = _optional_integer(cells.get("GS"), "GS", display_name)
    source_values = {key: value for key, value in cells.items() if value != ""}
    stats: dict[str, Decimal] = {}
    source_fields: dict[str, str] = {}
    for source_field, stat_key in ATOMIC_SOURCE_FIELDS.items():
        source_value = cells.get(source_field)
        if source_value is None or source_value in {"", "--"}:
            continue
        stats[stat_key] = _decimal(source_value, source_field, display_name)
        source_fields[stat_key] = source_field

    bio_link = row.select_one('td[data-label="BIO"] a[href]')
    bio_url = (
        urljoin(source_url, str(bio_link.get("href")))
        if isinstance(bio_link, Tag)
        else None
    )
    first_cell = row.find("td")
    jersey_number = (
        first_cell.get_text(" ", strip=True) if isinstance(first_cell, Tag) else None
    )
    source_player_id = (
        str(identity_link.get("data-player-id") or "").strip()
        if isinstance(identity_link, Tag)
        else ""
    ) or _source_player_id_from_url(bio_url)
    return ParsedCumulativePlayer(
        display_name=display_name,
        jersey_number=jersey_number or None,
        source_player_id=source_player_id,
        bio_url=bio_url,
        games_played=games_played,
        games_started=games_started,
        stats=stats,
        source_fields=source_fields,
        source_values=source_values,
    )


def _is_team_row(row: Tag) -> bool:
    first_cell = row.find("td")
    if not isinstance(first_cell, Tag):
        return False
    return first_cell.get_text(" ", strip=True).casefold() in {"tm", "team"}


def _source_player_id_from_url(url: str | None) -> str | None:
    if url is None:
        return None
    match = re.search(r"/(\d+)(?:/)?$", url)
    return match.group(1) if match else None


def _extract_season(soup: BeautifulSoup, source_url: str) -> str | None:
    match = re.search(r"/stats/(20\d{2}-\d{2})(?:/|$|\?)", source_url)
    if match:
        return match.group(1)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    match = re.search(r"\b(20\d{2}-\d{2})\b", title)
    return match.group(1) if match else None


def _validate_season(season: str) -> None:
    if not re.fullmatch(r"20\d{2}-\d{2}", season):
        raise ValueError("Cumulative stats season must be like 2025-26")


def _required_integer(value: str | None, field_name: str, player: str) -> int:
    parsed = _optional_integer(value, field_name, player)
    if parsed is None:
        raise ValueError(f"{player} is missing required cumulative field {field_name}")
    return parsed


def _optional_integer(
    value: str | None,
    field_name: str,
    player: str,
) -> int | None:
    if value is None or value in {"", "--"}:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError as exc:
        raise ValueError(
            f"{player} has invalid cumulative field {field_name}: {value}"
        ) from exc


def _decimal(value: str, source_field: str, player: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(
            f"{player} has invalid cumulative field {source_field}: {value}"
        ) from exc
