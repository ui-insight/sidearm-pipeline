"""Schemas for the shared-credential prototype login."""

from pydantic import BaseModel, Field


class PrototypeLoginRequest(BaseModel):
    """Credentials submitted by the prototype login screen."""

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class PrototypeSessionRead(BaseModel):
    """Current prototype session state."""

    authenticated: bool
    username: str | None = None
