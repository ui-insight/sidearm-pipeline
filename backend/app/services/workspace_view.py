"""Persistence operations for deployment-wide workspace views."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace_view import WorkspaceView
from app.schemas.workspace_view import WorkspaceViewCreate

MAX_SHARED_WORKSPACE_VIEWS = 100


async def list_workspace_views(db: AsyncSession) -> list[WorkspaceView]:
    """Return the bounded shared collection in deterministic newest-first order."""
    return list(
        await db.scalars(
            select(WorkspaceView)
            .order_by(WorkspaceView.created_at.desc(), WorkspaceView.id.desc())
            .limit(MAX_SHARED_WORKSPACE_VIEWS)
        )
    )


async def create_workspace_view(
    db: AsyncSession,
    request: WorkspaceViewCreate,
    *,
    created_by: str,
) -> WorkspaceView:
    """Persist one validated shared workspace route definition."""
    workspace_view = WorkspaceView(
        name=request.name,
        view_kind=request.view,
        params=request.params,
        created_by=created_by,
    )
    db.add(workspace_view)
    await db.flush()
    await db.refresh(workspace_view)
    return workspace_view


async def delete_workspace_view(db: AsyncSession, view_id: str) -> bool:
    """Delete one shared view, returning whether it existed."""
    workspace_view = await db.get(WorkspaceView, view_id)
    if workspace_view is None:
        return False
    await db.delete(workspace_view)
    return True
