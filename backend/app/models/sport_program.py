"""Sport-program dimension for the athletics data warehouse."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SportProgram(Base):
    """An Idaho athletics program with its season naming convention."""

    __tablename__ = "sport_programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    sport: Mapped[str] = mapped_column(String(64), index=True)
    gender: Mapped[str | None] = mapped_column(String(32))
    season_format: Mapped[str] = mapped_column(
        String(32), default="academic_year", nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
