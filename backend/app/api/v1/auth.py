"""Prototype authentication endpoints."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth.prototype import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    credentials_are_valid,
    issue_session_token,
    session_username,
    set_session_cookie,
)
from app.config import settings
from app.schemas.auth import PrototypeLoginRequest, PrototypeSessionRead

router = APIRouter()


@router.get("/session", response_model=PrototypeSessionRead)
async def read_prototype_session(
    request: Request,
    response: Response,
) -> PrototypeSessionRead:
    """Return the current shared-account authentication state."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.PROTOTYPE_AUTH_ENABLED:
        return PrototypeSessionRead(
            authenticated=True,
            username=settings.PROTOTYPE_AUTH_USERNAME,
            roles=settings.prototype_auth_roles_list,
        )

    username = session_username(request.cookies.get(SESSION_COOKIE_NAME))
    return PrototypeSessionRead(
        authenticated=username is not None,
        username=username,
        roles=settings.prototype_auth_roles_list if username is not None else [],
    )


@router.post("/login", response_model=PrototypeSessionRead)
async def login_prototype_user(
    payload: PrototypeLoginRequest,
    response: Response,
) -> PrototypeSessionRead:
    """Validate the shared prototype credentials and start a signed session."""
    if not settings.PROTOTYPE_AUTH_ENABLED:
        return PrototypeSessionRead(
            authenticated=True,
            username=settings.PROTOTYPE_AUTH_USERNAME,
            roles=settings.prototype_auth_roles_list,
        )

    if not credentials_are_valid(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username or password is incorrect",
            headers={"Cache-Control": "no-store"},
        )

    token = issue_session_token(payload.username)
    set_session_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return PrototypeSessionRead(
        authenticated=True,
        username=payload.username,
        roles=settings.prototype_auth_roles_list,
    )


@router.post("/logout", response_model=PrototypeSessionRead)
async def logout_prototype_user(response: Response) -> PrototypeSessionRead:
    """Clear the current shared-account session."""
    clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return PrototypeSessionRead(authenticated=False)
