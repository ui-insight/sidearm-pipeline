"""Canonical players, external identities, and season memberships."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Player(Base):
    """A canonical person independent of any one source-system identifier."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), index=True)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    external_identities: Mapped[list[PlayerExternalIdentity]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )
    seasons: Mapped[list[PlayerSeason]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class PlayerExternalIdentity(Base):
    """A player id namespaced by source system and institution."""

    __tablename__ = "player_external_identities"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "institution",
            "source_player_id",
            name="uq_player_external_identity_namespace",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    source_system: Mapped[str] = mapped_column(String(64))
    institution: Mapped[str] = mapped_column(String(255))
    source_player_id: Mapped[str] = mapped_column(String(128), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    player: Mapped[Player] = relationship(back_populates="external_identities")


class PlayerSeason(Base):
    """A player's roster membership for one program season."""

    __tablename__ = "player_seasons"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "sport_program_id",
            "season",
            name="uq_player_season_membership",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
    )
    source_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    season: Mapped[str] = mapped_column(String(16), index=True)
    jersey_number: Mapped[str | None] = mapped_column(String(16))
    class_year: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[str | None] = mapped_column(String(64))
    bio_url: Mapped[str | None] = mapped_column(String(1024))

    player: Mapped[Player] = relationship(back_populates="seasons")
    sport_program: Mapped[SportProgram] = relationship()
    team: Mapped[Team | None] = relationship()
    source_snapshot: Mapped[SourceSnapshot | None] = relationship()


from app.models.game import SourceSnapshot  # noqa: E402
from app.models.sport_program import SportProgram  # noqa: E402
from app.models.team import Team  # noqa: E402
