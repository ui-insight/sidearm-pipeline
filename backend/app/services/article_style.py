"""Manage, validate, and resolve immutable athletics Style Guide versions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import StyleGuideVersion
from app.schemas.style_guide import (
    ResolvedStyleGuideRead,
    StyleGuideActivationCreate,
    StyleGuideCreate,
    StyleGuidePreviewCreate,
    StyleGuideResolutionIssueRead,
    StyleGuideSuccessorCreate,
    StyleGuideVersionRead,
    rule_payload,
)

SEED_GUIDE_KEY = "athletics-default"
SEED_GUIDE_VERSION = 1
SEED_GUIDE_NAME = "Vandals Athletics seed guide"
SEED_GUIDE_INSTRUCTIONS = (
    "Use AP style, third person, and measured language. Lead with the approved "
    "achievement and preserve every Coverage Window qualifier exactly. Do not "
    "invent quotes or context."
)
SEED_GUIDE_RULES: list[dict[str, Any]] = [
    {
        "key": "headline-length",
        "category": "length",
        "severity": "error",
        "enforcement": "headline_max_chars",
        "value": 90,
    },
    {
        "key": "unsupported-fact-classes",
        "category": "facts",
        "severity": "error",
        "enforcement": "forbidden_fact_classes",
        "value": ["quotes", "injuries", "attendance", "weather"],
    },
    {
        "key": "measured-language",
        "category": "tone",
        "severity": "error",
        "enforcement": "forbidden_terms",
        "value": ["all cylinders", "statement win", "came to play"],
    },
    {
        "key": "no-exclamation",
        "category": "tone",
        "severity": "warning",
        "enforcement": "forbidden_terms",
        "value": ["!"],
    },
]
ARTICLE_TYPES = ("game_recap", "player_spotlight", "achievement_story")
SCOPE_PRECEDENCE = {
    "shared_athletics": 0,
    "sport": 1,
    "article_type": 2,
    "channel": 3,
}


class StyleGuideNotFoundError(ValueError):
    """Raised when a requested Style Guide version does not exist."""


class StyleGuideConflictError(ValueError):
    """Raised when lifecycle or resolution rules reject a requested transition."""


def canonical_hash(value: Any) -> str:
    """Return a stable SHA-256 for JSON-compatible editorial data."""
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seed_style_content() -> dict[str, Any]:
    """Return the immutable policy fields covered by the seeded version hash."""
    return {
        "guide_key": SEED_GUIDE_KEY,
        "version": SEED_GUIDE_VERSION,
        "name": SEED_GUIDE_NAME,
        "scope_type": "shared_athletics",
        "scope_value": None,
        "instructions": SEED_GUIDE_INSTRUCTIONS,
        "rules": SEED_GUIDE_RULES,
    }


def _immutable_content(
    *,
    guide_key: str,
    version: int,
    name: str,
    scope_type: str,
    scope_value: str | None,
    instructions: str,
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "guide_key": guide_key,
        "version": version,
        "name": name,
        "scope_type": scope_type,
        "scope_value": scope_value,
        "instructions": instructions,
        "rules": rules,
    }


def _version_read(guide: StyleGuideVersion) -> StyleGuideVersionRead:
    return StyleGuideVersionRead.model_validate(guide, from_attributes=True)


async def ensure_seed_style_guide(db: AsyncSession) -> StyleGuideVersion:
    """Return the default active guide, creating it when a database is unseeded."""
    existing = await db.scalar(
        select(StyleGuideVersion).where(
            StyleGuideVersion.guide_key == SEED_GUIDE_KEY,
            StyleGuideVersion.version == SEED_GUIDE_VERSION,
        )
    )
    if existing is not None:
        return existing

    content = seed_style_content()
    now = datetime.now(UTC)
    guide = StyleGuideVersion(
        **content,
        predecessor_version_id=None,
        content_hash=canonical_hash(content),
        active=True,
        lifecycle_state="active",
        created_by="system-seed",
        effective_at=now,
        activated_at=now,
        activated_by="system-seed",
    )
    db.add(guide)
    await db.flush()
    return guide


async def list_style_guides(db: AsyncSession) -> list[StyleGuideVersionRead]:
    """Return every immutable Style Guide version in lineage/version order."""
    guides = list(
        await db.scalars(
            select(StyleGuideVersion).order_by(
                StyleGuideVersion.guide_key,
                StyleGuideVersion.version.desc(),
            )
        )
    )
    return [_version_read(guide) for guide in guides]


async def read_style_guide(db: AsyncSession, version_id: int) -> StyleGuideVersionRead:
    """Return one immutable Style Guide version."""
    guide = await db.get(StyleGuideVersion, version_id)
    if guide is None:
        raise StyleGuideNotFoundError("Style Guide version not found.")
    return _version_read(guide)


async def create_style_guide(
    db: AsyncSession,
    payload: StyleGuideCreate,
    *,
    author: str,
) -> StyleGuideVersionRead:
    """Create version 1 as an immutable draft in a new scoped lineage."""
    if await db.scalar(
        select(StyleGuideVersion.id).where(
            StyleGuideVersion.guide_key == payload.guide_key
        )
    ):
        raise StyleGuideConflictError("That Style Guide key already exists.")

    rules = [rule_payload(rule) for rule in payload.rules]
    content = _immutable_content(
        guide_key=payload.guide_key,
        version=1,
        name=payload.name,
        scope_type=payload.scope_type,
        scope_value=payload.scope_value,
        instructions=payload.instructions,
        rules=rules,
    )
    guide = StyleGuideVersion(
        **content,
        predecessor_version_id=None,
        content_hash=canonical_hash(content),
        active=False,
        lifecycle_state="draft",
        created_by=author,
    )
    db.add(guide)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise StyleGuideConflictError("That Style Guide key already exists.") from exc
    await db.refresh(guide)
    return _version_read(guide)


async def create_style_guide_successor(
    db: AsyncSession,
    predecessor_id: int,
    payload: StyleGuideSuccessorCreate,
    *,
    author: str,
) -> StyleGuideVersionRead:
    """Append one immutable draft successor without editing its predecessor."""
    predecessor = await db.get(StyleGuideVersion, predecessor_id)
    if predecessor is None:
        raise StyleGuideNotFoundError("Style Guide version not found.")
    latest_version = await db.scalar(
        select(StyleGuideVersion.version)
        .where(StyleGuideVersion.guide_key == predecessor.guide_key)
        .order_by(StyleGuideVersion.version.desc())
        .limit(1)
    )
    if latest_version is None or predecessor.version != latest_version:
        raise StyleGuideConflictError(
            "Create a successor from the latest version in this guide lineage."
        )

    version = latest_version + 1
    rules = [rule_payload(rule) for rule in payload.rules]
    content = _immutable_content(
        guide_key=predecessor.guide_key,
        version=version,
        name=payload.name,
        scope_type=predecessor.scope_type,
        scope_value=predecessor.scope_value,
        instructions=payload.instructions,
        rules=rules,
    )
    successor = StyleGuideVersion(
        **content,
        predecessor_version_id=predecessor.id,
        content_hash=canonical_hash(content),
        active=False,
        lifecycle_state="draft",
        created_by=author,
    )
    db.add(successor)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise StyleGuideConflictError(
            "Another successor was created first. Reload the Style Guide history."
        ) from exc
    await db.refresh(successor)
    return _version_read(successor)


def _guide_applies(
    guide: StyleGuideVersion,
    *,
    sport: str | None,
    article_type: str,
    channel: str | None,
) -> bool:
    return (
        guide.scope_type == "shared_athletics"
        or (guide.scope_type == "sport" and guide.scope_value == sport)
        or (guide.scope_type == "article_type" and guide.scope_value == article_type)
        or (guide.scope_type == "channel" and guide.scope_value == channel)
    )


def _issue(
    code: str,
    message: str,
    *,
    rule_key: str | None = None,
    version_ids: list[int] | None = None,
) -> StyleGuideResolutionIssueRead:
    return StyleGuideResolutionIssueRead(
        code=code,
        message=message,
        rule_key=rule_key,
        version_ids=version_ids or [],
    )


def _resolved_snapshot(
    guides: list[StyleGuideVersion],
    *,
    sport: str | None,
    article_type: str,
    channel: str | None,
) -> ResolvedStyleGuideRead:
    applicable = [
        guide
        for guide in guides
        if _guide_applies(
            guide,
            sport=sport,
            article_type=article_type,
            channel=channel,
        )
    ]
    applicable.sort(
        key=lambda guide: (
            SCOPE_PRECEDENCE[guide.scope_type],
            guide.guide_key,
            guide.version,
            guide.id,
        )
    )
    issues: list[StyleGuideResolutionIssueRead] = []
    resolved: dict[str, tuple[dict[str, Any], StyleGuideVersion]] = {}

    for guide in applicable:
        for raw_rule in guide.rules:
            rule = rule_payload(raw_rule)
            previous = resolved.get(rule["key"])
            if previous is None:
                if rule.get("override", False):
                    issues.append(
                        _issue(
                            "orphan_override",
                            f"Rule {rule['key']} declares an override but no less "
                            "specific rule is active in this context.",
                            rule_key=rule["key"],
                            version_ids=[guide.id],
                        )
                    )
                resolved[rule["key"]] = (rule, guide)
                continue

            previous_rule, previous_guide = previous
            previous_precedence = SCOPE_PRECEDENCE[previous_guide.scope_type]
            current_precedence = SCOPE_PRECEDENCE[guide.scope_type]
            if current_precedence == previous_precedence:
                issues.append(
                    _issue(
                        "same_scope_rule_conflict",
                        f"Rule {rule['key']} is defined by more than one active "
                        f"{guide.scope_type.replace('_', ' ')} guide.",
                        rule_key=rule["key"],
                        version_ids=[previous_guide.id, guide.id],
                    )
                )
                continue
            if not rule.get("override", False):
                issues.append(
                    _issue(
                        "override_required",
                        f"Rule {rule['key']} must explicitly override the less "
                        "specific active rule.",
                        rule_key=rule["key"],
                        version_ids=[previous_guide.id, guide.id],
                    )
                )
                continue
            resolved[rule["key"]] = (rule, guide)

    required_terms: dict[str, tuple[str, StyleGuideVersion]] = {}
    forbidden_terms: dict[str, tuple[str, StyleGuideVersion]] = {}
    length_values: dict[str, list[tuple[int, StyleGuideVersion]]] = {}
    for rule, guide in resolved.values():
        if rule["enforcement"] == "required_terms":
            required_terms.update(
                {str(term).casefold(): (str(term), guide) for term in rule["value"]}
            )
        elif rule["enforcement"] == "forbidden_terms":
            forbidden_terms.update(
                {str(term).casefold(): (str(term), guide) for term in rule["value"]}
            )
        elif rule["enforcement"] in {"headline_max_chars", "body_max_chars"}:
            length_values.setdefault(rule["enforcement"], []).append(
                (int(rule["value"]), guide)
            )

    for normalized in sorted(required_terms.keys() & forbidden_terms.keys()):
        required_term, required_guide = required_terms[normalized]
        _, forbidden_guide = forbidden_terms[normalized]
        issues.append(
            _issue(
                "required_forbidden_conflict",
                f"Term {required_term!r} is both required and forbidden.",
                version_ids=[required_guide.id, forbidden_guide.id],
            )
        )
    for enforcement, values in length_values.items():
        distinct = {value for value, _ in values}
        if len(distinct) > 1:
            issues.append(
                _issue(
                    "length_constraint_conflict",
                    f"Resolved {enforcement.replace('_', ' ')} rules disagree: "
                    + ", ".join(str(value) for value in sorted(distinct))
                    + ".",
                    version_ids=[guide.id for _, guide in values],
                )
            )

    versions = [
        {
            "id": guide.id,
            "guide_key": guide.guide_key,
            "version": guide.version,
            "name": guide.name,
            "scope_type": guide.scope_type,
            "scope_value": guide.scope_value,
            "content_hash": guide.content_hash,
        }
        for guide in applicable
    ]
    rules = [
        {
            **rule,
            "source_version_id": guide.id,
            "source_guide_key": guide.guide_key,
            "source_scope_type": guide.scope_type,
            "source_scope_value": guide.scope_value,
        }
        for rule, guide in resolved.values()
    ]
    snapshot = {
        "sport": sport,
        "article_type": article_type,
        "channel": channel,
        "versions": versions,
        "instructions": [guide.instructions for guide in applicable],
        "rules": rules,
    }
    return ResolvedStyleGuideRead(
        **snapshot,
        style_hash=canonical_hash(snapshot),
        valid_for_activation=bool(applicable) and not issues,
        issues=issues,
    )


async def _active_guides(
    db: AsyncSession, *, as_of: datetime | None = None
) -> list[StyleGuideVersion]:
    effective_time = as_of or datetime.now(UTC)
    await ensure_seed_style_guide(db)
    return list(
        await db.scalars(
            select(StyleGuideVersion).where(
                StyleGuideVersion.lifecycle_state == "active",
                StyleGuideVersion.effective_at.is_not(None),
                StyleGuideVersion.effective_at <= effective_time,
            )
        )
    )


async def preview_resolved_style(
    db: AsyncSession,
    payload: StyleGuidePreviewCreate,
) -> ResolvedStyleGuideRead:
    """Preview active resolution, optionally substituting one draft candidate."""
    guides = await _active_guides(db)
    if payload.candidate_version_id is not None:
        candidate = await db.get(StyleGuideVersion, payload.candidate_version_id)
        if candidate is None:
            raise StyleGuideNotFoundError("Style Guide version not found.")
        guides = [guide for guide in guides if guide.guide_key != candidate.guide_key]
        guides.append(candidate)
    return _resolved_snapshot(
        guides,
        sport=payload.sport,
        article_type=payload.article_type,
        channel=payload.channel,
    )


def _candidate_contexts(
    candidate: StyleGuideVersion,
    guides: list[StyleGuideVersion],
) -> list[tuple[str | None, str, str | None]]:
    sports = sorted(
        {
            guide.scope_value
            for guide in [*guides, candidate]
            if guide.scope_type == "sport" and guide.scope_value
        }
    )
    article_types = sorted(
        {
            *ARTICLE_TYPES,
            *(
                guide.scope_value
                for guide in [*guides, candidate]
                if guide.scope_type == "article_type" and guide.scope_value
            ),
        }
    )
    channels = sorted(
        {
            guide.scope_value
            for guide in [*guides, candidate]
            if guide.scope_type == "channel" and guide.scope_value
        }
    )
    sports_or_none: list[str | None] = sports or [None]
    channels_or_none: list[str | None] = [None, *channels]

    if candidate.scope_type == "sport":
        sports_or_none = [candidate.scope_value]
    if candidate.scope_type == "article_type":
        article_types = [str(candidate.scope_value)]
    if candidate.scope_type == "channel":
        channels_or_none = [candidate.scope_value]
    return [
        (sport, article_type, channel)
        for sport in sports_or_none
        for article_type in article_types
        for channel in channels_or_none
    ]


async def activate_style_guide(
    db: AsyncSession,
    version_id: int,
    payload: StyleGuideActivationCreate,
    *,
    actor: str,
) -> StyleGuideVersionRead:
    """Validate and activate a draft, retiring its active lineage predecessor."""
    candidate = await db.scalar(
        select(StyleGuideVersion)
        .where(StyleGuideVersion.id == version_id)
        .with_for_update()
    )
    if candidate is None:
        raise StyleGuideNotFoundError("Style Guide version not found.")
    if candidate.lifecycle_state != "draft":
        raise StyleGuideConflictError("Only a draft Style Guide can be activated.")

    now = datetime.now(UTC)
    effective_at = payload.effective_at or now
    if effective_at > now + timedelta(seconds=1):
        raise StyleGuideConflictError(
            "Future activation is not supported; activate when the guide is effective."
        )

    active = await _active_guides(db, as_of=effective_at)
    active_without_lineage = [
        guide for guide in active if guide.guide_key != candidate.guide_key
    ]
    activation_guides = [*active_without_lineage, candidate]
    issues: list[StyleGuideResolutionIssueRead] = []
    for sport, article_type, channel in _candidate_contexts(
        candidate, active_without_lineage
    ):
        preview = _resolved_snapshot(
            activation_guides,
            sport=sport,
            article_type=article_type,
            channel=channel,
        )
        issues.extend(preview.issues)
    unique_issues = {
        (issue.code, issue.message, tuple(issue.version_ids)): issue for issue in issues
    }
    if unique_issues:
        message = " ".join(issue.message for issue in unique_issues.values())
        raise StyleGuideConflictError(message)

    active_predecessors = list(
        await db.scalars(
            select(StyleGuideVersion)
            .where(
                StyleGuideVersion.guide_key == candidate.guide_key,
                StyleGuideVersion.lifecycle_state == "active",
            )
            .with_for_update()
        )
    )
    for predecessor in active_predecessors:
        predecessor.lifecycle_state = "retired"
        predecessor.active = False
        predecessor.retired_at = now
        predecessor.retired_by = actor

    candidate.lifecycle_state = "active"
    candidate.active = True
    candidate.effective_at = effective_at
    candidate.activated_at = now
    candidate.activated_by = actor
    await db.flush()
    await db.refresh(candidate)
    return _version_read(candidate)


async def retire_style_guide(
    db: AsyncSession,
    version_id: int,
    *,
    actor: str,
) -> StyleGuideVersionRead:
    """Retire an active version without changing any stored policy content."""
    guide = await db.scalar(
        select(StyleGuideVersion)
        .where(StyleGuideVersion.id == version_id)
        .with_for_update()
    )
    if guide is None:
        raise StyleGuideNotFoundError("Style Guide version not found.")
    if guide.lifecycle_state != "active":
        raise StyleGuideConflictError("Only an active Style Guide can be retired.")
    if guide.scope_type == "shared_athletics":
        replacement = await db.scalar(
            select(StyleGuideVersion.id).where(
                StyleGuideVersion.id != guide.id,
                StyleGuideVersion.scope_type == "shared_athletics",
                StyleGuideVersion.lifecycle_state == "active",
                StyleGuideVersion.effective_at.is_not(None),
                StyleGuideVersion.effective_at <= datetime.now(UTC),
            )
        )
        if replacement is None:
            raise StyleGuideConflictError(
                "Activate another shared athletics guide before retiring this one."
            )

    guide.lifecycle_state = "retired"
    guide.active = False
    guide.retired_at = datetime.now(UTC)
    guide.retired_by = actor
    await db.flush()
    await db.refresh(guide)
    return _version_read(guide)


async def resolve_article_style(
    db: AsyncSession,
    *,
    sport: str | None,
    article_type: str,
) -> tuple[StyleGuideVersion, dict[str, Any], str]:
    """Resolve active Article scopes and return one frozen reproducible snapshot."""
    guides = await _active_guides(db)
    preview = _resolved_snapshot(
        guides,
        sport=sport,
        article_type=article_type,
        channel=None,
    )
    if not preview.versions:
        raise RuntimeError("No active Style Guide is available for this Article.")
    if preview.issues:
        raise RuntimeError(
            "The active Style Guide configuration is invalid: "
            + " ".join(issue.message for issue in preview.issues)
        )
    primary = await db.get(StyleGuideVersion, preview.versions[-1].id)
    if primary is None:
        raise RuntimeError("The resolved Style Guide version was not found.")
    snapshot = {
        "sport": preview.sport,
        "article_type": preview.article_type,
        "channel": preview.channel,
        "versions": [version.model_dump(mode="json") for version in preview.versions],
        "instructions": preview.instructions,
        "rules": [rule.model_dump(mode="json") for rule in preview.rules],
    }
    return primary, snapshot, preview.style_hash
