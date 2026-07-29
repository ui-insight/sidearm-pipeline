"""Validated API contracts for versioned athletics Style Guides."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

StyleGuideScopeType = Literal["shared_athletics", "sport", "article_type", "channel"]
StyleGuideLifecycleState = Literal["draft", "active", "retired"]
StyleGuideSeverity = Literal["error", "warning", "guidance"]
StyleGuideEnforcement = Literal[
    "prompt_guidance",
    "deterministic_lint",
    "required_terms",
    "forbidden_terms",
    "headline_max_chars",
    "body_max_chars",
    "forbidden_fact_classes",
]
ArticleType = Literal["game_recap", "player_spotlight", "achievement_story"]

GuideKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=128,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
ScopeValue = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
    ),
]
TrimmedName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=255)
]
TrimmedInstructions = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
]
RuleKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=128,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
RuleCategory = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$",
    ),
]
RuleDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)
]


class StyleGuideRule(BaseModel):
    """One stable-keyed immutable Style Guide rule."""

    model_config = ConfigDict(extra="forbid")

    key: RuleKey
    category: RuleCategory
    severity: StyleGuideSeverity
    enforcement: StyleGuideEnforcement
    value: str | int | list[str]
    override: bool = False
    description: RuleDescription | None = None

    @model_validator(mode="after")
    def validate_enforcement_value(self) -> "StyleGuideRule":
        """Require a safe, deterministic value shape for each enforcement type."""
        if self.enforcement == "prompt_guidance":
            if self.severity != "guidance":
                raise ValueError("prompt guidance rules must use guidance severity")
            if not isinstance(self.value, str) or not self.value.strip():
                raise ValueError("prompt guidance requires non-empty text")
            self.value = self.value.strip()
            return self

        if self.enforcement == "deterministic_lint":
            allowed_lints = {"no_all_caps", "no_double_space", "no_exclamation"}
            if not isinstance(self.value, str) or self.value not in allowed_lints:
                raise ValueError(
                    "deterministic lint must be no_all_caps, no_double_space, "
                    "or no_exclamation"
                )
            return self

        if self.enforcement in {
            "required_terms",
            "forbidden_terms",
            "forbidden_fact_classes",
        }:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.enforcement} requires a non-empty term list")
            normalized = [str(value).strip() for value in self.value]
            if any(not value for value in normalized):
                raise ValueError("rule terms must not be empty")
            if len({value.casefold() for value in normalized}) != len(normalized):
                raise ValueError("rule terms must be unique ignoring case")
            self.value = normalized
            return self

        if self.enforcement in {"headline_max_chars", "body_max_chars"}:
            if isinstance(self.value, bool) or not isinstance(self.value, int):
                raise ValueError(f"{self.enforcement} requires an integer")
            if not 1 <= self.value <= 50_000:
                raise ValueError("length constraints must be between 1 and 50000")
            return self

        raise ValueError("unsupported Style Guide enforcement")


class _StyleGuideContent(BaseModel):
    """Shared immutable content fields for initial and successor versions."""

    model_config = ConfigDict(extra="forbid")

    name: TrimmedName
    instructions: TrimmedInstructions
    rules: list[StyleGuideRule] = Field(default_factory=list, max_length=100)

    @field_validator("rules")
    @classmethod
    def validate_unique_rule_keys(
        cls, rules: list[StyleGuideRule]
    ) -> list[StyleGuideRule]:
        """Reject ambiguous duplicate stable keys inside one version."""
        keys = [rule.key for rule in rules]
        if len(keys) != len(set(keys)):
            raise ValueError("Style Guide rule keys must be unique within a version")
        return rules


class StyleGuideCreate(_StyleGuideContent):
    """Create the immutable first draft in one scoped guide lineage."""

    guide_key: GuideKey
    scope_type: StyleGuideScopeType
    scope_value: ScopeValue | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "StyleGuideCreate":
        """Require a value for scoped guides and none for shared athletics."""
        if self.scope_type == "shared_athletics" and self.scope_value is not None:
            raise ValueError("shared athletics scope must not have a scope value")
        if self.scope_type != "shared_athletics" and self.scope_value is None:
            raise ValueError(f"{self.scope_type} scope requires a scope value")
        if self.scope_type == "article_type" and self.scope_value not in {
            "game_recap",
            "player_spotlight",
            "achievement_story",
        }:
            raise ValueError("article type scope value is not supported")
        return self


class StyleGuideSuccessorCreate(_StyleGuideContent):
    """Create an immutable draft successor in an existing guide lineage."""


class StyleGuideActivationCreate(BaseModel):
    """Activate a draft immediately or at an explicit effective timestamp."""

    model_config = ConfigDict(extra="forbid")

    effective_at: datetime | None = None


class StyleGuideRetirementCreate(BaseModel):
    """Explicitly retire one active Style Guide version."""

    model_config = ConfigDict(extra="forbid")


class StyleGuideVersionRead(BaseModel):
    """Lifecycle and immutable content for one Style Guide version."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    guide_key: str
    version: int
    predecessor_version_id: int | None
    name: str
    scope_type: StyleGuideScopeType
    scope_value: str | None
    instructions: str
    rules: list[StyleGuideRule]
    content_hash: str
    lifecycle_state: StyleGuideLifecycleState
    created_by: str
    created_at: datetime
    effective_at: datetime | None
    activated_at: datetime | None
    activated_by: str | None
    retired_at: datetime | None
    retired_by: str | None


class StyleGuidePreviewCreate(BaseModel):
    """The editorial context used to preview deterministic Style Guide resolution."""

    model_config = ConfigDict(extra="forbid")

    sport: ScopeValue | None = None
    article_type: ArticleType
    channel: ScopeValue | None = None
    candidate_version_id: int | None = Field(default=None, gt=0)


class ResolvedStyleGuideVersionRead(BaseModel):
    """One source version contributing to a resolved Style Guide."""

    id: int
    guide_key: str
    version: int
    name: str
    scope_type: StyleGuideScopeType
    scope_value: str | None
    content_hash: str


class ResolvedStyleGuideRuleRead(StyleGuideRule):
    """One effective rule and the immutable version that supplied it."""

    source_version_id: int
    source_guide_key: str
    source_scope_type: StyleGuideScopeType
    source_scope_value: str | None


class StyleGuideResolutionIssueRead(BaseModel):
    """One conflict or invalid configuration discovered during resolution."""

    code: str
    message: str
    rule_key: str | None = None
    version_ids: list[int] = Field(default_factory=list)


class ResolvedStyleGuideRead(BaseModel):
    """A reproducible resolution preview for one Article or rendition context."""

    sport: str | None
    article_type: ArticleType
    channel: str | None
    versions: list[ResolvedStyleGuideVersionRead]
    instructions: list[str]
    rules: list[ResolvedStyleGuideRuleRead]
    style_hash: str
    valid_for_activation: bool
    issues: list[StyleGuideResolutionIssueRead]


def rule_payload(rule: StyleGuideRule | dict[str, Any]) -> dict[str, Any]:
    """Return one normalized JSON-compatible rule mapping."""
    if isinstance(rule, StyleGuideRule):
        return rule.model_dump(mode="json")
    return StyleGuideRule.model_validate(rule).model_dump(mode="json")
