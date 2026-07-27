"""Evidence-bound editorial Article and Article Brief persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Article(Base):
    """The canonical editorial work product for one game."""

    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_article_creator_idempotency_key",
        ),
        CheckConstraint(
            "status IN ('brief', 'generating', 'in_edit', 'ready', "
            "'needs_revalidation', 'archived')",
            name="ck_article_status",
        ),
        CheckConstraint(
            "article_type IN ('game_recap', 'player_spotlight', 'achievement_story')",
            name="ck_article_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="brief", server_default="brief", index=True
    )
    article_type: Mapped[str] = mapped_column(String(32), index=True)
    angle: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(255))
    constraints: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    game: Mapped[Game] = relationship()
    suggestion_links: Mapped[list[ArticleAchievementSuggestion]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
    evidence_bundles: Mapped[list[EvidenceBundle]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="EvidenceBundle.version",
    )


class ArticleAchievementSuggestion(Base):
    """The durable link from an Article Brief to an approved suggestion."""

    __tablename__ = "article_achievement_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "suggestion_key",
            name="uq_article_achievement_suggestion",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    achievement_suggestion_id: Mapped[int | None] = mapped_column(
        ForeignKey("achievement_suggestions.id", ondelete="SET NULL"), index=True
    )
    suggestion_key: Mapped[str] = mapped_column(String(255))
    reviewed_fact_hash: Mapped[str] = mapped_column(String(64))
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    article: Mapped[Article] = relationship(back_populates="suggestion_links")
    achievement_suggestion: Mapped[AchievementSuggestion] = relationship()


class EvidenceBundle(Base):
    """An immutable, canonical snapshot of facts allowed for Article writing."""

    __tablename__ = "evidence_bundles"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "version",
            name="uq_evidence_bundle_article_version",
        ),
        CheckConstraint("version > 0", name="ck_evidence_bundle_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONType, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    article: Mapped[Article] = relationship(back_populates="evidence_bundles")


from app.models.achievement import AchievementSuggestion  # noqa: E402
from app.models.game import Game  # noqa: E402
