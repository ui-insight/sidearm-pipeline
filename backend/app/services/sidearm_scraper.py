"""Scraper for Sidearm Sports boxscore pages.

Sidearm sites (e.g. govandals.com) render boxscores as standard HTML tables
inside labelled sections. The scraper fetches the page, walks the DOM, and
classifies each table by the nearest preceding heading so the data can be
stored in a normalized schema.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 VandalsStatsPipeline/0.1"
)

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

BASKETBALL_SPORTS = {"mens-basketball", "womens-basketball"}
BASKETBALL_PLAYER_COLUMNS = {
    "##",
    "Player",
    "GS",
    "MIN",
    "FG",
    "3PT",
    "FT",
    "ORB-DRB",
    "REB",
    "PF",
    "A",
    "TO",
    "BLK",
    "STL",
    "PTS",
}
BASKETBALL_SINGLE_VALUE_STATS = {
    "MIN": "minutes_played",
    "REB": "total_rebounds",
    "PF": "personal_fouls",
    "A": "assists",
    "TO": "turnovers",
    "BLK": "blocks",
    "STL": "steals",
    "PTS": "points",
}
BASKETBALL_PAIRED_VALUE_STATS = {
    "FG": ("field_goals_made", "field_goals_attempted"),
    "3PT": ("three_point_field_goals_made", "three_point_field_goals_attempted"),
    "FT": ("free_throws_made", "free_throws_attempted"),
    "ORB-DRB": ("offensive_rebounds", "defensive_rebounds"),
}


@dataclass(frozen=True)
class FetchRetryPolicy:
    """Timeout and retry settings for one Sidearm fetch operation."""

    timeout_seconds: float
    max_attempts: int
    backoff_seconds: float


@dataclass(frozen=True)
class FetchResult:
    """Fetched response body plus retry metadata."""

    html: str
    attempt_count: int
    max_attempts: int
    retryable_failures: int


class SidearmFetchError(httpx.HTTPError):
    """Fetch failure annotated with retry metadata."""

    def __init__(
        self,
        original_error: httpx.HTTPError,
        *,
        attempt_count: int,
        max_attempts: int,
        retryable: bool,
    ) -> None:
        super().__init__(str(original_error))
        self.original_error = original_error
        self.attempt_count = attempt_count
        self.max_attempts = max_attempts
        self.retryable = retryable


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
    player_stat_rows: list[dict] = field(default_factory=list)
    scoring_plays: list[dict] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)
    raw_html: str = ""
    fetch_attempt_count: int = 1
    fetch_max_attempts: int = 1
    fetch_retryable_failures: int = 0


def current_fetch_retry_policy() -> FetchRetryPolicy:
    """Build the current Sidearm fetch policy from application settings."""
    return FetchRetryPolicy(
        timeout_seconds=settings.SIDEARM_REQUEST_TIMEOUT_SECONDS,
        max_attempts=settings.SIDEARM_FETCH_MAX_ATTEMPTS,
        backoff_seconds=settings.SIDEARM_FETCH_BACKOFF_SECONDS,
    )


async def fetch_boxscore(url: str, timeout_seconds: float | None = None) -> str:
    """Fetch the boxscore HTML."""
    timeout = timeout_seconds or settings.SIDEARM_REQUEST_TIMEOUT_SECONDS
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def fetch_boxscore_with_retries(
    url: str,
    policy: FetchRetryPolicy | None = None,
) -> FetchResult:
    """Fetch a boxscore with retry/backoff for transient source failures."""
    retry_policy = policy or current_fetch_retry_policy()
    retryable_failures = 0

    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            html = await fetch_boxscore(
                url,
                timeout_seconds=retry_policy.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            retryable = is_retryable_fetch_error(exc)
            if retryable:
                retryable_failures += 1

            if not retryable or attempt >= retry_policy.max_attempts:
                raise SidearmFetchError(
                    exc,
                    attempt_count=attempt,
                    max_attempts=retry_policy.max_attempts,
                    retryable=retryable,
                ) from exc

            sleep_seconds = retry_policy.backoff_seconds * (2 ** (attempt - 1))
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
        else:
            return FetchResult(
                html=html,
                attempt_count=attempt,
                max_attempts=retry_policy.max_attempts,
                retryable_failures=retryable_failures,
            )

    raise RuntimeError("Sidearm fetch retry loop exited unexpectedly")


def http_status_from_fetch_error(exc: httpx.HTTPError) -> int | None:
    """Return an HTTP status code from raw or retry-wrapped httpx errors."""
    original = exc.original_error if isinstance(exc, SidearmFetchError) else exc
    if isinstance(original, httpx.HTTPStatusError):
        return original.response.status_code
    return None


def is_retryable_fetch_error(exc: httpx.HTTPError) -> bool:
    """Return whether an HTTP/network failure should be retried."""
    if isinstance(exc, SidearmFetchError):
        return exc.retryable
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 408 or status_code == 429 or status_code >= 500
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.NetworkError,
            httpx.PoolTimeout,
            httpx.ReadError,
            httpx.ReadTimeout,
            httpx.RemoteProtocolError,
            httpx.TimeoutException,
            httpx.WriteError,
            httpx.WriteTimeout,
        ),
    )


def fetch_attempt_count(exc: httpx.HTTPError) -> int:
    """Return attempts used by a failed Sidearm fetch."""
    if isinstance(exc, SidearmFetchError):
        return exc.attempt_count
    return 1


def fetch_max_attempts(exc: httpx.HTTPError) -> int:
    """Return max attempts configured for a failed Sidearm fetch."""
    if isinstance(exc, SidearmFetchError):
        return exc.max_attempts
    return current_fetch_retry_policy().max_attempts


def original_fetch_error_type(exc: httpx.HTTPError) -> str:
    """Return the underlying fetch error class name."""
    if isinstance(exc, SidearmFetchError):
        return type(exc.original_error).__name__
    return type(exc).__name__


def parse_boxscore(url: str, html: str) -> ParsedBoxscore:
    """Parse a Sidearm boxscore HTML document into a structured payload."""
    soup = BeautifulSoup(html, "lxml")
    result = ParsedBoxscore(source_url=url, raw_html=html)

    _extract_metadata(soup, url, result)
    _derive_teams_from_title(result)
    tables = _collect_labelled_tables(soup)

    for table in tables:
        heading_lower = table.heading.lower()
        if _is_score_by_period(heading_lower):
            _ingest_score_by_period(table, result)
        elif _is_scoring_summary(heading_lower):
            _ingest_scoring_summary(table, result)
        elif _is_team_stats(heading_lower):
            result.team_stats.extend(_team_stat_rows(table))
        elif _is_basketball_player_stats(table):
            team = _basketball_team_from_heading(table.heading)
            result.player_stats.append(
                {
                    "category": "boxscore",
                    "team": team,
                    "columns": table.columns,
                    "rows": table.rows,
                }
            )
            result.player_stat_rows.extend(_basketball_player_rows(table, team, result))
        elif _is_unsupported_basketball_player_table(table, result.sport):
            result.parser_warnings.append(
                "Unsupported basketball player table "
                f"'{table.heading}' with columns {table.columns}"
            )
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

    previous = table.find_previous(["h1", "h2", "h3", "h4", "h5"])
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


def _is_score_by_period(heading: str) -> bool:
    return "team score by" in heading


def _is_team_stats(heading: str) -> bool:
    return "team stat" in heading


def _player_category(heading: str) -> str | None:
    for keyword, category in PLAYER_CATEGORY_KEYWORDS.items():
        if keyword in heading:
            return category
    return None


def _is_basketball_player_stats(table: ParsedTable) -> bool:
    """Return whether a table has Sidearm's complete basketball player shape."""
    return BASKETBALL_PLAYER_COLUMNS.issubset(table.columns)


def _is_unsupported_basketball_player_table(
    table: ParsedTable,
    sport: str | None,
) -> bool:
    """Identify player-like basketball tables that must not be silently ignored."""
    return sport in BASKETBALL_SPORTS and "Player" in table.columns


def _basketball_team_from_heading(heading: str) -> str | None:
    """Remove the final score from a Sidearm basketball table caption."""
    team = re.sub(r"\s+\d+\s*$", "", heading).strip()
    return team or None


def _basketball_player_rows(
    table: ParsedTable,
    team: str | None,
    result: ParsedBoxscore,
) -> Iterable[dict]:
    """Parse athlete identity and atomic stats from a basketball player table."""
    if table.raw_table is None:
        return

    for tr in table.raw_table.select("tbody > tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) != len(table.columns):
            result.parser_warnings.append(
                f"Basketball player row for '{team}' has {len(cells)} cells; "
                f"expected {len(table.columns)}"
            )
            continue

        source_values = {
            column: _cell_text(cell)
            for column, cell in zip(table.columns, cells, strict=True)
        }
        jersey_number = source_values["##"] or None
        if jersey_number == "TM":
            continue

        player_cell = cells[table.columns.index("Player")]
        player_name, player_bio_url, source_player_id = _basketball_player_identity(
            player_cell,
            jersey_number,
            result.source_url,
        )
        if not player_name or player_name.lower() in {"team", "totals"}:
            continue

        stats = _basketball_atomic_stats(
            source_values,
            result.parser_warnings,
            team=team,
            player_name=player_name,
        )
        yield {
            "team": team,
            "team_role": _team_role(team, result),
            "is_idaho": _same_team(team, _host_team_from_title(result.title or "")),
            "jersey_number": jersey_number,
            "player_name": player_name,
            "player_bio_url": player_bio_url,
            "source_player_id": source_player_id,
            "starter": source_values["GS"] == "*",
            "stats": stats,
            "source_values": source_values,
        }


def _basketball_player_identity(
    player_cell: Tag,
    jersey_number: str | None,
    source_url: str,
) -> tuple[str, str | None, str | None]:
    """Extract the displayed name and optional Sidearm bio identity from a cell."""
    bio_link = player_cell.find("a", href=re.compile(r"/roster/"))
    if bio_link:
        player_name = _cell_text(bio_link)
        player_bio_url = urljoin(source_url, str(bio_link.get("href")))
        source_player_id = _source_player_id(player_bio_url)
        return player_name, player_bio_url, source_player_id

    player_name = _cell_text(player_cell)
    if jersey_number:
        player_name = re.sub(
            rf"^{re.escape(jersey_number)}\s+",
            "",
            player_name,
        )
    return player_name, None, None


def _source_player_id(player_bio_url: str) -> str | None:
    """Return the terminal numeric id from a Sidearm player bio URL."""
    path = urlparse(player_bio_url).path.rstrip("/")
    match = re.search(r"/(\d+)$", path)
    return match.group(1) if match else None


def _basketball_atomic_stats(
    source_values: dict[str, str],
    warnings: list[str],
    *,
    team: str | None,
    player_name: str,
) -> dict[str, int]:
    """Expand Sidearm basketball cells into additive, integer stat values."""
    stats: dict[str, int] = {}

    for source_column, stat_key in BASKETBALL_SINGLE_VALUE_STATS.items():
        value = _safe_int(source_values[source_column])
        if value is None:
            _warn_unparsed_basketball_stat(
                warnings,
                team,
                player_name,
                source_column,
                source_values[source_column],
            )
            continue
        stats[stat_key] = value

    for source_column, stat_keys in BASKETBALL_PAIRED_VALUE_STATS.items():
        match = re.fullmatch(r"(\d+)-(\d+)", source_values[source_column].strip())
        if match is None:
            _warn_unparsed_basketball_stat(
                warnings,
                team,
                player_name,
                source_column,
                source_values[source_column],
            )
            continue
        stats[stat_keys[0]] = int(match.group(1))
        stats[stat_keys[1]] = int(match.group(2))

    return stats


def _warn_unparsed_basketball_stat(
    warnings: list[str],
    team: str | None,
    player_name: str,
    source_column: str,
    source_value: str,
) -> None:
    warnings.append(
        f"Unable to parse basketball stat {source_column}='{source_value}' "
        f"for {team or 'unknown team'} player {player_name}"
    )


def _team_role(team: str | None, result: ParsedBoxscore) -> str:
    if _same_team(team, result.home_team):
        return "home"
    if _same_team(team, result.away_team):
        return "away"
    return "unknown"


def _same_team(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return _normalized_team_name(left) == _normalized_team_name(right)


def _normalized_team_name(value: str) -> str:
    value = re.sub(r"\bstate\b", "st", value.lower())
    return re.sub(r"[^a-z0-9]", "", value)


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


def _ingest_score_by_period(table: ParsedTable, result: ParsedBoxscore) -> None:
    """Extract final event scores from Sidearm's shared score-by-period table."""
    if len(table.rows) < 2:
        return

    away_row = table.rows[0]
    home_row = table.rows[1]
    if len(away_row) < 3 or len(home_row) < 3:
        return

    final_index = _final_score_column_index(table.columns)
    if final_index is not None:
        result.away_score = _safe_int(_cell_at(away_row, final_index))
        result.home_score = _safe_int(_cell_at(home_row, final_index))
        return

    away_period_scores = [_safe_int(value) for value in away_row[1:]]
    home_period_scores = [_safe_int(value) for value in home_row[1:]]
    paired_scores = [
        (away, home)
        for away, home in zip(away_period_scores, home_period_scores, strict=False)
        if away is not None and home is not None
    ]
    if not paired_scores:
        return

    result.away_score = sum(1 for away, home in paired_scores if away > home)
    result.home_score = sum(1 for away, home in paired_scores if home > away)


def _final_score_column_index(columns: list[str]) -> int | None:
    for index, column in enumerate(columns):
        normalized = column.lower()
        if "total" in normalized or normalized in {"f", "final"}:
            return index
    return None


def _cell_at(row: list[str], index: int) -> str | None:
    if index >= len(row):
        return None
    return row[index]


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
        host = match.group(1).strip()
        if host == "University of Idaho":
            return "Idaho"
        return host
    return None


async def scrape_boxscore(
    url: str,
    policy: FetchRetryPolicy | None = None,
) -> ParsedBoxscore:
    """High-level entry point: fetch + parse."""
    fetch_result = await fetch_boxscore_with_retries(url, policy=policy)
    parsed = parse_boxscore(url, fetch_result.html)
    parsed.fetch_attempt_count = fetch_result.attempt_count
    parsed.fetch_max_attempts = fetch_result.max_attempts
    parsed.fetch_retryable_failures = fetch_result.retryable_failures
    logger.info(
        "Scraped boxscore url=%s attempts=%d team_stats=%d player_groups=%d "
        "player_rows=%d scoring=%d warnings=%d",
        url,
        parsed.fetch_attempt_count,
        len(parsed.team_stats),
        len(parsed.player_stats),
        len(parsed.player_stat_rows),
        len(parsed.scoring_plays),
        len(parsed.parser_warnings),
    )
    return parsed
