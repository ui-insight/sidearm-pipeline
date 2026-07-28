"""Durable evidence-bound Article Draft generation and validation."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.article import (
    Article,
    ArticleGenerationJob,
    ArticleReadinessDecision,
    ArticleVersion,
    EvidenceBundle,
    StyleGuideVersion,
)
from app.models.game import Game
from app.schemas.article import (
    ArticleDraftOutput,
    ArticleGenerationJobCreate,
    ArticleGenerationJobRead,
    ArticleValidationFindingRead,
    ArticleVersionRead,
)
from app.services.article_style import canonical_hash, resolve_article_style
from app.services.article_writer import (
    ARTICLE_PROMPT_VERSION,
    ARTICLE_PROVIDER,
    article_model,
    generate_article_draft,
)

logger = logging.getLogger(__name__)

NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?")
PROPER_NAME_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:[\s,]+(?:[A-Z][a-z]+|[A-Z]{2,}))+\b"
)
COMPARATIVE_PATTERNS = {
    "career_high": re.compile(r"\bcareer[- ]high\b", re.IGNORECASE),
    "season_high": re.compile(r"\bseason[- ]high\b", re.IGNORECASE),
    "ranking": re.compile(
        r"\b(?:record|rank(?:ed|s|ing)?|top\s+\d+|lead(?:s|ing)?|leader)\b",
        re.IGNORECASE,
    ),
}
UNSUPPORTED_FACT_PATTERN = re.compile(
    r"[\"“”]|\b(?:said|says|injur(?:y|ed|ies)|attendance|weather|temperature)\b",
    re.IGNORECASE,
)


class ArticleGenerationNotFoundError(ValueError):
    """Raised when an Article, job, or required immutable input is missing."""


class ArticleGenerationConflictError(ValueError):
    """Raised when current Article state cannot accept a generation request."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _game_evidence_id(content: dict) -> str:
    return f"game:{content['game']['id']}"


def build_writer_input(
    article: Article,
    bundle: EvidenceBundle,
    style_snapshot: dict,
    *,
    base_version: ArticleVersion | None = None,
    editor_instructions: str | None = None,
) -> dict:
    evidence = dict(bundle.content)
    evidence["game"] = {
        "evidence_item_id": _game_evidence_id(bundle.content),
        **evidence["game"],
    }
    writer_input = {
        "article_brief": {
            "article_id": article.id,
            "article_type": article.article_type,
            "angle": article.angle,
            "audience": article.audience,
            "constraints": article.constraints,
        },
        "evidence_bundle": {
            "id": bundle.id,
            "version": bundle.version,
            "schema_version": bundle.schema_version,
            "content_hash": bundle.content_hash,
            "content": evidence,
        },
        "style_guide": style_snapshot,
    }
    if base_version is not None and editor_instructions is not None:
        writer_input["editor_revision"] = {
            "instructions": editor_instructions,
            "base_version": {
                "id": base_version.id,
                "version": base_version.version,
                "headline": base_version.headline,
                "headline_evidence_ids": base_version.headline_evidence_ids,
                "blocks": base_version.blocks,
            },
        }
    return writer_input


async def request_article_generation(
    db: AsyncSession,
    article_id: int,
    payload: ArticleGenerationJobCreate,
    *,
    requested_by: str,
) -> ArticleGenerationJobRead:
    """Persist an idempotent queued writer job for one Article Brief."""
    article = await db.scalar(
        select(Article).where(Article.id == article_id).with_for_update()
    )
    if article is None:
        raise ArticleGenerationNotFoundError("Article not found.")

    existing = await db.scalar(
        select(ArticleGenerationJob).where(
            ArticleGenerationJob.article_id == article_id,
            ArticleGenerationJob.requested_by == requested_by,
            ArticleGenerationJob.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return await article_generation_job_read(db, existing)

    if article.status == "needs_revalidation":
        raise ArticleGenerationConflictError(
            "This Article requires evidence revalidation before generation."
        )
    active_job = await db.scalar(
        select(ArticleGenerationJob).where(
            ArticleGenerationJob.article_id == article_id,
            ArticleGenerationJob.state.in_(("queued", "running")),
        )
    )
    if active_job is not None:
        raise ArticleGenerationConflictError(
            "This Article already has an active generation job."
        )
    if article.status == "archived":
        raise ArticleGenerationConflictError("Archived Articles cannot be revised.")

    latest_version = await db.scalar(
        select(ArticleVersion)
        .where(ArticleVersion.article_id == article_id)
        .order_by(ArticleVersion.version.desc())
        .limit(1)
    )
    if latest_version is None:
        if article.status != "brief":
            raise ArticleGenerationConflictError(
                "The first Article Draft can be generated only from a brief."
            )
        if (
            payload.base_version_id is not None
            or payload.editor_instructions is not None
        ):
            raise ArticleGenerationConflictError(
                "A first draft does not accept revision instructions."
            )
    else:
        if article.status not in {"in_edit", "ready"}:
            raise ArticleGenerationConflictError(
                "This Article cannot accept an AI revision in its current state."
            )
        if payload.base_version_id != latest_version.id:
            raise ArticleGenerationConflictError(
                "The base Article Version is stale. Reload before requesting "
                "a revision."
            )
        if payload.editor_instructions is None:
            raise ArticleGenerationConflictError(
                "Editor instructions are required for an AI revision."
            )

    bundle = await db.scalar(
        select(EvidenceBundle)
        .where(EvidenceBundle.article_id == article_id)
        .order_by(EvidenceBundle.version.desc())
        .limit(1)
    )
    if bundle is None:
        raise ArticleGenerationConflictError("Article has no Evidence Bundle.")
    if latest_version is None:
        game = await db.get(Game, article.game_id)
        if game is None:
            raise ArticleGenerationNotFoundError("Article game not found.")
        try:
            guide, style_snapshot, style_hash = await resolve_article_style(
                db,
                sport=game.sport,
                article_type=article.article_type,
            )
        except RuntimeError as exc:
            raise ArticleGenerationConflictError(str(exc)) from exc
    else:
        guide = await db.get(StyleGuideVersion, latest_version.style_guide_version_id)
        if guide is None:
            raise ArticleGenerationConflictError("Article Style Guide not found.")
        bundle = await db.get(EvidenceBundle, latest_version.evidence_bundle_id)
        if bundle is None:
            raise ArticleGenerationConflictError("Article Evidence Bundle not found.")
        style_snapshot = latest_version.style_snapshot
        style_hash = latest_version.style_hash
    writer_input = build_writer_input(
        article,
        bundle,
        style_snapshot,
        base_version=latest_version,
        editor_instructions=payload.editor_instructions,
    )
    job = ArticleGenerationJob(
        article_id=article.id,
        evidence_bundle_id=bundle.id,
        style_guide_version_id=guide.id,
        base_version_id=latest_version.id if latest_version else None,
        state="queued",
        requested_by=requested_by,
        idempotency_key=payload.idempotency_key,
        attempt_count=0,
        provider=ARTICLE_PROVIDER,
        model=article_model(),
        prompt_version=ARTICLE_PROMPT_VERSION,
        editor_instructions=payload.editor_instructions,
        input_hash=canonical_hash(writer_input),
        writer_input=writer_input,
        style_snapshot=style_snapshot,
        style_hash=style_hash,
        validation_results=[],
    )
    article.status = "generating"
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return await article_generation_job_read(db, job)


def _number_variants(value: object) -> set[str]:
    if value is None:
        return set()
    text = str(value)
    values = {match.replace(",", "") for match in NUMBER_PATTERN.findall(text)}
    try:
        decimal = Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return values
    normalized = format(decimal.normalize(), "f")
    values.add(normalized)
    if decimal == decimal.to_integral_value():
        values.add(str(int(decimal)))
    return values


def _evidence_index(writer_input: dict) -> dict[str, dict]:
    content = writer_input["evidence_bundle"]["content"]
    game = content["game"]
    index = {game["evidence_item_id"]: {"kind": "game", **game}}
    index.update(
        {
            suggestion["evidence_item_id"]: {
                "kind": "suggestion",
                **suggestion,
            }
            for suggestion in content["suggestions"]
        }
    )
    return index


def _allowed_numbers(item: dict) -> set[str]:
    if item["kind"] == "game":
        fields = (
            item.get("season"),
            item.get("game_date"),
            item.get("home_score"),
            item.get("away_score"),
        )
    else:
        coverage = item["coverage_window"]
        fields = (
            item.get("computed_value"),
            item.get("comparison_value"),
            item.get("rank"),
            item.get("phrasing"),
            coverage.get("first_season"),
            coverage.get("last_season"),
            coverage.get("claim_scope"),
        )
    return {number for field in fields for number in _number_variants(field)}


def _allowed_entities(index: dict[str, dict]) -> set[str]:
    game = next(item for item in index.values() if item["kind"] == "game")
    entities = {
        str(value).strip()
        for value in (
            game.get("home_team"),
            game.get("away_team"),
            game.get("title"),
            "Idaho Vandals",
            "The Vandals",
        )
        if value
    }
    entities.update(
        item["player_name"] for item in index.values() if item["kind"] == "suggestion"
    )
    return entities


def _finding(
    code: str,
    message: str,
    *,
    severity: str = "error",
    block_index: int | None = None,
    evidence_ids: list[str] | None = None,
) -> dict:
    return ArticleValidationFindingRead(
        code=code,
        severity=severity,
        message=message,
        block_index=block_index,
        evidence_ids=evidence_ids or [],
    ).model_dump(mode="json")


def _validate_section(
    text: str,
    evidence_ids: list[str],
    *,
    index: dict[str, dict],
    entities: set[str],
    block_index: int | None,
) -> list[dict]:
    findings: list[dict] = []
    unknown = [evidence_id for evidence_id in evidence_ids if evidence_id not in index]
    if unknown:
        findings.append(
            _finding(
                "unknown_evidence_id",
                f"Unknown evidence reference: {', '.join(unknown)}.",
                block_index=block_index,
                evidence_ids=unknown,
            )
        )
        return findings

    referenced = [index[evidence_id] for evidence_id in evidence_ids]
    allowed_numbers = {
        number for item in referenced for number in _allowed_numbers(item)
    }
    actual_numbers = {
        number.replace(",", "") for number in NUMBER_PATTERN.findall(text)
    }
    unsupported_numbers = sorted(actual_numbers - allowed_numbers)
    if unsupported_numbers:
        findings.append(
            _finding(
                "unsupported_numeral",
                "Unsupported numeral(s): " + ", ".join(unsupported_numbers) + ".",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )

    unknown_names = []
    for candidate in PROPER_NAME_PATTERN.findall(text):
        normalized = candidate.strip(" ,")
        if not any(
            normalized.casefold() in entity.casefold()
            or entity.casefold() in normalized.casefold()
            for entity in entities
        ):
            unknown_names.append(normalized)
    if unknown_names:
        findings.append(
            _finding(
                "unsupported_entity",
                "Unsupported named entity or phrase: "
                + ", ".join(sorted(set(unknown_names)))
                + ".",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )

    if UNSUPPORTED_FACT_PATTERN.search(text):
        findings.append(
            _finding(
                "unsupported_fact_class",
                "Copy includes a quote or unsupported injury, attendance, or "
                "weather claim.",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )

    referenced_suggestions = [
        item for item in referenced if item["kind"] == "suggestion"
    ]
    comparative = any(pattern.search(text) for pattern in COMPARATIVE_PATTERNS.values())
    if comparative and not referenced_suggestions:
        findings.append(
            _finding(
                "unsupported_comparative_claim",
                "Comparative or record language requires approved suggestion evidence.",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )
    if COMPARATIVE_PATTERNS["career_high"].search(text) and not any(
        item["achievement_type"] == "career_high" for item in referenced_suggestions
    ):
        findings.append(
            _finding(
                "unsupported_career_high",
                "Career-high language is not supported by the referenced evidence.",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )
    if COMPARATIVE_PATTERNS["season_high"].search(text) and not any(
        item["achievement_type"] == "season_high" for item in referenced_suggestions
    ):
        findings.append(
            _finding(
                "unsupported_season_high",
                "Season-high language is not supported by the referenced evidence.",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )
    if COMPARATIVE_PATTERNS["ranking"].search(text) and not any(
        item["achievement_type"] == "all_time_top_n" and item.get("rank") is not None
        for item in referenced_suggestions
    ):
        findings.append(
            _finding(
                "unsupported_ranking_claim",
                "Ranking, record, or leader language is not supported by the "
                "referenced evidence.",
                block_index=block_index,
                evidence_ids=evidence_ids,
            )
        )
    if comparative:
        for item in referenced_suggestions:
            qualifier = item["coverage_window"]["claim_scope"].strip()
            if qualifier and qualifier.casefold() not in text.casefold():
                findings.append(
                    _finding(
                        "missing_coverage_qualifier",
                        f"Comparative claim must preserve qualifier: {qualifier}.",
                        block_index=block_index,
                        evidence_ids=[item["evidence_item_id"]],
                    )
                )
    return findings


def validate_article_draft(
    draft: ArticleDraftOutput,
    writer_input: dict,
    style_snapshot: dict,
) -> list[dict]:
    """Return deterministic fact and Style Guide findings for writer output."""
    index = _evidence_index(writer_input)
    entities = _allowed_entities(index)
    findings = _validate_section(
        draft.headline,
        draft.headline_evidence_ids,
        index=index,
        entities=entities,
        block_index=None,
    )
    for block_index, block in enumerate(draft.blocks):
        findings.extend(
            _validate_section(
                block.text,
                block.evidence_ids,
                index=index,
                entities=entities,
                block_index=block_index,
            )
        )

    full_text = "\n".join([draft.headline, *(block.text for block in draft.blocks)])
    for rule in style_snapshot["rules"]:
        enforcement = rule["enforcement"]
        severity = rule["severity"]
        if enforcement == "headline_max_chars" and len(draft.headline) > int(
            rule["value"]
        ):
            findings.append(
                _finding(
                    f"style:{rule['key']}",
                    f"Headline exceeds {rule['value']} characters.",
                    severity=severity,
                )
            )
        elif enforcement == "forbidden_terms":
            matched = [
                term
                for term in rule["value"]
                if str(term).casefold() in full_text.casefold()
            ]
            if matched:
                findings.append(
                    _finding(
                        f"style:{rule['key']}",
                        "Forbidden Style Guide term(s): "
                        + ", ".join(str(term) for term in matched)
                        + ".",
                        severity=severity,
                    )
                )
    return findings


def article_version_read(version: ArticleVersion) -> ArticleVersionRead:
    """Serialize one immutable Article Version."""
    return ArticleVersionRead.model_validate(
        {
            "id": version.id,
            "article_id": version.article_id,
            "version": version.version,
            "origin": version.origin,
            "parent_version_id": version.parent_version_id,
            "headline": version.headline,
            "headline_evidence_ids": version.headline_evidence_ids,
            "body": version.body,
            "blocks": version.blocks,
            "evidence_bundle_id": version.evidence_bundle_id,
            "evidence_hash": version.evidence_hash,
            "style_guide_version_id": version.style_guide_version_id,
            "style_snapshot": version.style_snapshot,
            "style_hash": version.style_hash,
            "prompt_version": version.prompt_version,
            "editor_instructions": version.editor_instructions,
            "provider": version.provider,
            "model": version.model,
            "output_hash": version.output_hash,
            "validation_results": version.validation_results,
            "author": version.author,
            "created_at": version.created_at,
            "warning_overrides": [],
        }
    )


async def article_generation_job_read(
    db: AsyncSession,
    job: ArticleGenerationJob,
) -> ArticleGenerationJobRead:
    """Serialize a durable generation job and any resulting version."""
    version = await db.scalar(
        select(ArticleVersion).where(ArticleVersion.generation_job_id == job.id)
    )
    return ArticleGenerationJobRead.model_validate(
        {
            "id": job.id,
            "article_id": job.article_id,
            "state": job.state,
            "requested_by": job.requested_by,
            "attempt_count": job.attempt_count,
            "evidence_bundle_id": job.evidence_bundle_id,
            "style_guide_version_id": job.style_guide_version_id,
            "base_version_id": job.base_version_id,
            "style_snapshot": job.style_snapshot,
            "style_hash": job.style_hash,
            "provider": job.provider,
            "model": job.model,
            "prompt_version": job.prompt_version,
            "editor_instructions": job.editor_instructions,
            "input_hash": job.input_hash,
            "output_hash": job.output_hash,
            "validation_results": job.validation_results,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "article_version": article_version_read(version) if version else None,
        }
    )


async def read_article_generation_job(
    db: AsyncSession,
    article_id: int,
    job_id: int,
) -> ArticleGenerationJobRead:
    """Read one job, constrained to its owning Article."""
    job = await db.scalar(
        select(ArticleGenerationJob).where(
            ArticleGenerationJob.id == job_id,
            ArticleGenerationJob.article_id == article_id,
        )
    )
    if job is None:
        raise ArticleGenerationNotFoundError("Article generation job not found.")
    return await article_generation_job_read(db, job)


def _lease_is_expired(job: ArticleGenerationJob, now: datetime) -> bool:
    if job.lease_expires_at is None:
        return True
    lease = job.lease_expires_at
    if lease.tzinfo is None:
        lease = lease.replace(tzinfo=UTC)
    return lease <= now


async def _restore_article_status(db: AsyncSession, article: Article) -> None:
    version_count = await db.scalar(
        select(func.count(ArticleVersion.id)).where(
            ArticleVersion.article_id == article.id
        )
    )
    if article.ready_version_id is not None:
        article.status = "ready"
    else:
        article.status = "in_edit" if version_count else "brief"


async def process_article_generation_job(
    db: AsyncSession,
    job_id: int,
) -> bool:
    """Claim and execute one queued or abandoned durable generation job."""
    now = _utcnow()
    job = await db.scalar(
        select(ArticleGenerationJob)
        .where(ArticleGenerationJob.id == job_id)
        .with_for_update()
    )
    if job is None or job.state in {"succeeded", "failed"}:
        return False
    if job.state == "running" and not _lease_is_expired(job, now):
        return False

    job.state = "running"
    job.attempt_count += 1
    claimed_attempt = job.attempt_count
    job.started_at = now
    job.completed_at = None
    job.lease_expires_at = now + timedelta(
        seconds=settings.ARTICLE_GENERATION_LEASE_SECONDS
    )
    job.error_code = None
    job.error_message = None
    job.validation_results = []
    article = await db.get(Article, job.article_id)
    if article is None:
        job.state = "failed"
        job.error_code = "article_missing"
        job.error_message = "Article not found."
        job.completed_at = now
        job.lease_expires_at = None
        await db.commit()
        return True
    article.status = "generating"
    await db.commit()

    draft: ArticleDraftOutput | None = None
    output_hash: str | None = None
    findings: list[dict] = []
    error_code: str | None = None
    error_message: str | None = None
    try:
        draft = await generate_article_draft(job.writer_input)
        output_hash = canonical_hash(draft.model_dump(mode="json"))
        findings = validate_article_draft(
            draft,
            job.writer_input,
            job.style_snapshot,
        )
        if any(finding["severity"] == "error" for finding in findings):
            error_code = "validation_failed"
            error_message = (
                "The generated draft failed deterministic fact or style validation."
            )
    except RuntimeError as exc:
        error_code = "provider_unavailable"
        error_message = str(exc)
    except Exception:
        logger.exception("Article generation failed job_id=%s", job_id)
        error_code = "generation_failed"
        error_message = (
            "Article generation failed unexpectedly. The Article Brief is unchanged "
            "and can be retried."
        )

    job = await db.scalar(
        select(ArticleGenerationJob)
        .where(ArticleGenerationJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None or job.state != "running" or job.attempt_count != claimed_attempt:
        await db.rollback()
        return False
    article = await db.get(Article, job.article_id)
    if article is None:
        await db.rollback()
        return False
    completed_at = _utcnow()
    job.output_hash = output_hash
    job.validation_results = findings
    job.completed_at = completed_at
    job.lease_expires_at = None

    if error_code or draft is None:
        job.state = "failed"
        job.error_code = error_code or "generation_failed"
        job.error_message = error_message or "Article generation failed."
        await _restore_article_status(db, article)
        await db.commit()
        return True

    existing_version = await db.scalar(
        select(ArticleVersion).where(ArticleVersion.generation_job_id == job.id)
    )
    if existing_version is None:
        latest_version = await db.scalar(
            select(ArticleVersion)
            .where(ArticleVersion.article_id == article.id)
            .order_by(ArticleVersion.version.desc())
            .limit(1)
        )
        body = "\n\n".join(block.text for block in draft.blocks)
        version = ArticleVersion(
            article_id=article.id,
            parent_version_id=job.base_version_id,
            evidence_bundle_id=job.evidence_bundle_id,
            style_guide_version_id=job.style_guide_version_id,
            generation_job_id=job.id,
            version=(latest_version.version + 1) if latest_version else 1,
            origin="ai",
            headline=draft.headline,
            headline_evidence_ids=draft.headline_evidence_ids,
            body=body,
            blocks=[block.model_dump(mode="json") for block in draft.blocks],
            author=None,
            provider=job.provider,
            model=job.model,
            prompt_version=job.prompt_version,
            editor_instructions=job.editor_instructions,
            evidence_hash=job.writer_input["evidence_bundle"]["content_hash"],
            style_snapshot=job.style_snapshot,
            style_hash=job.style_hash,
            output_hash=output_hash,
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
                    actor=job.requested_by,
                    reason="AI revision requested and completed.",
                )
            )
            article.ready_version_id = None
    job.state = "succeeded"
    article.status = "in_edit"
    await db.commit()
    return True


async def process_next_article_generation_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Process the oldest queued or lease-expired job, if one exists."""
    async with session_factory() as db:
        job_id = await db.scalar(
            select(ArticleGenerationJob.id)
            .where(
                or_(
                    ArticleGenerationJob.state == "queued",
                    and_(
                        ArticleGenerationJob.state == "running",
                        or_(
                            ArticleGenerationJob.lease_expires_at.is_(None),
                            ArticleGenerationJob.lease_expires_at <= func.now(),
                        ),
                    ),
                )
            )
            .order_by(ArticleGenerationJob.created_at, ArticleGenerationJob.id)
            .limit(1)
        )
        if job_id is None:
            return False
        return await process_article_generation_job(db, job_id)


async def article_generation_worker(
    session_factory: async_sessionmaker[AsyncSession],
    stop_event: asyncio.Event,
) -> None:
    """Continuously process durable jobs and reclaim expired leases after restart."""
    while not stop_event.is_set():
        try:
            processed = await process_next_article_generation_job(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Article generation worker iteration failed")
            processed = False
        if processed:
            continue
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.ARTICLE_GENERATION_POLL_SECONDS,
            )
        except TimeoutError:
            pass
