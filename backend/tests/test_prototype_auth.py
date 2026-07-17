"""Verify the shared-credential prototype session gate."""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def enable_prototype_auth(monkeypatch):
    """Enable deterministic shared credentials for each auth test."""
    monkeypatch.setattr(settings, "PROTOTYPE_AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "PROTOTYPE_AUTH_USERNAME", "prototype-user")
    monkeypatch.setattr(settings, "PROTOTYPE_AUTH_PASSWORD", "prototype-pass")
    monkeypatch.setattr(
        settings,
        "SECRET_KEY",
        "test-session-signing-secret-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "DEV_MODE", True)


async def test_protected_api_requires_a_session_but_health_stays_public(client):
    session = await client.get("/api/v1/auth/session")
    protected = await client.get("/api/v1/games")
    shared_views = await client.get("/api/v1/workspace-views")
    health = await client.get("/api/v1/health")

    assert session.status_code == 200
    assert session.json() == {"authenticated": False, "username": None}
    assert session.headers["cache-control"] == "no-store"
    assert protected.status_code == 401
    assert protected.json() == {"detail": "Authentication required"}
    assert shared_views.status_code == 401
    assert health.status_code == 200


async def test_invalid_credentials_are_rejected(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "prototype-user", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Username or password is incorrect"}
    assert response.headers["cache-control"] == "no-store"
    assert "vandals_stats_session" not in response.cookies


async def test_login_cookie_unlocks_the_api_and_logout_clears_it(client):
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "prototype-user", "password": "prototype-pass"},
    )

    assert login.status_code == 200
    assert login.json() == {
        "authenticated": True,
        "username": "prototype-user",
    }
    cookie_header = login.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header

    protected = await client.get("/api/v1/games")
    assert protected.status_code == 200

    shared_view = await client.post(
        "/api/v1/workspace-views",
        json={
            "name": "Authenticated view",
            "view": "season",
            "params": {
                "season": "2025-26",
                "stat": "points",
                "scope": "all",
                "opponent": "all",
                "limit": "10",
            },
        },
    )
    assert shared_view.status_code == 201
    assert shared_view.json()["created_by"] == "prototype-user"

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False, "username": None}
    assert "max-age=0" in logout.headers["set-cookie"].lower()

    protected_after_logout = await client.get("/api/v1/games")
    assert protected_after_logout.status_code == 401


async def test_production_session_cookie_is_secure(client, monkeypatch):
    monkeypatch.setattr(settings, "DEV_MODE", False)

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "prototype-user", "password": "prototype-pass"},
    )

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


async def test_disabled_prototype_gate_preserves_local_access(client, monkeypatch):
    monkeypatch.setattr(settings, "PROTOTYPE_AUTH_ENABLED", False)

    session = await client.get("/api/v1/auth/session")
    games = await client.get("/api/v1/games")

    assert session.json() == {
        "authenticated": True,
        "username": "prototype-user",
    }
    assert games.status_code == 200
