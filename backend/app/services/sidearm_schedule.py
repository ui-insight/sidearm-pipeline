"""Parser for Sidearm schedule pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from app.config import settings
from app.services.sidearm_scraper import USER_AGENT
from app.services.source_registry import SportSource, get_source_registry


@dataclass
class ParsedScheduleEvent:
    """One event discovered from a Sidearm schedule page."""

    sport_slug: str
    sport_name: str
    gender: str | None
    season: str | None
    source_system: str
    schedule_url: str
    source_event_id: str | None
    opponent_source_id: str | None
    opponent_name: str | None
    event_status: str
    home_away_neutral: str | None
    event_date: date | None
    date_text: str | None
    time_text: str | None
    location_name: str | None
    venue_name: str | None
    conference_name: str | None
    conference_event: bool
    result_status: str | None
    team_score: int | None
    opponent_score: int | None
    source_urls: dict[str, str] = field(default_factory=dict)

    @property
    def boxscore_url(self) -> str | None:
        return self.source_urls.get("boxscore_html")


async def fetch_schedule(url: str) -> str:
    """Fetch a Sidearm schedule HTML page."""
    async with httpx.AsyncClient(
        timeout=settings.SIDEARM_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def discover_schedule_events(
    sport_slug: str,
    season: str | None = None,
) -> list[ParsedScheduleEvent]:
    """Fetch and parse the configured schedule page for one registered sport."""
    registry = get_source_registry()
    sport = registry.require_sport(sport_slug)
    schedule_path = sport.source_patterns.schedule_url.rstrip("/")
    if season:
        if not re.fullmatch(r"20\d{2}(?:-\d{2})?", season):
            raise ValueError(
                "Season must be a four-digit year or academic year like 2025-26"
            )
        schedule_path = f"{schedule_path}/{season}"

    schedule_url = urljoin(str(registry.base_url), schedule_path)
    html = await fetch_schedule(schedule_url)
    return parse_schedule(html, sport=sport, schedule_url=schedule_url)


def parse_schedule(
    html: str,
    *,
    sport: SportSource,
    schedule_url: str,
) -> list[ParsedScheduleEvent]:
    """Parse rendered Sidearm schedule game rows into structured events."""
    soup = BeautifulSoup(html, "lxml")
    season = _extract_season(soup, schedule_url)

    events: list[ParsedScheduleEvent] = []
    for row in soup.select("li.sidearm-schedule-game"):
        if not isinstance(row, Tag):
            continue

        date_text, time_text = _date_and_time(row)
        event = ParsedScheduleEvent(
            sport_slug=sport.sport_slug,
            sport_name=sport.sport_name,
            gender=sport.gender,
            season=season,
            source_system="sidearm",
            schedule_url=schedule_url,
            source_event_id=_attr(row, "data-game-id"),
            opponent_source_id=_attr(row, "data-game-opponent-id"),
            opponent_name=_opponent_name(row),
            event_status=_event_status(row),
            home_away_neutral=_home_away_neutral(row),
            event_date=_event_date(date_text, season),
            date_text=date_text,
            time_text=time_text,
            location_name=_location_parts(row)[0],
            venue_name=_location_parts(row)[1],
            conference_name=_conference_name(row),
            conference_event=_conference_event(row),
            result_status=_result(row)[0],
            team_score=_result(row)[1],
            opponent_score=_result(row)[2],
            source_urls=_source_urls(row, schedule_url),
        )
        events.append(event)

    return events


def _attr(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    return str(value).strip() if value else None


def _extract_season(soup: BeautifulSoup, schedule_url: str) -> str | None:
    url_match = re.search(r"/schedule/(20\d{2}(?:-\d{2})?)", schedule_url)
    if url_match:
        return url_match.group(1)

    selected = soup.select_one("#sidearm-schedule-select-season option[selected]")
    if selected:
        value = selected.get("value") or selected.get_text(" ", strip=True)
        match = re.search(r"(20\d{2}(?:-\d{2})?)", str(value))
        if match:
            return match.group(1)

    title = soup.find("title")
    if title:
        match = re.search(
            r"\b(20\d{2}(?:-\d{2})?)\b",
            title.get_text(" ", strip=True),
        )
        if match:
            return match.group(1)

    return None


def _date_and_time(row: Tag) -> tuple[str | None, str | None]:
    date_block = row.select_one(".sidearm-schedule-game-opponent-date")
    if not date_block:
        return None, None

    spans = [
        span.get_text(" ", strip=True)
        for span in date_block.find_all("span", recursive=False)
        if span.get_text(" ", strip=True)
    ]
    date_text = spans[0] if spans else None
    time_text = spans[1] if len(spans) > 1 else None
    return date_text, time_text


def _event_date(date_text: str | None, season: str | None) -> date | None:
    if not date_text or not season:
        return None

    match = re.match(r"^([A-Za-z]{3,9})\s+(\d{1,2})", date_text)
    if not match:
        return None

    month_names = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    month_key = match.group(1).lower()[:4].rstrip(".")
    month = month_names.get(month_key) or month_names.get(month_key[:3])
    if month is None:
        return None

    return date(_season_year_for_month(season, month), month, int(match.group(2)))


def _season_year_for_month(season: str, month: int) -> int:
    start_year = int(season[:4])
    if "-" not in season:
        return start_year

    # Academic-year schedules use fall months in the first calendar year and
    # winter/spring months in the following calendar year.
    return start_year + 1 if month <= 8 else start_year


def _opponent_name(row: Tag) -> str | None:
    opponent = row.select_one(".sidearm-schedule-game-opponent-name")
    if not opponent:
        return None
    return _clean_text(opponent)


def _event_status(row: Tag) -> str:
    classes = set(row.get("class") or [])
    if "sidearm-schedule-game-completed" in classes:
        return "final"
    if "sidearm-schedule-game-cancelled" in classes:
        return "canceled"
    if "sidearm-schedule-game-postponed" in classes:
        return "postponed"
    return "scheduled"


def _home_away_neutral(row: Tag) -> str | None:
    classes = set(row.get("class") or [])
    if "sidearm-schedule-home-game" in classes:
        return "home"
    if "sidearm-schedule-away-game" in classes:
        return "away"
    if "sidearm-schedule-neutral-game" in classes:
        return "neutral"
    return None


def _location_parts(row: Tag) -> tuple[str | None, str | None]:
    block = row.select_one(".x-large-4 .sidearm-schedule-game-location")
    if not block:
        block = row.select_one(".sidearm-schedule-game-location")
    if not block:
        return None, None

    values = [
        _clean_text(span)
        for span in block.find_all("span", recursive=False)
        if _clean_text(span)
    ]
    location = values[0] if values else None
    venue = values[1] if len(values) > 1 else None
    return location, venue


def _conference_name(row: Tag) -> str | None:
    conference = row.select_one(".sidearm-schedule-game-conference")
    if conference:
        return _clean_text(conference)
    return None


def _conference_event(row: Tag) -> bool:
    if _conference_name(row):
        return True
    marker = row.select_one(".sidearm-schedule-game-conference-small")
    return marker is not None and "*" in _clean_text(marker)


def _result(row: Tag) -> tuple[str | None, int | None, int | None]:
    result = row.select_one(".sidearm-schedule-game-result")
    if not result:
        return None, None, None

    text = _clean_text(result)
    status_match = re.search(r"\b([WLT])\s*,", text)
    score_match = re.search(r"(\d+)\s*-\s*(\d+)", text)
    return (
        status_match.group(1) if status_match else None,
        int(score_match.group(1)) if score_match else None,
        int(score_match.group(2)) if score_match else None,
    )


def _source_urls(row: Tag, schedule_url: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    link_selectors = {
        "boxscore_html": ".sidearm-schedule-game-links-boxscore a",
        "recap_html": ".sidearm-schedule-game-links-recap a",
        "live_stats": ".sidearm-schedule-game-links-stats a",
    }

    for source_type, selector in link_selectors.items():
        link = row.select_one(selector)
        if link and link.get("href"):
            sources[source_type] = urljoin(schedule_url, str(link["href"]))

    gamefile = row.select_one(".sidearm-schedule-game-links-gamefile a")
    if not gamefile:
        gamefile = row.select_one(".sidearm-schedule-game-links-gamefiles a")
    if gamefile and gamefile.get("href"):
        sources["gamefile"] = urljoin(schedule_url, str(gamefile["href"]))

    return sources


def _clean_text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()
