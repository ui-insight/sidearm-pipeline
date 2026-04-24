"""Generated content ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class GeneratedContent(Base):
    """A bundle of AI-generated coverage for one game (recap + spotlight + social)."""

    __tablename__ = "generated_content"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    recap: Mapped[str] = mapped_column(Text)
    spotlight_player: Mapped[str | None] = mapped_column(String(255))
    spotlight_body: Mapped[str] = mapped_column(Text)
    social_post: Mapped[str] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    game: Mapped["Game"] = relationship(back_populates="generated_content")  # noqa: F821
