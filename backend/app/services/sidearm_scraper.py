"""Scraper for Sidearm Sports boxscore pages.

Sidearm sites (e.g. govandals.com) render boxscores as standard HTML tables
inside labelled sections. The scraper fetches the page, walks the DOM, and
classifies each table by the nearest preceding heading so the data can be
stored in a normalized schema.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 VandalsStatsPipeline/0.1"
)
REQUEST_TIMEOUT = 20.0

PLAYER_CATEGORY_KEYWORDS = {
    "passing": "passing",
    "rushing": "rushing",
    "receiving": "receiving",
    "defense": "defense",
    "defensive": "defense",
    "tackles": "defense",
    "kicking": "kicking",
    "field goal": "kicking",
    "punting": "punting",
    "kick return": "kick_returns",
    "punt return": "punt_returns",
    "returns": "returns",
    "interception": "interceptions",
}


@dataclass
class ParsedTable:
    heading: str
    columns: list[str]
    rows: list[list[str]]
    raw_table: Tag | None = None


@dataclass
class ParsedBoxscore:
    source_url: str
    title: str | None = None
    sport: str | None = None
    season: str | None = None
    game_date: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    team_stats: list[dict] = field(default_factory=list)
    player_stats: list[dict] = field(default_factory=list)
    scoring_plays: list[dict] = field(default_factory=list)
    raw_html: str = ""


async def fetch_boxscore(url: str) -> str:
    """Fetch the boxscore HTML."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def parse_boxscore(url: str, html: str) -> ParsedBoxscore:
    """Parse a Sidearm boxscore HTML document into a structured payload."""
    soup = BeautifulSoup(html, "lxml")
    result = ParsedBoxscore(source_url=url, raw_html=html)

    _extract_metadata(soup, url, result)
    tables = _collect_labelled_tables(soup)

    for table in tables:
        heading_lower = table.heading.lower()
        if _is_scoring_summary(heading_lower):
            _ingest_scoring_summary(table, result)
        elif _is_team_stats(heading_lower):
            result.team_stats.extend(_team_stat_rows(table))
        else:
            category = _player_category(heading_lower)
            if category:
                result.player_stats.append(
                    {
                        "category": category,
                        "team": None,
                        "columns": table.columns,
                        "rows": table.rows,
                    }
                )

    _derive_teams_from_title(result)
    return result


def _extract_metadata(soup: BeautifulSoup, url: str, result: ParsedBoxscore) -> None:
    """Pull page title and URL-derived metadata (sport, season)."""
    title_tag = soup.find("title")
    if title_tag:
        result.title = title_tag.get_text(strip=True)

    # URL shape: /sports/<sport>/stats/<season>/<opponent-slug>/boxscore/<id>
    url_match = re.search(r"/sports/([^/]+)/stats/([^/]+)/", url)
    if url_match:
        result.sport = url_match.group(1)
        result.season = url_match.group(2)


def _collect_labelled_tables(soup: BeautifulSoup) -> list[ParsedTable]:
    """Walk all <table> elements and label each by the nearest preceding heading."""
    parsed: list[ParsedTable] = []
    for table in soup.find_all("table"):
        heading = _nearest_heading(table)
        columns, rows = _extract_table(table)
        if not rows:
            continue
        parsed.append(
            ParsedTable(heading=heading, columns=columns, rows=rows, raw_table=table)
        )
    return parsed


def _nearest_heading(table: Tag) -> str:
    """Find the closest preceding heading or caption for a table."""
    caption = table.find("caption")
    if caption and caption.get_text(strip=True):
        return caption.get_text(strip=True)

    for ancestor in table.parents:
        if not isinstance(ancestor, Tag):
            continue
        heading = ancestor.find(["h1", "h2", "h3", "h4", "h5"])
        if heading and heading.get_text(strip=True):
            return heading.get_text(" ", strip=True)

    previous = table.find_previous(["h1", "h2", "h3", "h4", "h5", "caption"])
    if previous:
        return previous.get_text(" ", strip=True)

    aria = table.get("aria-label") or table.get("summary")
    return (aria or "").strip()


def _extract_table(table: Tag) -> tuple[list[str], list[list[str]]]:
    """Return (columns, rows) with cells as stripped strings."""
    columns: list[str] = []

    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            columns = [_cell_text(c) for c in header_row.find_all(["th", "td"])]

    if not columns:
        first_row = table.find("tr")
        if first_row and first_row.find("th"):
            columns = [_cell_text(c) for c in first_row.find_all(["th", "td"])]

    body_rows: list[list[str]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        if tr.find_parent("thead"):
            continue
        if not columns and tr is table.find("tr") and tr.find("th"):
            continue
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row = [_cell_text(c) for c in cells]
        if any(cell for cell in row):
            body_rows.append(row)

    return columns, body_rows


def _cell_text(cell: Tag) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True))


def _is_scoring_summary(heading: str) -> bool:
    return "scoring summary" in heading or heading.strip() == "scoring"


def _is_team_stats(heading: str) -> bool:
    return "team stat" in heading


def _player_category(heading: str) -> str | None:
    for keyword, category in PLAYER_CATEGORY_KEYWORDS.items():
        if keyword in heading:
            return category
    return None


def _team_stat_rows(table: ParsedTable) -> Iterable[dict]:
    """A team-stats table has one label column plus two value columns."""
    for index, row in enumerate(table.rows):
        if len(row) < 3:
            continue
        yield {
            "stat_name": row[0],
            "home_value": row[1],
            "away_value": row[2],
            "sort_order": index,
        }


def _ingest_scoring_summary(table: ParsedTable, result: ParsedBoxscore) -> None:
    """Parse a Sidearm scoring summary table using its column cells with data-labels.

    Sidearm renders two views in the same table (mobile combined + desktop split),
    so positional indexing is unreliable. The column cells expose ``data-label``
    attributes that map to the visible desktop headers ("Qtr", "Time", "UCD",
    "IDA"), which we use as the authoritative key.
    """
    if table.raw_table is None:
        return

    away_code, home_code = _score_column_codes(table.columns)

    for index, tr in enumerate(table.raw_table.select("tbody > tr")):
        labelled = {
            (cell.get("data-label") or "").strip(): _cell_text(cell)
            for cell in tr.find_all(["td", "th"])
        }

        period = labelled.get("Qtr") or None
        clock = labelled.get("Time") or None

        if not period or not clock:
            combined = labelled.get("Qtr. - Time") or ""
            combined_match = re.match(r"^\s*(\S+)\s*-\s*([\d:]+)\s*$", combined)
            if combined_match:
                period = period or combined_match.group(1)
                clock = clock or combined_match.group(2)

        description = None
        for cell in tr.find_all("td"):
            classes = cell.get("class") or []
            if "hide-on-large" in classes:
                continue
            text = _cell_text(cell)
            if len(text) > 20 and not text.isdigit():
                description = text
                break

        away_score = _safe_int(labelled.get(away_code)) if away_code else None
        home_score = _safe_int(labelled.get(home_code)) if home_code else None

        team = None
        if description:
            team_match = re.match(r"^([A-Z]{2,4})\s+-\s+", description)
            if team_match:
                team = team_match.group(1)

        result.scoring_plays.append(
            {
                "period": period,
                "clock": clock,
                "description": description,
                "team": team,
                "home_score": home_score,
                "away_score": away_score,
                "sort_order": index,
            }
        )

    if result.scoring_plays:
        last = result.scoring_plays[-1]
        result.home_score = last.get("home_score")
        result.away_score = last.get("away_score")


def _score_column_codes(columns: list[str]) -> tuple[str | None, str | None]:
    """Return (away_code, home_code) from a scoring-summary header row.

    In Sidearm the two right-most columns are team codes (e.g., "UCD", "IDA").
    The first is the away/visitor, the second is the home side.
    """
    codes = [
        c for c in columns if re.fullmatch(r"[A-Z]{2,4}", c) and c not in {"TD", "INT"}
    ]
    if len(codes) >= 2:
        return codes[0], codes[1]
    return None, None


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    return int(value) if value.isdigit() else None


def _derive_teams_from_title(result: ParsedBoxscore) -> None:
    """Parse home/away team names and game date from the page title.

    Typical format: "Football vs UC Davis on 11/8/2025 - Box Score - Idaho Athletics".
    """
    if not result.title:
        return

    match = re.search(
        r"(?:vs\.?|at)\s+(.+?)\s+on\s+(\d{1,2}/\d{1,2}/\d{2,4})",
        result.title,
        flags=re.IGNORECASE,
    )
    if not match:
        return

    opponent, date_str = match.group(1).strip(), match.group(2).strip()
    result.game_date = date_str

    host = _host_team_from_title(result.title)
    is_home_game = bool(re.search(r"\bvs\.?\b", result.title, flags=re.IGNORECASE))

    if is_home_game:
        result.home_team = result.home_team or host
        result.away_team = result.away_team or opponent
    else:
        result.home_team = result.home_team or opponent
        result.away_team = result.away_team or host


def _host_team_from_title(title: str) -> str | None:
    """Extract the host/school name from the trailing "- <School> Athletics" suffix."""
    match = re.search(r"-\s*([A-Z][^-]+?)\s+Athletics\b", title)
    if match:
        return match.group(1).strip()
    return None


async def scrape_boxscore(url: str) -> ParsedBoxscore:
    """High-level entry point: fetch + parse."""
    html = await fetch_boxscore(url)
    parsed = parse_boxscore(url, html)
    logger.info(
        "Scraped boxscore url=%s team_stats=%d player_groups=%d scoring=%d",
        url,
        len(parsed.team_stats),
        len(parsed.player_stats),
        len(parsed.scoring_plays),
    )
    return parsed
