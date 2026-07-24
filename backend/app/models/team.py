"""Canonical teams and observed source aliases."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Team(Base):
    """A canonical Idaho or opponent team identity."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True)
    short_name: Mapped[str | None] = mapped_column(String(128))
    institution: Mapped[str | None] = mapped_column(String(255))
    is_idaho: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    aliases: Mapped[list[OpponentAlias]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class OpponentAlias(Base):
    """A source-specific team label resolved to one canonical Team."""

    __tablename__ = "opponent_aliases"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "sport_program_id",
            "normalized_alias",
            name="uq_opponent_alias_namespace",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    source_system: Mapped[str] = mapped_column(String(64))
    observed_name: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255))

    team: Mapped[Team] = relationship(back_populates="aliases")
    sport_program: Mapped[SportProgram] = relationship()


from app.models.sport_program import SportProgram  # noqa: E402
