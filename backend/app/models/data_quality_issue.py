"""Reviewable data-quality failures and uncertainties."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class DataQualityIssue(Base):
    """An identity, reconciliation, source, parser, or coverage problem."""

    __tablename__ = "data_quality_issues"
    __table_args__ = (
        CheckConstraint(
            "issue_type IN ('unresolved_identity', 'reconciliation_mismatch', "
            "'source_conflict', 'parser_failure', 'missing_event', "
            "'coverage_gap')",
            name="ck_data_quality_issue_type",
        ),
        CheckConstraint(
            "status IN ('open', 'in_review', 'resolved', 'accepted_gap')",
            name="ck_data_quality_issue_status",
        ),
        CheckConstraint(
            "severity IN ('info', 'warning', 'error', 'critical')",
            name="ck_data_quality_issue_severity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[int | None] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True
    )
    stat_definition_id: Mapped[int | None] = mapped_column(
        ForeignKey("stat_definitions.id", ondelete="CASCADE"), index=True
    )
    source_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    deduplication_key: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True
    )
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    severity: Mapped[str] = mapped_column(String(32), default="warning")
    summary: Mapped[str] = mapped_column(String(512))
    details: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)

    sport_program: Mapped[SportProgram] = relationship()
    game: Mapped[Game | None] = relationship()
    player: Mapped[Player | None] = relationship()
    team: Mapped[Team | None] = relationship()
    stat_definition: Mapped[StatDefinition | None] = relationship()
    source_snapshot: Mapped[SourceSnapshot | None] = relationship()


from app.models.game import Game, SourceSnapshot  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.sport_program import SportProgram  # noqa: E402
from app.models.stat_definition import StatDefinition  # noqa: E402
from app.models.team import Team  # noqa: E402
