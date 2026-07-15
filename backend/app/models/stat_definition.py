"""Metric semantics for normalized warehouse facts."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class StatDefinition(Base):
    """The value, aggregation, comparison, and display rules for one metric."""

    __tablename__ = "stat_definitions"
    __table_args__ = (
        UniqueConstraint(
            "sport_program_id",
            "entity_scope",
            "stat_key",
            name="uq_stat_definition_program_scope_key",
        ),
        CheckConstraint(
            "entity_scope IN ('player', 'team', 'event', 'participant')",
            name="ck_stat_definition_entity_scope",
        ),
        CheckConstraint(
            "value_type IN ('integer', 'decimal', 'duration')",
            name="ck_stat_definition_value_type",
        ),
        CheckConstraint(
            "aggregation_method IN ('sum', 'maximum', 'minimum', 'average', "
            "'ratio_from_components', 'latest', 'non_aggregable')",
            name="ck_stat_definition_aggregation_method",
        ),
        CheckConstraint(
            "comparison_direction IN ('higher', 'lower', 'neutral')",
            name="ck_stat_definition_comparison_direction",
        ),
        CheckConstraint(
            "aggregation_method != 'ratio_from_components' OR "
            "(ratio_numerator_stat_key IS NOT NULL AND "
            "ratio_denominator_stat_key IS NOT NULL)",
            name="ck_stat_definition_ratio_components",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sport_program_id: Mapped[int] = mapped_column(
        ForeignKey("sport_programs.id", ondelete="CASCADE"), index=True
    )
    stat_key: Mapped[str] = mapped_column(String(128), index=True)
    display_label: Mapped[str] = mapped_column(String(128))
    entity_scope: Mapped[str] = mapped_column(String(32))
    value_type: Mapped[str] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(64))
    aggregation_method: Mapped[str] = mapped_column(String(32))
    comparison_direction: Mapped[str] = mapped_column(String(16))
    qualifying_minimum: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    display_format: Mapped[str | None] = mapped_column(String(64))
    source_field_aliases: Mapped[list[str]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    ratio_numerator_stat_key: Mapped[str | None] = mapped_column(String(128))
    ratio_denominator_stat_key: Mapped[str | None] = mapped_column(String(128))
    record_book_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    notability_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    sport_program: Mapped[SportProgram] = relationship()


from app.models.sport_program import SportProgram  # noqa: E402
