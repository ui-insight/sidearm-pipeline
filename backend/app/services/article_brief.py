"""Create and read immutable, evidence-bound Article Briefs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.achievement import (
    AchievementSuggestion,
    NotabilityPolicy,
)
from app.models.article import (
    Article,
    ArticleAchievementSuggestion,
    EvidenceBundle,
)
from app.models.coverage_window import CoverageWindow
from app.models.game import Game, SourceSnapshot
from app.models.player import Player
from app.models.stat_definition import StatDefinition
from app.schemas.article import ArticleBriefCreate, ArticleBriefRead

EVIDENCE_SCHEMA_VERSION = "article-evidence-bundle-v1"
SUPPORTED_ARTICLE_SPORT = "womens-basketball"


class ArticleBriefNotFoundError(ValueError):
    """Raised when an Article or selected Achievement Suggestion does not exist."""


class ArticleBriefConflictError(ValueError):
    """Raised when current records cannot safely create the requested brief."""


@dataclass(frozen=True)
class _SuggestionEvidence:
    suggestion: AchievementSuggestion
    player: Player
    definition: StatDefinition
    source: SourceSnapshot | None
    coverage: CoverageWindow | None
    policy: NotabilityPolicy


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def achievement_fact_hash(
    suggestion: AchievementSuggestion,
    *,
    game: Game | None,
    source: SourceSnapshot | None,
    coverage: CoverageWindow | None,
) -> str:
    """Fingerprint every deterministic fact and provenance field at verdict time."""
    return _canonical_hash(
        {
            "suggestion_key": suggestion.suggestion_key,
            "game_id": suggestion.game_id,
            "player_id": suggestion.player_id,
            "stat_definition_id": suggestion.stat_definition_id,
            "notability_policy_id": suggestion.notability_policy_id,
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
            "ai_model": suggestion.ai_model,
            "ai_prompt_version": suggestion.ai_prompt_version,
            "ai_output_hash": suggestion.ai_output_hash,
            "context": suggestion.context,
            "coverage_context": suggestion.coverage_context,
            "game": (
                {
                    "id": game.id,
                    "canonical_uid": game.canonical_uid,
                    "sport": game.sport,
                    "season": game.season,
                    "game_date": game.game_date,
                    "event_status": game.event_status,
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "title": game.title,
                    "source_url": game.source_url,
                }
                if game is not None
                else None
            ),
            "source": (
                {
                    "id": source.id,
                    "game_id": source.game_id,
                    "source_system": source.source_system,
                    "source_type": source.source_type,
                    "source_url": source.source_url,
                    "parser_version": source.parser_version,
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
                    "known_limitations": coverage.known_limitations,
                    "source_system": coverage.source_system,
                    "verified_at": (
                        coverage.verified_at.isoformat()
                        if coverage.verified_at is not None
                        else None
                    ),
                }
                if coverage is not None
                else None
            ),
        }
    )


async def _load_suggestion_evidence(
    db: AsyncSession,
    suggestion_ids: list[int],
) -> list[_SuggestionEvidence]:
    rows = (
        await db.execute(
            select(
                AchievementSuggestion,
                Player,
                StatDefinition,
                SourceSnapshot,
                CoverageWindow,
                NotabilityPolicy,
            )
            .join(Player, Player.id == AchievementSuggestion.player_id)
            .join(
                StatDefinition,
                StatDefinition.id == AchievementSuggestion.stat_definition_id,
            )
            .outerjoin(
                SourceSnapshot,
                SourceSnapshot.id == AchievementSuggestion.source_snapshot_id,
            )
            .outerjoin(
                CoverageWindow,
                CoverageWindow.id == AchievementSuggestion.coverage_window_id,
            )
            .join(
                NotabilityPolicy,
                NotabilityPolicy.id == AchievementSuggestion.notability_policy_id,
            )
            .where(AchievementSuggestion.id.in_(suggestion_ids))
        )
    ).all()
    by_id = {
        suggestion.id: _SuggestionEvidence(
            suggestion=suggestion,
            player=player,
            definition=definition,
            source=source,
            coverage=coverage,
            policy=policy,
        )
        for suggestion, player, definition, source, coverage, policy in rows
    }
    missing = [
        suggestion_id for suggestion_id in suggestion_ids if suggestion_id not in by_id
    ]
    if missing:
        joined = ", ".join(str(suggestion_id) for suggestion_id in missing)
        raise ArticleBriefNotFoundError(f"Achievement Suggestion not found: {joined}.")
    return [by_id[suggestion_id] for suggestion_id in sorted(suggestion_ids)]


def _validate_evidence(rows: list[_SuggestionEvidence], game: Game) -> None:
    if game.sport != SUPPORTED_ARTICLE_SPORT:
        raise ArticleBriefConflictError(
            "Release 1 Article Briefs support women's basketball only."
        )
    if game.event_status != "final":
        raise ArticleBriefConflictError("Article Briefs require a finalized game.")

    for row in rows:
        suggestion = row.suggestion
        if suggestion.state != "approved":
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} is not approved."
            )
        if (
            suggestion.reviewed_at is None
            or not suggestion.reviewed_by
            or not suggestion.reviewed_fact_hash
        ):
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} must be re-approved "
                "to capture complete verdict provenance."
            )
        if (
            row.source is None
            or row.source.game_id != suggestion.game_id
            or not row.source.content_hash
        ):
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} has invalid source provenance."
            )
        if row.coverage is None or row.coverage.completeness not in {
            "complete",
            "partial",
        }:
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} lacks an eligible "
                "Coverage Window."
            )
        claim_scope = suggestion.coverage_context.get("claim_scope")
        if not isinstance(claim_scope, str) or not claim_scope.strip():
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} lacks claim-scope wording."
            )
        if row.coverage.completeness == "partial" and not (
            row.coverage.known_limitations
            or suggestion.coverage_context.get("known_limitations")
        ):
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} has an undocumented "
                "partial Coverage Window."
            )
        current_hash = achievement_fact_hash(
            suggestion,
            game=game,
            source=row.source,
            coverage=row.coverage,
        )
        if current_hash != suggestion.reviewed_fact_hash:
            raise ArticleBriefConflictError(
                f"Achievement Suggestion {suggestion.id} changed after approval."
            )


def _game_evidence(game: Game) -> dict:
    return {
        "id": game.id,
        "canonical_uid": game.canonical_uid,
        "sport": game.sport,
        "season": game.season,
        "game_date": game.game_date,
        "title": game.title,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "home_score": game.home_score,
        "away_score": game.away_score,
        "source_url": game.source_url,
    }


def _suggestion_evidence(row: _SuggestionEvidence) -> dict:
    suggestion = row.suggestion
    source = row.source
    coverage = row.coverage
    if (
        source is None
        or coverage is None
        or suggestion.reviewed_at is None
        or suggestion.reviewed_by is None
        or suggestion.reviewed_fact_hash is None
    ):
        raise ArticleBriefConflictError(
            f"Achievement Suggestion {suggestion.id} has incomplete evidence."
        )
    return {
        "evidence_item_id": f"achievement-suggestion:{suggestion.id}",
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
        "source": {
            "snapshot_id": source.id,
            "source_system": source.source_system,
            "source_type": source.source_type,
            "source_url": source.source_url,
            "content_hash": source.content_hash,
            "fetched_at": source.fetched_at.isoformat(),
        },
        "coverage_window": {
            "id": coverage.id,
            "grain": coverage.grain,
            "first_season": coverage.first_season,
            "last_season": coverage.last_season,
            "completeness": coverage.completeness,
            "known_limitations": (
                coverage.known_limitations
                or suggestion.coverage_context.get("known_limitations")
            ),
            "claim_scope": suggestion.coverage_context["claim_scope"],
        },
        "verdict": {
            "state": "approved",
            "reviewed_at": suggestion.reviewed_at.isoformat(),
            "reviewed_by": suggestion.reviewed_by,
        },
        "fact_hash": suggestion.reviewed_fact_hash,
    }


def _request_hash(payload: ArticleBriefCreate) -> str:
    request_data = payload.model_dump(mode="json", exclude={"idempotency_key"})
    request_data["suggestion_ids"] = sorted(request_data["suggestion_ids"])
    return _canonical_hash(request_data)


async def create_article_brief(
    db: AsyncSession,
    payload: ArticleBriefCreate,
    *,
    created_by: str,
) -> ArticleBriefRead:
    """Create one Article and its first immutable Evidence Bundle."""
    request_hash = _request_hash(payload)
    existing = await db.scalar(
        select(Article).where(
            Article.created_by == created_by,
            Article.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise ArticleBriefConflictError(
                "The idempotency key was already used for a different Article Brief."
            )
        return await read_article_brief(db, existing.id)

    evidence_rows = await _load_suggestion_evidence(db, payload.suggestion_ids)
    game_ids = {row.suggestion.game_id for row in evidence_rows}
    if len(game_ids) != 1:
        raise ArticleBriefConflictError(
            "All Achievement Suggestions must belong to the same game."
        )
    game_id = next(iter(game_ids))
    game = await db.get(Game, game_id)
    if game is None:
        raise ArticleBriefNotFoundError("Game not found.")
    _validate_evidence(evidence_rows, game)

    content = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "game": _game_evidence(game),
        "suggestions": [_suggestion_evidence(row) for row in evidence_rows],
    }
    article = Article(
        game_id=game.id,
        status="brief",
        article_type=payload.article_type,
        angle=payload.angle,
        audience=payload.audience,
        constraints=payload.constraints,
        created_by=created_by,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
    )
    db.add(article)
    await db.flush()
    db.add_all(
        [
            ArticleAchievementSuggestion(
                article_id=article.id,
                achievement_suggestion_id=row.suggestion.id,
                suggestion_key=row.suggestion.suggestion_key,
                reviewed_fact_hash=row.suggestion.reviewed_fact_hash,
            )
            for row in evidence_rows
        ]
    )
    bundle = EvidenceBundle(
        article_id=article.id,
        version=1,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        content=content,
        content_hash=_canonical_hash(content),
        created_by=created_by,
    )
    db.add(bundle)
    await db.flush()
    await db.refresh(article)
    await db.refresh(bundle)
    return _article_brief_read(article, bundle)


def _article_brief_read(
    article: Article,
    bundle: EvidenceBundle,
) -> ArticleBriefRead:
    content = bundle.content
    return ArticleBriefRead.model_validate(
        {
            "id": article.id,
            "status": article.status,
            "article_type": article.article_type,
            "angle": article.angle,
            "audience": article.audience,
            "constraints": article.constraints,
            "created_by": article.created_by,
            "created_at": article.created_at,
            "game": content["game"],
            "evidence_bundle": {
                "id": bundle.id,
                "version": bundle.version,
                "schema_version": bundle.schema_version,
                "content_hash": bundle.content_hash,
                "created_by": bundle.created_by,
                "created_at": bundle.created_at,
                "suggestions": content["suggestions"],
            },
        }
    )


async def read_article_brief(
    db: AsyncSession,
    article_id: int,
) -> ArticleBriefRead:
    """Return one Article Brief and its latest frozen Evidence Bundle."""
    article = await db.get(Article, article_id)
    if article is None:
        raise ArticleBriefNotFoundError("Article not found.")
    bundle = await db.scalar(
        select(EvidenceBundle)
        .where(EvidenceBundle.article_id == article.id)
        .order_by(EvidenceBundle.version.desc())
        .limit(1)
    )
    if bundle is None:
        raise ArticleBriefConflictError("Article has no Evidence Bundle.")
    return _article_brief_read(article, bundle)
