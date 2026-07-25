"""Versioned notability policy and deterministic achievement suggestions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class NotabilityPolicy(Base):
    """An immutable, versioned sport-specific editorial rubric."""

    __tablename__ = "notability_policies"
    __table_args__ = (
        UniqueConstraint(
            "sport_program_id",
            "version",
            name="uq_notability_policy_program_version",
        ),
        CheckConstraint("version > 0", name="ck_notability_policy_version"),
        CheckConstraint("top_n > 0", name="ck_notability_policy_top_n"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    scope_weights: Mapped[dict] = mapped_column(JSONType, nullable=False)
    top_n: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sport_program: Mapped[SportProgram] = relationship()
    metric_rules: Mapped[list[NotabilityPolicyMetric]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
    )


class NotabilityPolicyMetric(Base):
    """One metric's weight, thresholds, and suppression rule in a policy."""

    __tablename__ = "notability_policy_metrics"
    __table_args__ = (
        UniqueConstraint(
            "notability_policy_id",
            "stat_definition_id",
            name="uq_notability_policy_metric",
        ),
        CheckConstraint(
            "importance_weight >= 0",
            name="ck_notability_policy_metric_weight",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    notability_policy_id: Mapped[int] = mapped_column(
        ForeignKey("notability_policies.id", ondelete="CASCADE"), index=True
    )
    stat_definition_id: Mapped[int] = mapped_column(
        ForeignKey("stat_definitions.id", ondelete="CASCADE"), index=True
    )
    importance_weight: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    thresholds: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    policy: Mapped[NotabilityPolicy] = relationship(back_populates="metric_rules")
    stat_definition: Mapped[StatDefinition] = relationship()


class AchievementSuggestion(Base):
    """A persisted comparative fact computed from warehouse history."""

    __tablename__ = "achievement_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "suggestion_key",
            name="uq_achievement_suggestion_game_key",
        ),
        CheckConstraint(
            "achievement_type IN ('career_high', 'season_high', "
            "'threshold_crossing', 'all_time_top_n')",
            name="ck_achievement_suggestion_type",
        ),
        CheckConstraint(
            "scope IN ('career', 'season', 'program')",
            name="ck_achievement_suggestion_scope",
        ),
        CheckConstraint(
            "state IN ('pending', 'approved', 'rejected')",
            name="ck_achievement_suggestion_state",
        ),
        CheckConstraint(
            "notability_score >= 0",
            name="ck_achievement_suggestion_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True
    )
    stat_definition_id: Mapped[int] = mapped_column(
        ForeignKey("stat_definitions.id", ondelete="CASCADE"), index=True
    )
    notability_policy_id: Mapped[int] = mapped_column(
        ForeignKey("notability_policies.id", ondelete="RESTRICT"), index=True
    )
    coverage_window_id: Mapped[int | None] = mapped_column(
        ForeignKey("coverage_windows.id", ondelete="SET NULL"), index=True
    )
    source_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="SET NULL"), index=True
    )
    suggestion_key: Mapped[str] = mapped_column(String(255))
    achievement_type: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(16), index=True)
    computed_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    comparison_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    rank: Mapped[int | None] = mapped_column(Integer)
    notability_score: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    context: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    coverage_context: Mapped[dict] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    phrasing: Mapped[str | None] = mapped_column(String(1024))
    state: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    game: Mapped[Game] = relationship()
    player: Mapped[Player] = relationship()
    stat_definition: Mapped[StatDefinition] = relationship()
    notability_policy: Mapped[NotabilityPolicy] = relationship()
    coverage_window: Mapped[CoverageWindow | None] = relationship()
    source_snapshot: Mapped[SourceSnapshot | None] = relationship()


from app.models.coverage_window import CoverageWindow  # noqa: E402
from app.models.game import Game, SourceSnapshot  # noqa: E402
from app.models.player import Player  # noqa: E402
from app.models.sport_program import SportProgram  # noqa: E402
from app.models.stat_definition import StatDefinition  # noqa: E402
