"""Normalized player facts at game grain."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class PlayerGameStat(Base):
    """One atomic metric value for one player in one game."""

    __tablename__ = "player_game_stats"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "player_id",
            "stat_definition_id",
            name="uq_player_game_stat_fact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), index=True
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

    game: Mapped[Game] = relationship()
    player: Mapped[Player] = relationship()
    team: Mapped[Team | None] = relationship()
    stat_definition: Mapped[StatDefinition] = relationship()
    source_snapshot: Mapped[SourceSnapshot | None] = relationship()


from app.models.game import Game, SourceSnapshot  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.stat_definition import StatDefinition  # noqa: E402
from app.models.team import Team  # noqa: E402
