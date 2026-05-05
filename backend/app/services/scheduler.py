"""Background scheduler for automated Sidearm boxscore ingestion.

Runs a periodic ingest cycle that discovers finalized games for every
Release 1 sport and ingests any that have a boxscore URL available.

Enable in ``.env``:

    SCHEDULER_ENABLED=true
    SCHEDULER_INTERVAL_SECONDS=900   # 15 minutes (minimum 60)
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.ingest import ingest_boxscore_url
from app.services.sidearm_schedule import discover_schedule_events
from app.services.source_registry import get_source_registry

logger = logging.getLogger(__name__)

# Explicit season per sport for the current academic year.
# Update these at the start of each new season.
CURRENT_SEASONS: dict[str, str] = {
    "football": "2025",
    "mens-basketball": "2025-26",
    "womens-basketball": "2025-26",
    "womens-soccer": "2025",
    "womens-volleyball": "2025",
}


async def run_ingest_cycle(db_factory: async_sessionmaker) -> None:
    """One complete ingest pass over all Release 1 sports.

    For each sport:
    1. Fetch the Sidearm schedule page.
    2. Keep only finalized events that have a boxscore URL.
    3. Ingest each one (idempotent — updates in-place if already stored).

    Errors on individual sports or individual games are logged and skipped
    so a single failure does not abort the whole cycle.
    """
    registry = get_source_registry()
    sports = registry.release_1_sports
    logger.info("Starting ingest cycle sports=%d", len(sports))

    for sport in sports:
        season = CURRENT_SEASONS.get(sport.sport_slug)
        try:
            events = await discover_schedule_events(sport.sport_slug, season=season)
        except Exception:
            logger.exception(
                "Schedule discovery failed sport=%s season=%s",
                sport.sport_slug,
                season,
            )
            continue

        finals = [e for e in events if e.event_status == "final" and e.boxscore_url]
        logger.info(
            "Discovered sport=%s finals=%d total=%d",
            sport.sport_slug,
            len(finals),
            len(events),
        )

        for event in finals:
            url = event.boxscore_url
            async with db_factory() as db:
                try:
                    await ingest_boxscore_url(url, db, trigger_type="scheduled")
                    logger.debug("Ingested url=%s sport=%s", url, sport.sport_slug)
                except Exception:
                    logger.exception(
                        "Scheduled ingest failed url=%s sport=%s", url, sport.sport_slug
                    )

    logger.info("Ingest cycle complete")


async def scheduler_loop(
    db_factory: async_sessionmaker,
    interval_seconds: float,
) -> None:
    """Run ingest cycles on a fixed interval until the task is cancelled.

    Designed to be started with ``asyncio.create_task()`` from the FastAPI
    lifespan handler. The task is cleaned up on application shutdown via
    ``task.cancel()``.
    """
    logger.info("Scheduler started interval_seconds=%.0f", interval_seconds)
    while True:
        try:
            await run_ingest_cycle(db_factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected error in scheduler cycle")
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise
    logger.info("Scheduler stopped")
