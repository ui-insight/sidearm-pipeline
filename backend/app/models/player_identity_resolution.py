"""Persistent human decisions for unresolved player source rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class PlayerIdentityResolution(Base):
    """A reviewed source-row signature mapped to one canonical player."""

    __tablename__ = "player_identity_resolutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    source_system: Mapped[str] = mapped_column(String(64))
    institution: Mapped[str] = mapped_column(String(255))
    season: Mapped[str] = mapped_column(String(16))
    source_player_id: Mapped[str | None] = mapped_column(String(128), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255))
    jersey_number: Mapped[str | None] = mapped_column(String(16))
    created_from_issue_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_quality_issues.id", ondelete="SET NULL"), index=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sport_program: Mapped[SportProgram] = relationship()
    player: Mapped[Player] = relationship()
    created_from_issue: Mapped[DataQualityIssue | None] = relationship()


from app.models.data_quality_issue import DataQualityIssue  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.sport_program import SportProgram  # noqa: E402
