"""Coverage boundaries attached to warehouse claims."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class CoverageWindow(Base):
    """The verified season and grain boundary for a warehouse metric."""

    __tablename__ = "coverage_windows"
    __table_args__ = (
        CheckConstraint(
            "grain IN ('game', 'season', 'career', 'match', 'heat', 'round', "
            "'meet', 'tournament')",
            name="ck_coverage_window_grain",
        ),
        CheckConstraint(
            "completeness IN ('complete', 'partial', 'unknown', 'unavailable')",
            name="ck_coverage_window_completeness",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    stat_definition_id: Mapped[int | None] = mapped_column(
        ForeignKey("stat_definitions.id", ondelete="CASCADE"), index=True
    )
    grain: Mapped[str] = mapped_column(String(32), index=True)
    source_system: Mapped[str] = mapped_column(String(64))
    first_season: Mapped[str | None] = mapped_column(String(16))
    last_season: Mapped[str | None] = mapped_column(String(16))
    completeness: Mapped[str] = mapped_column(String(32), index=True)
    known_limitations: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sport_program: Mapped[SportProgram] = relationship()
    stat_definition: Mapped[StatDefinition | None] = relationship()


from app.models.sport_program import SportProgram  # noqa: E402
from app.models.stat_definition import StatDefinition  # noqa: E402
