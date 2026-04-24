"""Typed access to the Sidearm source registry."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "source_registry.json"


class SourcePatterns(BaseModel):
    """URL templates for one sport's authoritative Sidearm sources."""

    schedule_url: str
    boxscore_url_pattern: str | None = None


class PollingPolicy(BaseModel):
    """Polling cadence policy in seconds for one sport."""

    final_only: bool = True
    pregame_seconds: int = Field(ge=0)
    live_seconds: int = Field(ge=0)
    postgame_seconds: int = Field(ge=0)


class SportSource(BaseModel):
    """Source registry entry for one sport."""

    sport_slug: str
    sport_name: str
    gender: str | None = None
    release_scope: str
    event_shape: str
    parser_strategy: str
    source_patterns: SourcePatterns
    supported_source_types: list[str]
    polling_policy: PollingPolicy
    notes: list[str] = []


class SourceRegistry(BaseModel):
    """Configured source coverage for one Sidearm host."""

    version: str
    source_system: str
    base_url: HttpUrl
    sports: list[SportSource]

    def get_sport(self, sport_slug: str) -> SportSource | None:
        """Return one sport entry by its Sidearm slug."""
        return next(
            (sport for sport in self.sports if sport.sport_slug == sport_slug),
            None,
        )

    def require_sport(self, sport_slug: str) -> SportSource:
        """Return one sport entry or raise a clear configuration error."""
        sport = self.get_sport(sport_slug)
        if sport is None:
            raise KeyError(f"No source registry entry for sport '{sport_slug}'")
        return sport

    @property
    def release_1_sports(self) -> list[SportSource]:
        """Return sports currently in Release 1 scope."""
        return [sport for sport in self.sports if sport.release_scope == "release_1"]


def load_source_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> SourceRegistry:
    """Load and validate a source registry JSON file."""
    registry_path = Path(path)
    with registry_path.open(encoding="utf-8") as handle:
        return SourceRegistry.model_validate(json.load(handle))


@lru_cache
def get_source_registry() -> SourceRegistry:
    """Load the bundled source registry once per process."""
    return load_source_registry(DEFAULT_REGISTRY_PATH)
