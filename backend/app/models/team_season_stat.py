"""Authoritative team facts at season grain."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class TeamSeasonStat(Base):
    """One source-provided metric value for one team and program season."""

    __tablename__ = "team_season_stats"
    __table_args__ = (
        UniqueConstraint(
            "sport_program_id",
            "season",
            "team_id",
            "stat_definition_id",
            name="uq_team_season_stat_fact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    season: Mapped[str] = mapped_column(String(16), index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    stat_definition_id: Mapped[int] = mapped_column(
        ForeignKey("stat_definitions.id", ondelete="CASCADE"), index=True
    )
    source_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source_field: Mapped[str | None] = mapped_column(String(128))
    source_value: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sport_program: Mapped[SportProgram] = relationship()
    team: Mapped[Team] = relationship()
    stat_definition: Mapped[StatDefinition] = relationship()
    source_snapshot: Mapped[SourceSnapshot | None] = relationship()


from app.models.game import SourceSnapshot  # noqa: E402
from app.models.sport_program import SportProgram  # noqa: E402
from app.models.stat_definition import StatDefinition  # noqa: E402
from app.models.team import Team  # noqa: E402
