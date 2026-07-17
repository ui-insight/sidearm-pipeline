"""Deployment-wide shared workspace-view endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.schemas.workspace_view import WorkspaceViewCreate, WorkspaceViewRead
from app.services.workspace_view import (
    create_workspace_view,
    delete_workspace_view,
    list_workspace_views,
)

router = APIRouter()


def _request_username(request: Request) -> str:
    """Return middleware identity or the configured local-development identity."""
    return getattr(
        request.state,
        "authenticated_username",
        settings.PROTOTYPE_AUTH_USERNAME,
    )


@router.get("", response_model=list[WorkspaceViewRead])
async def get_workspace_views(
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceViewRead]:
    """List the deployment's bounded shared workspace-view collection."""
    views = await list_workspace_views(db)
    return [WorkspaceViewRead.model_validate(view) for view in views]


@router.post(
    "",
    response_model=WorkspaceViewRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_workspace_view(
    payload: WorkspaceViewCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceViewRead:
    """Save one route/filter definition for everyone signed into the deployment."""
    view = await create_workspace_view(
        db,
        payload,
        created_by=_request_username(request),
    )
    await db.commit()
    return WorkspaceViewRead.model_validate(view)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_workspace_view(
    view_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete one shared view for everyone signed into the deployment."""
    if not await delete_workspace_view(db, str(view_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace view not found",
        )
    await db.commit()
