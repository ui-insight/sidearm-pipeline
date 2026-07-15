"""Game and boxscore ORM models."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Game(Base):
    """A single athletic event ingested from a Sidearm boxscore URL.

    The table is still named ``games`` for API compatibility, but it now carries
    the first canonical event fields needed for idempotent ingestion and
    website-ready publication.
    """

    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_games_source_url"),
        UniqueConstraint("canonical_uid", name="uq_games_canonical_uid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_uid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(64), default="sidearm")
    source_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    sport: Mapped[str | None] = mapped_column(String(64))
    sport_name: Mapped[str | None] = mapped_column(String(128))
    gender: Mapped[str | None] = mapped_column(String(32))
    season: Mapped[str | None] = mapped_column(String(16))
    game_date: Mapped[str | None] = mapped_column(String(64))
    event_shape: Mapped[str] = mapped_column(String(64), default="team_contest")
    event_status: Mapped[str] = mapped_column(String(32), default="final")
    publish_status: Mapped[str] = mapped_column(String(32), default="draft")
    home_team: Mapped[str | None] = mapped_column(String(255))
    away_team: Mapped[str | None] = mapped_column(String(255))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(512))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(64))
    location_name: Mapped[str | None] = mapped_column(String(255))
    venue_name: Mapped[str | None] = mapped_column(String(255))
    home_away_neutral: Mapped[str | None] = mapped_column(String(16))
    conference_event: Mapped[bool] = mapped_column(Boolean, default=False)
    exhibition: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_successful_ingest_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_html: Mapped[str | None] = mapped_column(Text)

    team_stats: Mapped[list["TeamStat"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    player_stats: Mapped[list["PlayerStatGroup"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    scoring_plays: Mapped[list["ScoringPlay"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    event_sources: Mapped[list["EventSource"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    source_snapshots: Mapped[list["SourceSnapshot"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["EventStatusHistory"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    ingest_runs: Mapped[list["IngestRun"]] = relationship(
        back_populates="game",
        order_by="IngestRun.started_at.desc()",
        passive_deletes=True,
    )
    generated_content: Mapped[list["GeneratedContent"]] = relationship(  # noqa: F821
        back_populates="game",
        cascade="all, delete-orphan",
        order_by="GeneratedContent.generated_at.desc()",
    )


class TeamStat(Base):
    """A single team-stat row (e.g., 'First Downs', '22', '15')."""

    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    stat_name: Mapped[str] = mapped_column(String(128), nullable=False)
    home_value: Mapped[str | None] = mapped_column(String(64))
    away_value: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped[Game] = relationship(back_populates="team_stats")


class PlayerStatGroup(Base):
    """A table of individual stats for one category (passing, rushing, etc.)."""

    __tablename__ = "player_stat_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    team: Mapped[str | None] = mapped_column(String(255))
    columns: Mapped[list] = mapped_column(JSONType, default=list)
    rows: Mapped[list] = mapped_column(JSONType, default=list)

    game: Mapped[Game] = relationship(back_populates="player_stats")


class ScoringPlay(Base):
    """A single scoring play from the scoring summary."""

    __tablename__ = "scoring_plays"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    period: Mapped[str | None] = mapped_column(String(16))
    clock: Mapped[str | None] = mapped_column(String(16))
    team: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped[Game] = relationship(back_populates="scoring_plays")


class EventSource(Base):
    """A source URL or external identifier associated with an athletic event."""

    __tablename__ = "event_sources"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "source_type",
            "source_url",
            name="uq_event_source_url",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(128), index=True)
    primary_source: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    game: Mapped[Game] = relationship(back_populates="event_sources")
    snapshots: Mapped[list["SourceSnapshot"]] = relationship(
        back_populates="event_source", cascade="all, delete-orphan"
    )


class SourceSnapshot(Base):
    """A raw source payload captured for replay, auditing, and parser debugging.

    Snapshots may belong to an event, but roster and season sources are retained
    without inventing a synthetic game.
    """

    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    event_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_sources.id", ondelete="SET NULL"), index=True
    )
    source_system: Mapped[str] = mapped_column(
        String(64), default="sidearm", server_default="sidearm", nullable=False
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        default="boxscore_html",
        server_default="boxscore_html",
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_body: Mapped[str | None] = mapped_column(Text)

    game: Mapped[Game | None] = relationship(back_populates="source_snapshots")
    event_source: Mapped[EventSource | None] = relationship(back_populates="snapshots")


class EventStatusHistory(Base):
    """A durable record of event lifecycle status changes."""

    __tablename__ = "event_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped[Game] = relationship(back_populates="status_history")


class IngestRun(Base):
    """Durable status history for one ingestion attempt."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id", ondelete="SET NULL"), index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(64), default="manual")
    source_system: Mapped[str] = mapped_column(String(64), default="sidearm")
    source_type: Mapped[str] = mapped_column(String(64), default="boxscore_html")
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(128), index=True)
    sport: Mapped[str | None] = mapped_column(String(64), index=True)
    season: Mapped[str | None] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    http_status: Mapped[int | None] = mapped_column(Integer)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    error_type: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    run_metadata: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)

    game: Mapped[Game | None] = relationship(back_populates="ingest_runs")
