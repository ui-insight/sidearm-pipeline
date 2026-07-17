"""Curated semantic-query catalog and execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.semantic_query import (
    SemanticQueryCatalogRead,
    SemanticQueryRequest,
    SemanticQueryResult,
)
from app.services.record_book import RecordBookMetricNotFoundError
from app.services.semantic_query import (
    SemanticQueryEntityNotFoundError,
    execute_semantic_query,
    get_semantic_query_catalog,
)

router = APIRouter()


@router.get(
    "/catalog",
    response_model=SemanticQueryCatalogRead,
    summary="List curated women's basketball semantic queries",
)
async def list_semantic_queries() -> SemanticQueryCatalogRead:
    """Return stable query ids, question templates, and parameter schemas."""
    return get_semantic_query_catalog()


@router.post(
    "/execute",
    response_model=SemanticQueryResult,
    summary="Execute one curated women's basketball semantic query",
)
async def run_semantic_query(
    request: SemanticQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> SemanticQueryResult:
    """Validate typed parameters and execute only the selected vetted query."""
    try:
        return await execute_semantic_query(db, request)
    except (RecordBookMetricNotFoundError, SemanticQueryEntityNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
