"""Seed and resolve immutable Style Guide versions for Article generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import StyleGuideVersion

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


async def ensure_seed_style_guide(db: AsyncSession) -> StyleGuideVersion:
    """Return the seeded guide, creating it for local/test databases if absent."""
    existing = await db.scalar(
        select(StyleGuideVersion).where(
            StyleGuideVersion.guide_key == SEED_GUIDE_KEY,
            StyleGuideVersion.version == SEED_GUIDE_VERSION,
        )
    )
    if existing is not None:
        return existing

    content = seed_style_content()
    guide = StyleGuideVersion(
        **content,
        content_hash=canonical_hash(content),
        active=True,
        created_by="system-seed",
    )
    db.add(guide)
    await db.flush()
    return guide


async def resolve_article_style(
    db: AsyncSession,
    *,
    sport: str | None,
    article_type: str,
) -> tuple[StyleGuideVersion, dict[str, Any], str]:
    """Resolve the active Release 1 guide and return its frozen snapshot."""
    await ensure_seed_style_guide(db)
    guides = list(
        await db.scalars(
            select(StyleGuideVersion)
            .where(StyleGuideVersion.active.is_(True))
            .order_by(StyleGuideVersion.id)
        )
    )
    applicable = [
        guide
        for guide in guides
        if guide.scope_type == "shared_athletics"
        or (guide.scope_type == "sport" and guide.scope_value == sport)
        or (guide.scope_type == "article_type" and guide.scope_value == article_type)
    ]
    if not applicable:
        raise RuntimeError("No active Style Guide is available for this Article.")

    precedence = {"shared_athletics": 0, "sport": 1, "article_type": 2}
    applicable.sort(key=lambda guide: (precedence[guide.scope_type], guide.id))
    primary = applicable[-1]
    snapshot = {
        "versions": [
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
        ],
        "instructions": [guide.instructions for guide in applicable],
        "rules": [rule for guide in applicable for rule in guide.rules],
    }
    return primary, snapshot, canonical_hash(snapshot)
