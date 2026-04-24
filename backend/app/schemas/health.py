"""Health and readiness response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned by the liveness health check."""

    status: str


class ReadinessResponse(BaseModel):
    """Response returned by the dependency readiness check."""

    status: str
