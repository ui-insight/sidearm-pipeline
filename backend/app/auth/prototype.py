"""Small shared-credential session gate for the internal prototype."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import compare_digest
from typing import Final

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.config import settings

SESSION_COOKIE_NAME: Final[str] = "vandals_stats_session"
SESSION_ALGORITHM: Final[str] = "HS256"
SESSION_PURPOSE: Final[str] = "prototype_session"
PUBLIC_API_PATHS: Final[frozenset[str]] = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/session",
        "/api/v1/health",
        "/api/v1/ready",
    }
)


def credentials_are_valid(username: str, password: str) -> bool:
    """Compare the supplied shared credentials without early-exit timing leaks."""
    username_matches = compare_digest(
        username.encode("utf-8"),
        settings.PROTOTYPE_AUTH_USERNAME.encode("utf-8"),
    )
    password_matches = compare_digest(
        password.encode("utf-8"),
        settings.PROTOTYPE_AUTH_PASSWORD.encode("utf-8"),
    )
    return username_matches and password_matches


def issue_session_token(username: str) -> str:
    """Issue a short-lived signed token for the shared prototype account."""
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {
            "sub": username,
            "purpose": SESSION_PURPOSE,
            "iat": issued_at,
            "exp": expires_at,
        },
        settings.SECRET_KEY,
        algorithm=SESSION_ALGORITHM,
    )


def session_username(token: str | None) -> str | None:
    """Return the authenticated username when the session token is valid."""
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[SESSION_ALGORITHM],
        )
    except jwt.InvalidTokenError:
        return None

    username = payload.get("sub")
    if payload.get("purpose") != SESSION_PURPOSE or not isinstance(username, str):
        return None
    if not compare_digest(
        username.encode("utf-8"),
        settings.PROTOTYPE_AUTH_USERNAME.encode("utf-8"),
    ):
        return None
    return username


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the signed session as an HttpOnly same-site cookie."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEV_MODE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the prototype session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=not settings.DEV_MODE,
        samesite="lax",
        path="/",
    )


class PrototypeAuthMiddleware(BaseHTTPMiddleware):
    """Require a valid prototype session for non-public application APIs."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if (
            not settings.PROTOTYPE_AUTH_ENABLED
            or request.method == "OPTIONS"
            or not request.url.path.startswith("/api/v1/")
            or request.url.path in PUBLIC_API_PATHS
        ):
            return await call_next(request)

        username = session_username(request.cookies.get(SESSION_COOKIE_NAME))
        if username is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"Cache-Control": "no-store"},
            )

        request.state.authenticated_username = username
        return await call_next(request)
