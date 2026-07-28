"""Evidence-bound editorial Article and Article Brief persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
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
    generation_jobs: Mapped[list[ArticleGenerationJob]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="ArticleGenerationJob.created_at",
    )
    versions: Mapped[list[ArticleVersion]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="ArticleVersion.version",
        foreign_keys="ArticleVersion.article_id",
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


class StyleGuideVersion(Base):
    """One immutable, reproducible version of an editorial Style Guide."""

    __tablename__ = "style_guide_versions"
    __table_args__ = (
        UniqueConstraint(
            "guide_key",
            "version",
            name="uq_style_guide_key_version",
        ),
        CheckConstraint("version > 0", name="ck_style_guide_version"),
        CheckConstraint(
            "scope_type IN ('shared_athletics', 'sport', 'article_type', 'channel')",
            name="ck_style_guide_scope_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    guide_key: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_value: Mapped[str | None] = mapped_column(String(128), index=True)
    instructions: Mapped[str] = mapped_column(Text)
    rules: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ArticleGenerationJob(Base):
    """Durable work record for one evidence-bound writer request."""

    __tablename__ = "article_generation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "requested_by",
            "idempotency_key",
            name="uq_article_generation_request",
        ),
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_article_generation_job_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_article_generation_attempts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    evidence_bundle_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_bundles.id", ondelete="RESTRICT"), index=True
    )
    style_guide_version_id: Mapped[int] = mapped_column(
        ForeignKey("style_guide_versions.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(
        String(32), default="queued", server_default="queued", index=True
    )
    requested_by: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    writer_input: Mapped[dict] = mapped_column(JSONType, nullable=False)
    style_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    style_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    validation_results: Mapped[list[dict]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    article: Mapped[Article] = relationship(back_populates="generation_jobs")
    evidence_bundle: Mapped[EvidenceBundle] = relationship()
    style_guide_version: Mapped[StyleGuideVersion] = relationship()
    article_version: Mapped[ArticleVersion | None] = relationship(
        back_populates="generation_job",
        uselist=False,
    )


class ArticleVersion(Base):
    """An immutable AI or human Article checkpoint."""

    __tablename__ = "article_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "version", name="uq_article_version"),
        UniqueConstraint("generation_job_id", name="uq_article_version_generation_job"),
        CheckConstraint("version > 0", name="ck_article_version_number"),
        CheckConstraint("origin IN ('ai', 'human')", name="ck_article_version_origin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    parent_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("article_versions.id", ondelete="RESTRICT"), index=True
    )
    evidence_bundle_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_bundles.id", ondelete="RESTRICT"), index=True
    )
    style_guide_version_id: Mapped[int] = mapped_column(
        ForeignKey("style_guide_versions.id", ondelete="RESTRICT"), index=True
    )
    generation_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("article_generation_jobs.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(16))
    headline: Mapped[str] = mapped_column(Text)
    headline_evidence_ids: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    body: Mapped[str] = mapped_column(Text)
    blocks: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    author: Mapped[str | None] = mapped_column(String(128))
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64), index=True)
    style_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    style_hash: Mapped[str] = mapped_column(String(64), index=True)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    validation_results: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    article: Mapped[Article] = relationship(
        back_populates="versions",
        foreign_keys=[article_id],
    )
    parent_version: Mapped[ArticleVersion | None] = relationship(
        remote_side="ArticleVersion.id"
    )
    evidence_bundle: Mapped[EvidenceBundle] = relationship()
    style_guide_version: Mapped[StyleGuideVersion] = relationship()
    generation_job: Mapped[ArticleGenerationJob | None] = relationship(
        back_populates="article_version"
    )


from app.models.achievement import AchievementSuggestion  # noqa: E402
from app.models.game import Game  # noqa: E402
