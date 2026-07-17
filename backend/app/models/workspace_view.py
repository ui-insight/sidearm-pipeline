"""Deployment-wide saved workspace routes and filters."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class WorkspaceView(Base):
    """A shared, named workspace route definition for the deployment."""

    __tablename__ = "workspace_views"
    __table_args__ = (
        CheckConstraint(
            "view_kind IN ('season', 'comparison')",
            name="ck_workspace_view_kind",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    view_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    params: Mapped[dict[str, str]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
