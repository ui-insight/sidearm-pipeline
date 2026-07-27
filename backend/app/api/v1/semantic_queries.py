"""Curated semantic-query catalog and execution endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db
from app.schemas.semantic_query import (
    SemanticQueryCatalogRead,
    SemanticQueryRequest,
    SemanticQueryResult,
    SemanticWorkspaceOptionsRead,
)
from app.schemas.semantic_question import (
    SemanticQuestionAnswerRead,
    SemanticQuestionRequest,
)
from app.services.record_book import RecordBookMetricNotFoundError
from app.services.semantic_query import (
    SemanticQueryEntityNotFoundError,
    execute_semantic_query,
    get_semantic_query_catalog,
    get_semantic_workspace_options,
)
from app.services.semantic_question import (
    SemanticQuestionAIError,
    ask_semantic_question,
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


@router.get(
    "/options",
    response_model=SemanticWorkspaceOptionsRead,
    summary="List women's basketball workspace filter options",
)
async def list_workspace_options(
    db: AsyncSession = Depends(get_db),
) -> SemanticWorkspaceOptionsRead:
    """Return available seasons, metrics, and supported leaderboard sizes."""
    return await get_semantic_workspace_options(db)


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


@router.post(
    "/ask",
    response_model=SemanticQuestionAnswerRead,
    summary="Answer a natural-language question through the semantic catalog",
)
async def ask_question(
    request: SemanticQuestionRequest,
    db: AsyncSession = Depends(get_db),
) -> SemanticQuestionAnswerRead:
    """Map an SID question to one vetted query and return its visible evidence."""
    try:
        return await ask_semantic_question(db, question=request.question.strip())
    except (RecordBookMetricNotFoundError, SemanticQueryEntityNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SemanticQuestionAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
