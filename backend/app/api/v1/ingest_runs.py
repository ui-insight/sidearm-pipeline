"""Ingest job history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.models.game import IngestRun
from app.schemas.ingest import IngestRunRead

router = APIRouter()


@router.get(
    "",
    response_model=list[IngestRunRead],
    summary="List recent ingest runs",
)
async def list_ingest_runs(
    status: str | None = Query(default=None, description="Optional run status filter."),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[IngestRunRead]:
    """Return recent ingest attempts for operations and troubleshooting."""
    stmt = select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(IngestRun.status == status)

    result = await db.scalars(stmt)
    return [IngestRunRead.model_validate(row) for row in result.all()]
