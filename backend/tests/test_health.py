"""Verify the health check endpoint works."""

import logging

from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import get_db
from app.logging import REQUEST_ID_HEADER
from app.main import app


async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_health_check_emits_request_id_in_response_and_logs(client, caplog):
    caplog.set_level(logging.INFO, logger="app.request")

    response = await client.get("/api/v1/health")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert request_id
    assert any(
        record.name == "app.request"
        and getattr(record, "request_id", None) == request_id
        and "request completed" in record.getMessage()
        for record in caplog.records
    )


async def test_health_check_reuses_supplied_request_id(client, caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    request_id = "request-id-from-client"

    response = await client.get(
        "/api/v1/health",
        headers={REQUEST_ID_HEADER: request_id},
    )

    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert any(
        record.name == "app.request"
        and getattr(record, "request_id", None) == request_id
        for record in caplog.records
    )


async def test_readiness_check(client):
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_check_returns_503_when_database_is_unavailable():
    class BrokenSession:
        async def scalar(self, statement):
            raise SQLAlchemyError("database unavailable")

    async def override_get_db():
        yield BrokenSession()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
