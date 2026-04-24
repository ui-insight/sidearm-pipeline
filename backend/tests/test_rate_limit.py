"""Verify the starter rate limiting middleware."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.rate_limit import configure_rate_limiting


def build_rate_limited_app() -> FastAPI:
    """Create a minimal app for rate limiting tests."""
    app = FastAPI()

    @app.get("/limited")
    async def limited() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    return app


async def test_rate_limiter_returns_429_after_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_EXEMPT_PATHS", '["/health"]')

    app = build_rate_limited_app()
    configure_rate_limiting(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/limited")
        second = await client.get("/limited")
        third = await client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert third.status_code == 429
    assert third.json() == {"detail": "Rate limit exceeded"}
    assert third.headers["Retry-After"] == "60"


async def test_rate_limiter_skips_exempt_paths(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_EXEMPT_PATHS", '["/health"]')

    app = build_rate_limited_app()
    configure_rate_limiting(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/health")
        second = await client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 200
