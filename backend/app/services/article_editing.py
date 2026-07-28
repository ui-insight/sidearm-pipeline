"""Human Article Version editing, validation, and readiness decisions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import (
    Article,
    ArticleGenerationJob,
    ArticleReadinessDecision,
    ArticleVersion,
    ArticleWarningOverride,
    EvidenceBundle,
)
from app.models.game import Game
from app.schemas.article import (
    ArticleDraftOutput,
    ArticleQueueItemRead,
    ArticleQueueRead,
    ArticleReadinessDecisionRead,
    ArticleReadyCreate,
    ArticleReadyRead,
    ArticleVersionCreate,
    ArticleVersionRead,
    ArticleWarningOverrideRead,
)
from app.services.article_generation import (
    article_version_read,
    build_writer_input,
    validate_article_draft,
)
from app.services.article_style import canonical_hash


class ArticleEditingNotFoundError(ValueError):
    """Raised when an Article or Article Version does not exist."""


class ArticleEditingConflictError(ValueError):
    """Raised when an editorial action violates the Article state contract."""


async def _latest_version(
    db: AsyncSession,
    article_id: int,
) -> ArticleVersion | None:
    return await db.scalar(
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version.desc())
        .limit(1)
    )


async def article_version_read_with_audit(
    db: AsyncSession,
    version: ArticleVersion,
) -> ArticleVersionRead:
    """Serialize a version with append-only warning acknowledgements."""
    overrides = list(
        await db.scalars(
            select(ArticleWarningOverride)
            .where(ArticleWarningOverride.article_version_id == version.id)
            .order_by(ArticleWarningOverride.created_at, ArticleWarningOverride.id)
        )
    )
    data = article_version_read(version).model_dump(mode="python")
    data["warning_overrides"] = [
        ArticleWarningOverrideRead.model_validate(override, from_attributes=True)
        for override in overrides
    ]
    return ArticleVersionRead.model_validate(data)


async def read_article_versions(
    db: AsyncSession,
    article_id: int,
) -> list[ArticleVersionRead]:
    """Return every immutable Article Version in chronological order."""
    if await db.get(Article, article_id) is None:
        raise ArticleEditingNotFoundError("Article not found.")
    versions = list(
        await db.scalars(
            select(ArticleVersion)
            .where(ArticleVersion.article_id == article_id)
            .order_by(ArticleVersion.version)
        )
    )
    return [await article_version_read_with_audit(db, version) for version in versions]


async def save_human_article_version(
    db: AsyncSession,
    article_id: int,
    payload: ArticleVersionCreate,
    *,
    author: str,
) -> ArticleVersionRead:
    """Append a validated human checkpoint using optimistic concurrency."""
    article = await db.scalar(
        select(Article).where(Article.id == article_id).with_for_update()
    )
    if article is None:
        raise ArticleEditingNotFoundError("Article not found.")
    if article.status in {"brief", "needs_revalidation", "archived"}:
        raise ArticleEditingConflictError(
            "This Article cannot accept edits in its current state."
        )
    active_job = await db.scalar(
        select(ArticleGenerationJob).where(
            ArticleGenerationJob.article_id == article_id,
            ArticleGenerationJob.state.in_(("queued", "running")),
        )
    )
    if active_job is not None:
        raise ArticleEditingConflictError(
            "Wait for the active AI revision before saving a human version."
        )

    latest = await _latest_version(db, article_id)
    if latest is None:
        raise ArticleEditingConflictError(
            "Generate the first Article Draft before editing."
        )
    if latest.id != payload.base_version_id:
        raise ArticleEditingConflictError(
            "The base Article Version is stale. Your edits were not overwritten; "
            "reload and reconcile them with the latest version."
        )

    bundle = await db.get(EvidenceBundle, latest.evidence_bundle_id)
    if bundle is None:
        raise ArticleEditingConflictError("Article Evidence Bundle not found.")
    draft = ArticleDraftOutput.model_validate(
        {
            "headline": payload.headline,
            "headline_evidence_ids": payload.headline_evidence_ids,
            "blocks": [block.model_dump(mode="json") for block in payload.blocks],
        }
    )
    writer_input = build_writer_input(article, bundle, latest.style_snapshot)
    findings = validate_article_draft(draft, writer_input, latest.style_snapshot)
    output = draft.model_dump(mode="json")
    version = ArticleVersion(
        article_id=article.id,
        parent_version_id=latest.id,
        evidence_bundle_id=latest.evidence_bundle_id,
        style_guide_version_id=latest.style_guide_version_id,
        generation_job_id=None,
        version=latest.version + 1,
        origin="human",
        headline=draft.headline,
        headline_evidence_ids=draft.headline_evidence_ids,
        body="\n\n".join(block.text for block in draft.blocks),
        blocks=[block.model_dump(mode="json") for block in draft.blocks],
        author=author,
        provider=None,
        model=None,
        prompt_version=None,
        editor_instructions=None,
        evidence_hash=bundle.content_hash,
        style_snapshot=latest.style_snapshot,
        style_hash=latest.style_hash,
        output_hash=canonical_hash(output),
        validation_results=findings,
    )
    db.add(version)
    await db.flush()

    if article.ready_version_id is not None:
        db.add(
            ArticleReadinessDecision(
                article_id=article.id,
                article_version_id=article.ready_version_id,
                action="reopened",
                actor=author,
                reason="A new human Article Version was saved.",
            )
        )
        article.ready_version_id = None
    article.status = "in_edit"
    await db.flush()
    await db.refresh(version)
    return await article_version_read_with_audit(db, version)


async def mark_article_version_ready(
    db: AsyncSession,
    article_id: int,
    version_id: int,
    payload: ArticleReadyCreate,
    *,
    actor: str,
) -> ArticleReadyRead:
    """Record the human gate selecting one validated immutable version."""
    article = await db.scalar(
        select(Article).where(Article.id == article_id).with_for_update()
    )
    if article is None:
        raise ArticleEditingNotFoundError("Article not found.")
    if article.status in {"brief", "generating", "needs_revalidation", "archived"}:
        raise ArticleEditingConflictError(
            "This Article cannot be marked ready in its current state."
        )
    version = await db.get(ArticleVersion, version_id)
    if version is None or version.article_id != article_id:
        raise ArticleEditingNotFoundError("Article Version not found.")
    latest = await _latest_version(db, article_id)
    if latest is None or latest.id != version.id:
        raise ArticleEditingConflictError(
            "Only the latest Article Version can be marked ready."
        )

    if article.status == "ready" and article.ready_version_id == version.id:
        decision = await db.scalar(
            select(ArticleReadinessDecision)
            .where(
                ArticleReadinessDecision.article_id == article_id,
                ArticleReadinessDecision.article_version_id == version.id,
                ArticleReadinessDecision.action == "ready",
            )
            .order_by(ArticleReadinessDecision.created_at.desc())
            .limit(1)
        )
        if decision is None:
            raise ArticleEditingConflictError(
                "Article readiness audit record not found."
            )
        return ArticleReadyRead(
            article_id=article.id,
            status="ready",
            ready_version=await article_version_read_with_audit(db, version),
            decision=ArticleReadinessDecisionRead.model_validate(
                decision, from_attributes=True
            ),
        )

    errors = [
        finding
        for finding in version.validation_results
        if finding.get("severity") == "error"
    ]
    if errors:
        raise ArticleEditingConflictError(
            "Resolve all blocking fact and Style Guide errors before readiness."
        )
    warning_codes = {
        str(finding.get("code"))
        for finding in version.validation_results
        if finding.get("severity") == "warning"
    }
    provided = {
        override.finding_code: override for override in payload.warning_overrides
    }
    if len(provided) != len(payload.warning_overrides):
        raise ArticleEditingConflictError("Each warning may be overridden only once.")
    unknown = set(provided) - warning_codes
    if unknown:
        raise ArticleEditingConflictError(
            "Warning override does not match this Article Version: "
            + ", ".join(sorted(unknown))
            + "."
        )
    missing = warning_codes - set(provided)
    if missing:
        raise ArticleEditingConflictError(
            "Record a reason for every warning before readiness: "
            + ", ".join(sorted(missing))
            + "."
        )

    for override in payload.warning_overrides:
        db.add(
            ArticleWarningOverride(
                article_version_id=version.id,
                finding_code=override.finding_code,
                reason=override.reason,
                overridden_by=actor,
            )
        )
    decision = ArticleReadinessDecision(
        article_id=article.id,
        article_version_id=version.id,
        action="ready",
        actor=actor,
        reason=(
            f"Acknowledged {len(warning_codes)} nonblocking warning(s)."
            if warning_codes
            else "No blocking findings."
        ),
    )
    db.add(decision)
    article.ready_version_id = version.id
    article.status = "ready"
    await db.flush()
    await db.refresh(decision)
    return ArticleReadyRead(
        article_id=article.id,
        status="ready",
        ready_version=await article_version_read_with_audit(db, version),
        decision=ArticleReadinessDecisionRead.model_validate(
            decision, from_attributes=True
        ),
    )


async def read_article_queue(db: AsyncSession) -> ArticleQueueRead:
    """Return the editorial queue with current, owner, and ready-version state."""
    rows = list(
        (
            await db.execute(
                select(Article, Game)
                .join(Game, Game.id == Article.game_id)
                .where(Article.status != "archived")
                .order_by(Article.created_at.desc(), Article.id.desc())
            )
        ).all()
    )
    items: list[ArticleQueueItemRead] = []
    for article, game in rows:
        latest = await _latest_version(db, article.id)
        ready = (
            await db.get(ArticleVersion, article.ready_version_id)
            if article.ready_version_id is not None
            else None
        )
        items.append(
            ArticleQueueItemRead(
                id=article.id,
                status=article.status,
                article_type=article.article_type,
                angle=article.angle,
                owner=article.created_by,
                created_at=article.created_at,
                game_date=str(game.game_date) if game.game_date else None,
                game_title=game.title,
                latest_version=(
                    await article_version_read_with_audit(db, latest)
                    if latest
                    else None
                ),
                ready_version=(
                    await article_version_read_with_audit(db, ready) if ready else None
                ),
            )
        )
    return ArticleQueueRead(items=items, total=len(items))
