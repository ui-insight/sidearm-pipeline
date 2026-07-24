"""Parser and discovery client for Sidearm roster pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.services.sidearm_scraper import USER_AGENT
from app.services.source_registry import get_source_registry

ROSTER_PARSER_VERSION = "sidearm-roster-html-v1"
IDAHO_INSTITUTION = "University of Idaho"
IDAHO_TEAM_SLUG = "idaho"


@dataclass
class ParsedRosterPlayer:
    """One athlete row parsed from a Sidearm roster page."""

    display_name: str
    jersey_number: str | None
    class_year: str | None
    position: str | None
    bio_url: str | None
    source_player_id: str | None
    canonical_bio_url: str | None = None
    identity_resolution_error: str | None = None

    @property
    def canonical_source_player_id(self) -> str | None:
        """Return the Sidearm id from the authoritative redirect target."""
        if self.canonical_bio_url is None:
            return None
        return source_player_id_from_url(self.canonical_bio_url)


@dataclass
class ParsedRoster:
    """A parsed roster source plus the raw payload retained for provenance."""

    sport_program_slug: str
    season: str
    source_system: str
    institution: str
    team_slug: str
    source_url: str
    raw_html: str
    players: list[ParsedRosterPlayer] = field(default_factory=list)
    http_status: int = 200


async def discover_roster(
    sport_slug: str,
    season: str,
) -> ParsedRoster:
    """Fetch a configured Sidearm roster and resolve authoritative bio redirects."""
    if not re.fullmatch(r"20\d{2}-\d{2}", season):
        raise ValueError("Roster season must be an academic year like 2025-26")

    registry = get_source_registry()
    sport = registry.require_sport(sport_slug)
    roster_path = sport.source_patterns.roster_url
    if roster_path is None:
        raise ValueError(f"No roster source configured for sport '{sport_slug}'")

    source_url = urljoin(
        str(registry.base_url),
        f"{roster_path.rstrip('/')}/{season}",
    )
    async with httpx.AsyncClient(
        timeout=settings.SIDEARM_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = await client.get(source_url)
        response.raise_for_status()
        roster = parse_roster(
            response.text,
            sport_program_slug=sport_slug,
            source_url=str(response.url),
            institution=IDAHO_INSTITUTION,
            team_slug=IDAHO_TEAM_SLUG,
        )
        for player in roster.players:
            if player.bio_url is None:
                continue
            try:
                player.canonical_bio_url = await _resolve_bio_url(
                    client, player.bio_url
                )
            except httpx.HTTPError as exc:
                player.identity_resolution_error = str(exc)

    return roster


def parse_roster(
    html: str,
    *,
    sport_program_slug: str,
    source_url: str,
    institution: str = IDAHO_INSTITUTION,
    team_slug: str = IDAHO_TEAM_SLUG,
) -> ParsedRoster:
    """Parse Sidearm roster cards or the accessible roster table."""
    soup = BeautifulSoup(html, "lxml")
    season = _extract_season(soup, source_url)
    if season is None:
        raise ValueError("Unable to determine roster season from URL or title")

    card_rows = [
        row for row in soup.select("li.sidearm-roster-player") if isinstance(row, Tag)
    ]
    if card_rows:
        players = [_parse_card(row, source_url) for row in card_rows]
    else:
        players = _parse_accessible_table(soup, source_url)
    players = _deduplicate_players(players)
    if not players:
        raise ValueError("No Sidearm roster player rows were found")

    return ParsedRoster(
        sport_program_slug=sport_program_slug,
        season=season,
        source_system="sidearm",
        institution=institution,
        team_slug=team_slug,
        source_url=source_url,
        raw_html=html,
        players=players,
    )


async def _resolve_bio_url(client: httpx.AsyncClient, bio_url: str) -> str:
    response = await client.head(bio_url)
    if response.status_code in {403, 405}:
        response = await client.get(bio_url)
    response.raise_for_status()
    return str(response.url)


def _parse_card(row: Tag, source_url: str) -> ParsedRosterPlayer:
    name_block = row.select_one(".sidearm-roster-player-name")
    bio_link = name_block.find("a", href=True) if name_block else None
    if bio_link is None:
        bio_link = row.find("a", href=re.compile(r"/roster/"))

    bio_url = _absolute_href(bio_link, source_url)
    display_name = _clean_text(bio_link or name_block or row)
    return ParsedRosterPlayer(
        display_name=display_name,
        jersey_number=_first_text(
            row,
            ".sidearm-roster-player-jersey-number",
            ".sidearm-roster-player-number",
        ),
        class_year=_first_text(
            row,
            ".sidearm-roster-player-academic-year",
            ".sidearm-roster-player-class",
        ),
        position=_first_text(
            row,
            ".sidearm-roster-player-position-short",
            ".sidearm-roster-player-position",
        ),
        bio_url=bio_url,
        source_player_id=(
            source_player_id_from_url(bio_url) if bio_url is not None else None
        ),
    )


def _parse_accessible_table(
    soup: BeautifulSoup,
    source_url: str,
) -> list[ParsedRosterPlayer]:
    for table in soup.find_all("table"):
        headers = [_clean_text(header) for header in table.select("thead th")]
        if "Full Name" not in headers or "Year" not in headers:
            continue

        players: list[ParsedRosterPlayer] = []
        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) != len(headers):
                continue
            values = dict(zip(headers, cells, strict=True))
            name_cell = values["Full Name"]
            bio_link = name_cell.find("a", href=True)
            bio_url = _absolute_href(bio_link, source_url)
            players.append(
                ParsedRosterPlayer(
                    display_name=_clean_text(bio_link or name_cell),
                    jersey_number=_table_value(values, "#"),
                    class_year=_table_value(values, "Year"),
                    position=_table_value(values, "Pos."),
                    bio_url=bio_url,
                    source_player_id=(
                        source_player_id_from_url(bio_url)
                        if bio_url is not None
                        else None
                    ),
                )
            )
        return players

    return []


def _extract_season(soup: BeautifulSoup, source_url: str) -> str | None:
    url_match = re.search(r"/roster/(20\d{2}-\d{2})(?:[/?#]|$)", source_url)
    if url_match:
        return url_match.group(1)

    title = soup.find("title")
    if title:
        title_match = re.search(r"\b(20\d{2}-\d{2})\b", _clean_text(title))
        if title_match:
            return title_match.group(1)
    return None


def source_player_id_from_url(url: str) -> str | None:
    """Return the terminal numeric Sidearm id from a player bio URL."""
    match = re.search(r"/(\d+)$", urlparse(url).path.rstrip("/"))
    return match.group(1) if match else None


def _absolute_href(link: Tag | None, source_url: str) -> str | None:
    if link is None or not link.get("href"):
        return None
    return urljoin(source_url, str(link["href"]))


def _first_text(row: Tag, *selectors: str) -> str | None:
    for selector in selectors:
        value = row.select_one(selector)
        if value is not None and _clean_text(value):
            return _clean_text(value)
    return None


def _table_value(values: dict[str, Tag], header: str) -> str | None:
    value = values.get(header)
    return _clean_text(value) if value is not None and _clean_text(value) else None


def _clean_text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def _deduplicate_players(
    players: list[ParsedRosterPlayer],
) -> list[ParsedRosterPlayer]:
    unique: list[ParsedRosterPlayer] = []
    seen: set[tuple[str | None, str, str | None]] = set()
    for player in players:
        key = (
            player.source_player_id,
            player.display_name.casefold(),
            player.jersey_number,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(player)
    return unique
