"""Detect, explain, and deliberately refresh stale Article evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import AchievementSuggestion
from app.models.article import (
    Article,
    ArticleAchievementSuggestion,
    ArticleEvidenceRevalidation,
    ArticleGenerationJob,
    ArticleReadinessDecision,
    ArticleVersion,
    EvidenceBundle,
)
from app.models.game import Game
from app.schemas.article import ArticleDraftOutput, ArticleEvidenceRevalidationRead
from app.services.article_brief import (
    EVIDENCE_SCHEMA_VERSION,
    _canonical_hash,
    _game_evidence,
    _load_suggestion_evidence,
    _suggestion_evidence,
    _validate_evidence,
    achievement_fact_hash,
    read_article_brief,
)
from app.services.article_generation import build_writer_input, validate_article_draft
from app.services.article_style import canonical_hash


class ArticleRevalidationNotFoundError(ValueError):
    """Raised when an Article or its current evidence cannot be found."""


class ArticleRevalidationConflictError(ValueError):
    """Raised when an Article cannot be refreshed safely."""


def _fact_value(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "player_id",
        "player_name",
        "stat_definition_id",
        "notability_policy_id",
        "notability_policy_version",
        "stat_key",
        "stat_label",
        "achievement_type",
        "scope",
        "computed_value",
        "comparison_value",
        "rank",
        "phrasing",
        "context",
    )
    return {key: item.get(key) for key in keys}


def _source_value(item: dict[str, Any]) -> dict[str, Any] | None:
    source = item.get("source")
    if not isinstance(source, dict):
        return None
    return {
        key: source.get(key)
        for key in ("source_system", "source_type", "source_url", "content_hash")
    }


def _coverage_value(item: dict[str, Any]) -> dict[str, Any] | None:
    coverage = item.get("coverage_window")
    if not isinstance(coverage, dict):
        return None
    return {
        key: coverage.get(key)
        for key in (
            "grain",
            "first_season",
            "last_season",
            "completeness",
            "known_limitations",
            "claim_scope",
        )
    }


def _current_item(row, *, evidence_item_id: str) -> dict[str, Any]:
    """Serialize current evidence even when its new verdict is still pending."""
    suggestion = row.suggestion
    source = row.source
    coverage = row.coverage
    return {
        "evidence_item_id": evidence_item_id,
        "id": suggestion.id,
        "suggestion_key": suggestion.suggestion_key,
        "player_id": suggestion.player_id,
        "player_name": row.player.display_name,
        "stat_definition_id": suggestion.stat_definition_id,
        "notability_policy_id": suggestion.notability_policy_id,
        "notability_policy_version": row.policy.version,
        "stat_key": row.definition.stat_key,
        "stat_label": row.definition.display_label,
        "achievement_type": suggestion.achievement_type,
        "scope": suggestion.scope,
        "computed_value": str(suggestion.computed_value),
        "comparison_value": (
            str(suggestion.comparison_value)
            if suggestion.comparison_value is not None
            else None
        ),
        "rank": suggestion.rank,
        "phrasing": suggestion.phrasing,
        "context": suggestion.context,
        "source": (
            {
                "snapshot_id": source.id,
                "source_system": source.source_system,
                "source_type": source.source_type,
                "source_url": source.source_url,
                "content_hash": source.content_hash,
                "fetched_at": source.fetched_at.isoformat(),
            }
            if source is not None
            else None
        ),
        "coverage_window": (
            {
                "id": coverage.id,
                "grain": coverage.grain,
                "first_season": coverage.first_season,
                "last_season": coverage.last_season,
                "completeness": coverage.completeness,
                "known_limitations": (
                    coverage.known_limitations
                    or suggestion.coverage_context.get("known_limitations")
                ),
                "claim_scope": suggestion.coverage_context.get("claim_scope"),
            }
            if coverage is not None
            else None
        ),
        "verdict": {
            "state": suggestion.state,
            "reviewed_at": (
                suggestion.reviewed_at.isoformat()
                if suggestion.reviewed_at is not None
                else None
            ),
            "reviewed_by": suggestion.reviewed_by,
        },
        "fact_hash": suggestion.reviewed_fact_hash,
    }


async def _current_rows_by_key(
    db: AsyncSession,
    *,
    game_id: int,
    suggestion_keys: list[str],
) -> dict[str, Any]:
    suggestions = list(
        await db.scalars(
            select(AchievementSuggestion).where(
                AchievementSuggestion.game_id == game_id,
                AchievementSuggestion.suggestion_key.in_(suggestion_keys),
            )
        )
    )
    if not suggestions:
        return {}
    rows = await _load_suggestion_evidence(db, [row.id for row in suggestions])
    return {row.suggestion.suggestion_key: row for row in rows}


def _change(
    change_type: str,
    label: str,
    *,
    suggestion_key: str | None = None,
    previous_value: Any = None,
    current_value: Any = None,
) -> dict[str, Any]:
    return {
        "change_type": change_type,
        "suggestion_key": suggestion_key,
        "label": label,
        "previous_value": previous_value,
        "current_value": current_value,
    }


async def _article_changes(
    db: AsyncSession,
    *,
    article: Article,
    game: Game,
    bundle: EvidenceBundle,
) -> list[dict[str, Any]]:
    previous_items = bundle.content.get("suggestions", [])
    keys = [str(item["suggestion_key"]) for item in previous_items]
    current_rows = await _current_rows_by_key(db, game_id=game.id, suggestion_keys=keys)
    changes: list[dict[str, Any]] = []
    current_game = _game_evidence(game)
    if bundle.content.get("game") != current_game:
        changes.append(
            _change(
                "game_changed",
                "Game result or identity evidence changed.",
                previous_value=bundle.content.get("game"),
                current_value=current_game,
            )
        )

    for previous in previous_items:
        suggestion_key = str(previous["suggestion_key"])
        row = current_rows.get(suggestion_key)
        if row is None:
            changes.append(
                _change(
                    "suggestion_removed",
                    "The source no longer produces this Achievement Suggestion.",
                    suggestion_key=suggestion_key,
                    previous_value=_fact_value(previous),
                )
            )
            continue
        current = _current_item(
            row,
            evidence_item_id=str(previous["evidence_item_id"]),
        )
        if _fact_value(previous) != _fact_value(current):
            changes.append(
                _change(
                    "fact_changed",
                    "The verified achievement fact changed.",
                    suggestion_key=suggestion_key,
                    previous_value=_fact_value(previous),
                    current_value=_fact_value(current),
                )
            )
        if _coverage_value(previous) != _coverage_value(current):
            changes.append(
                _change(
                    "coverage_changed",
                    "The governing Coverage Window changed.",
                    suggestion_key=suggestion_key,
                    previous_value=_coverage_value(previous),
                    current_value=_coverage_value(current),
                )
            )
        if _source_value(previous) != _source_value(current):
            changes.append(
                _change(
                    "source_changed",
                    "The material source snapshot changed.",
                    suggestion_key=suggestion_key,
                    previous_value=_source_value(previous),
                    current_value=_source_value(current),
                )
            )
        suggestion = row.suggestion
        current_hash = achievement_fact_hash(
            suggestion,
            game=game,
            source=row.source,
            coverage=row.coverage,
        )
        if (
            suggestion.state != "approved"
            or suggestion.reviewed_fact_hash != current_hash
        ):
            changes.append(
                _change(
                    "approval_changed",
                    "The current evidence no longer has a valid SID approval.",
                    suggestion_key=suggestion_key,
                    previous_value=previous.get("verdict", {}).get("state"),
                    current_value=suggestion.state,
                )
            )
    return changes


async def detect_article_evidence_drift(
    db: AsyncSession,
    *,
    game: Game,
) -> int:
    """Mark affected non-archived Articles stale after warehouse evidence changes."""
    articles = list(
        await db.scalars(
            select(Article).where(
                Article.game_id == game.id,
                Article.status != "archived",
            )
        )
    )
    detected = 0
    now = datetime.now(UTC)
    for article in articles:
        bundle = await db.scalar(
            select(EvidenceBundle)
            .where(EvidenceBundle.article_id == article.id)
            .order_by(EvidenceBundle.version.desc())
            .limit(1)
        )
        if bundle is None:
            continue
        changes = await _article_changes(db, article=article, game=game, bundle=bundle)
        if not changes:
            continue
        change_hash = _canonical_hash(changes)
        existing = await db.scalar(
            select(ArticleEvidenceRevalidation).where(
                ArticleEvidenceRevalidation.article_id == article.id,
                ArticleEvidenceRevalidation.resolved_at.is_(None),
                ArticleEvidenceRevalidation.change_hash == change_hash,
            )
        )
        if existing is None:
            db.add(
                ArticleEvidenceRevalidation(
                    article_id=article.id,
                    previous_evidence_bundle_id=bundle.id,
                    change_hash=change_hash,
                    changes=changes,
                )
            )
            detected += 1
        if article.ready_version_id is not None:
            db.add(
                ArticleReadinessDecision(
                    article_id=article.id,
                    article_version_id=article.ready_version_id,
                    action="reopened",
                    actor="evidence-revalidation",
                    reason="Material source evidence changed.",
                )
            )
            article.ready_version_id = None
        active_jobs = list(
            await db.scalars(
                select(ArticleGenerationJob).where(
                    ArticleGenerationJob.article_id == article.id,
                    ArticleGenerationJob.state.in_(("queued", "running")),
                )
            )
        )
        for job in active_jobs:
            job.state = "failed"
            job.error_code = "evidence_revalidation_required"
            job.error_message = (
                "Material source evidence changed before generation completed."
            )
            job.completed_at = now
            job.lease_expires_at = None
        article.status = "needs_revalidation"
    await db.flush()
    return detected


def revalidation_read(
    revalidation: ArticleEvidenceRevalidation,
) -> ArticleEvidenceRevalidationRead:
    """Serialize one evidence drift audit record."""
    return ArticleEvidenceRevalidationRead.model_validate(
        revalidation, from_attributes=True
    )


async def refresh_article_evidence(
    db: AsyncSession,
    article_id: int,
    *,
    actor: str,
):
    """Append refreshed evidence and a review checkpoint after renewed approval."""
    article = await db.scalar(
        select(Article).where(Article.id == article_id).with_for_update()
    )
    if article is None:
        raise ArticleRevalidationNotFoundError("Article not found.")
    if article.status != "needs_revalidation":
        raise ArticleRevalidationConflictError(
            "This Article does not currently require evidence revalidation."
        )
    game = await db.get(Game, article.game_id)
    if game is None:
        raise ArticleRevalidationNotFoundError("Article game not found.")
    previous_bundle = await db.scalar(
        select(EvidenceBundle)
        .where(EvidenceBundle.article_id == article.id)
        .order_by(EvidenceBundle.version.desc())
        .limit(1)
    )
    if previous_bundle is None:
        raise ArticleRevalidationConflictError("Article has no Evidence Bundle.")
    previous_items = previous_bundle.content.get("suggestions", [])
    keys = [str(item["suggestion_key"]) for item in previous_items]
    rows_by_key = await _current_rows_by_key(db, game_id=game.id, suggestion_keys=keys)
    if set(rows_by_key) != set(keys):
        raise ArticleRevalidationConflictError(
            "Every source Achievement Suggestion must exist before refresh."
        )
    rows = [rows_by_key[key] for key in keys]
    try:
        _validate_evidence(rows, game)
    except ValueError as exc:
        raise ArticleRevalidationConflictError(
            f"Every refreshed Achievement Suggestion must be currently approved: {exc}"
        ) from exc

    evidence_ids = {
        str(item["suggestion_key"]): str(item["evidence_item_id"])
        for item in previous_items
    }
    refreshed_items = []
    for row in rows:
        item = _suggestion_evidence(row)
        item["evidence_item_id"] = evidence_ids[row.suggestion.suggestion_key]
        refreshed_items.append(item)
    content = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "game": _game_evidence(game),
        "suggestions": refreshed_items,
    }
    bundle = EvidenceBundle(
        article_id=article.id,
        version=previous_bundle.version + 1,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        content=content,
        content_hash=_canonical_hash(content),
        created_by=actor,
    )
    db.add(bundle)
    await db.flush()

    links = list(
        await db.scalars(
            select(ArticleAchievementSuggestion).where(
                ArticleAchievementSuggestion.article_id == article.id
            )
        )
    )
    by_key = {row.suggestion.suggestion_key: row.suggestion for row in rows}
    for link in links:
        suggestion = by_key[link.suggestion_key]
        link.achievement_suggestion_id = suggestion.id
        link.reviewed_fact_hash = str(suggestion.reviewed_fact_hash)

    latest = await db.scalar(
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article.id)
        .order_by(ArticleVersion.version.desc())
        .limit(1)
    )
    if latest is not None:
        draft = ArticleDraftOutput.model_validate(
            {
                "headline": latest.headline,
                "headline_evidence_ids": latest.headline_evidence_ids,
                "blocks": latest.blocks,
            }
        )
        writer_input = build_writer_input(
            article, bundle, latest.style_snapshot, base_version=latest
        )
        findings = validate_article_draft(draft, writer_input, latest.style_snapshot)
        output = draft.model_dump(mode="json")
        version = ArticleVersion(
            article_id=article.id,
            parent_version_id=latest.id,
            evidence_bundle_id=bundle.id,
            style_guide_version_id=latest.style_guide_version_id,
            generation_job_id=None,
            version=latest.version + 1,
            origin="human",
            headline=draft.headline,
            headline_evidence_ids=draft.headline_evidence_ids,
            body="\n\n".join(block.text for block in draft.blocks),
            blocks=[block.model_dump(mode="json") for block in draft.blocks],
            author=actor,
            provider=None,
            model=None,
            prompt_version=None,
            editor_instructions="Evidence refreshed after source revalidation.",
            evidence_hash=bundle.content_hash,
            style_snapshot=latest.style_snapshot,
            style_hash=latest.style_hash,
            output_hash=canonical_hash(output),
            validation_results=findings,
        )
        db.add(version)
        article.status = "in_edit"
    else:
        article.status = "brief"

    if article.ready_version_id is not None:
        db.add(
            ArticleReadinessDecision(
                article_id=article.id,
                article_version_id=article.ready_version_id,
                action="reopened",
                actor=actor,
                reason="Evidence was refreshed for human review.",
            )
        )
        article.ready_version_id = None

    now = datetime.now(UTC)
    pending = list(
        await db.scalars(
            select(ArticleEvidenceRevalidation).where(
                ArticleEvidenceRevalidation.article_id == article.id,
                ArticleEvidenceRevalidation.resolved_at.is_(None),
            )
        )
    )
    for revalidation in pending:
        revalidation.refreshed_evidence_bundle_id = bundle.id
        revalidation.resolved_at = now
        revalidation.resolved_by = actor
    await db.flush()
    return await read_article_brief(db, article.id)
