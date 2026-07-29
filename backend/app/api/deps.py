"""Shared API dependencies for database sessions and role authorization."""

from fastapi import HTTPException, Request, status

from app.config import settings
from app.db.engine import get_db

# Re-export for convenient imports in route handlers
get_db = get_db


async def require_style_steward(request: Request) -> str:
    """Return the actor identity when the session may govern Style Guides."""
    roles = getattr(
        request.state,
        "authenticated_roles",
        settings.prototype_auth_roles_list,
    )
    if "style_steward" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The style_steward role is required for Style Guide management.",
        )
    return getattr(
        request.state,
        "authenticated_username",
        settings.PROTOTYPE_AUTH_USERNAME,
    )
