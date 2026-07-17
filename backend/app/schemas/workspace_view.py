"""Pydantic schemas for shared workspace views."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

WorkspaceViewKind = Literal["season", "comparison"]
WorkspaceViewName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
]

WORKSPACE_VIEW_PARAM_KEYS: dict[WorkspaceViewKind, frozenset[str]] = {
    "season": frozenset({"season", "stat", "scope", "opponent", "limit"}),
    "comparison": frozenset(
        {
            "season",
            "stat",
            "conference",
            "venue",
            "opponent",
            "left",
            "right",
        }
    ),
}


class WorkspaceViewCreate(BaseModel):
    """A validated route/filter definition to share with the deployment."""

    name: WorkspaceViewName
    view: WorkspaceViewKind
    params: dict[str, str] = Field(min_length=1, max_length=7)

    @field_validator("params")
    @classmethod
    def validate_param_values(cls, params: dict[str, str]) -> dict[str, str]:
        """Reject empty or unexpectedly large route parameters."""
        if any(not value.strip() or len(value) > 160 for value in params.values()):
            raise ValueError("workspace view parameters must be 1 to 160 characters")
        return params

    @model_validator(mode="after")
    def validate_param_shape(self) -> "WorkspaceViewCreate":
        """Require the exact supported filter set for the selected view."""
        expected = WORKSPACE_VIEW_PARAM_KEYS[self.view]
        if set(self.params) != expected:
            raise ValueError(
                f"{self.view} workspace views require exactly: "
                f"{', '.join(sorted(expected))}"
            )
        return self


class WorkspaceViewRead(BaseModel):
    """A deployment-wide saved workspace view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    view: WorkspaceViewKind = Field(validation_alias="view_kind")
    params: dict[str, str]
    created_by: str
    created_at: datetime
