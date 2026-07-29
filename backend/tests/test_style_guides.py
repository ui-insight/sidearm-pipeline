"""Behavior and authorization tests for versioned athletics Style Guides."""

from copy import deepcopy

from sqlalchemy import select

from app.config import settings
from app.models.article import StyleGuideVersion
from app.schemas.article import ArticleDraftOutput
from app.services import article_generation
from app.services.article_generation import validate_article_draft
from app.services.article_style import ensure_seed_style_guide
from tests.test_article_generation import _article_brief, _safe_draft


def _rule(
    key: str,
    *,
    severity: str = "error",
    enforcement: str = "headline_max_chars",
    value: object = 80,
    override: bool = False,
) -> dict:
    return {
        "key": key,
        "category": "terminology" if "terms" in enforcement else "length",
        "severity": severity,
        "enforcement": enforcement,
        "value": value,
        "override": override,
        "description": None,
    }


async def _seed(db_session) -> StyleGuideVersion:
    guide = await ensure_seed_style_guide(db_session)
    await db_session.commit()
    return guide


async def _create_and_activate(
    client,
    *,
    guide_key: str,
    scope_type: str,
    scope_value: str | None,
    rule: dict,
) -> dict:
    created = await client.post(
        "/api/v1/style-guides",
        json={
            "guide_key": guide_key,
            "name": f"{guide_key} guide",
            "scope_type": scope_type,
            "scope_value": scope_value,
            "instructions": f"Apply the {guide_key} policy.",
            "rules": [rule],
        },
    )
    assert created.status_code == 201, created.text
    activated = await client.post(
        f"/api/v1/style-guides/{created.json()['id']}/activate",
        json={},
    )
    assert activated.status_code == 200, activated.text
    return activated.json()


async def test_style_guide_api_resolves_all_scopes_in_precedence_order(
    client,
    db_session,
) -> None:
    await _seed(db_session)
    sport = await _create_and_activate(
        client,
        guide_key="wbb-style",
        scope_type="sport",
        scope_value="womens-basketball",
        rule=_rule("headline-length", value=80, override=True),
    )
    article_type = await _create_and_activate(
        client,
        guide_key="recap-style",
        scope_type="article_type",
        scope_value="game_recap",
        rule=_rule("headline-length", value=70, override=True),
    )
    channel = await _create_and_activate(
        client,
        guide_key="social-style",
        scope_type="channel",
        scope_value="social",
        rule=_rule("headline-length", value=60, override=True),
    )

    preview = await client.post(
        "/api/v1/style-guides/preview",
        json={
            "sport": "womens-basketball",
            "article_type": "game_recap",
            "channel": "social",
            "candidate_version_id": None,
        },
    )

    assert preview.status_code == 200
    resolved = preview.json()
    assert resolved["valid_for_activation"] is True
    assert [version["scope_type"] for version in resolved["versions"]] == [
        "shared_athletics",
        "sport",
        "article_type",
        "channel",
    ]
    headline_rule = next(
        rule for rule in resolved["rules"] if rule["key"] == "headline-length"
    )
    assert headline_rule["value"] == 60
    assert headline_rule["source_version_id"] == channel["id"]
    assert {sport["id"], article_type["id"], channel["id"]}.issubset(
        {version["id"] for version in resolved["versions"]}
    )

    retired = await client.post(
        f"/api/v1/style-guides/{channel['id']}/retire",
        json={},
    )
    assert retired.status_code == 200
    assert retired.json()["lifecycle_state"] == "retired"
    assert retired.json()["retired_by"] == settings.PROTOTYPE_AUTH_USERNAME


async def test_successor_activation_retires_prior_version_and_content_is_immutable(
    client,
    db_session,
) -> None:
    await _seed(db_session)
    first = await _create_and_activate(
        client,
        guide_key="website-style",
        scope_type="channel",
        scope_value="website",
        rule=_rule(
            "website-required-name",
            enforcement="required_terms",
            value=["Idaho"],
        ),
    )
    successor = await client.post(
        f"/api/v1/style-guides/{first['id']}/successors",
        json={
            "name": "Website style guide",
            "instructions": "Use concise website copy.",
            "rules": [
                _rule(
                    "website-required-name",
                    severity="warning",
                    enforcement="required_terms",
                    value=["Vandals"],
                )
            ],
        },
    )
    assert successor.status_code == 201
    draft = successor.json()
    assert draft["version"] == 2
    assert draft["predecessor_version_id"] == first["id"]
    assert draft["lifecycle_state"] == "draft"

    activated = await client.post(
        f"/api/v1/style-guides/{draft['id']}/activate",
        json={},
    )
    assert activated.status_code == 200
    history = (await client.get("/api/v1/style-guides")).json()
    previous = next(version for version in history if version["id"] == first["id"])
    current = next(version for version in history if version["id"] == draft["id"])
    assert previous["lifecycle_state"] == "retired"
    assert previous["rules"][0]["value"] == ["Idaho"]
    assert current["lifecycle_state"] == "active"
    assert current["effective_at"] is not None
    assert current["activated_by"] == settings.PROTOTYPE_AUTH_USERNAME


async def test_conflicting_and_invalid_rules_are_rejected_before_activation(
    client,
    db_session,
) -> None:
    await _seed(db_session)
    conflicting = await client.post(
        "/api/v1/style-guides",
        json={
            "guide_key": "conflicting-sport-style",
            "name": "Conflicting sport style",
            "scope_type": "sport",
            "scope_value": "womens-basketball",
            "instructions": "Use the reviewed sport policy.",
            "rules": [_rule("headline-length", value=70, override=False)],
        },
    )
    assert conflicting.status_code == 201
    activation = await client.post(
        f"/api/v1/style-guides/{conflicting.json()['id']}/activate",
        json={},
    )
    assert activation.status_code == 409
    assert "explicitly override" in activation.json()["detail"]
    persisted = await db_session.get(StyleGuideVersion, conflicting.json()["id"])
    assert persisted is not None
    assert persisted.lifecycle_state == "draft"

    invalid = await client.post(
        "/api/v1/style-guides",
        json={
            "guide_key": "invalid-guidance",
            "name": "Invalid guidance",
            "scope_type": "channel",
            "scope_value": "social",
            "instructions": "Use the channel policy.",
            "rules": [
                _rule(
                    "social-tone",
                    severity="error",
                    enforcement="prompt_guidance",
                    value="Keep the tone calm.",
                )
            ],
        },
    )
    assert invalid.status_code == 422

    contradictory = await client.post(
        "/api/v1/style-guides",
        json={
            "guide_key": "contradictory-terms",
            "name": "Contradictory terminology",
            "scope_type": "sport",
            "scope_value": "volleyball",
            "instructions": "Use reviewed volleyball terminology.",
            "rules": [
                _rule(
                    "required-vandals",
                    enforcement="required_terms",
                    value=["Vandals"],
                ),
                _rule(
                    "forbidden-vandals",
                    enforcement="forbidden_terms",
                    value=["Vandals"],
                ),
            ],
        },
    )
    assert contradictory.status_code == 201
    contradiction_activation = await client.post(
        f"/api/v1/style-guides/{contradictory.json()['id']}/activate",
        json={},
    )
    assert contradiction_activation.status_code == 409
    assert "both required and forbidden" in contradiction_activation.json()["detail"]


async def test_style_guide_management_requires_style_steward_role(
    client,
    db_session,
    monkeypatch,
) -> None:
    await _seed(db_session)
    monkeypatch.setattr(settings, "PROTOTYPE_AUTH_ROLES", "sid_editor,publisher")

    response = await client.get("/api/v1/style-guides")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "The style_steward role is required for Style Guide management."
    }


def test_error_warning_and_guidance_severities_have_distinct_findings() -> None:
    draft = ArticleDraftOutput.model_validate(
        {
            "headline": "Idaho wins!",
            "headline_evidence_ids": ["game:1"],
            "blocks": [
                {
                    "kind": "lead",
                    "text": "Idaho won the game.",
                    "evidence_ids": ["game:1"],
                }
            ],
        }
    )
    writer_input = {
        "evidence_bundle": {
            "content": {
                "game": {
                    "evidence_item_id": "game:1",
                    "id": 1,
                    "home_team": "Idaho",
                    "away_team": "Montana",
                    "home_score": None,
                    "away_score": None,
                },
                "suggestions": [],
            },
        }
    }
    style_snapshot = {
        "rules": [
            _rule(
                "headline-limit",
                severity="error",
                enforcement="headline_max_chars",
                value=5,
            ),
            _rule(
                "punctuation",
                severity="warning",
                enforcement="deterministic_lint",
                value="no_exclamation",
            ),
            _rule(
                "voice",
                severity="guidance",
                enforcement="prompt_guidance",
                value="Prefer direct, measured language.",
            ),
        ]
    }

    findings = validate_article_draft(draft, writer_input, style_snapshot)
    style_findings = {
        finding["code"]: finding["severity"]
        for finding in findings
        if finding["code"].startswith("style:")
    }
    assert style_findings == {
        "style:headline-limit": "error",
        "style:punctuation": "warning",
        "style:voice": "guidance",
    }


async def test_article_version_keeps_original_resolved_style_snapshot(
    client,
    db_session,
    monkeypatch,
) -> None:
    await _seed(db_session)
    brief = await _article_brief(client, db_session)

    async def safe_writer(_writer_input: dict) -> ArticleDraftOutput:
        return _safe_draft(brief)

    monkeypatch.setattr(article_generation, "generate_article_draft", safe_writer)
    queued = await client.post(
        f"/api/v1/articles/{brief['id']}/generation-jobs",
        json={"idempotency_key": "style-snapshot-generation"},
    )
    await article_generation.process_article_generation_job(
        db_session, queued.json()["id"]
    )
    completed = await client.get(
        f"/api/v1/articles/{brief['id']}/generation-jobs/{queued.json()['id']}"
    )
    original_version = completed.json()["article_version"]
    original_snapshot = deepcopy(original_version["style_snapshot"])
    original_hash = original_version["style_hash"]
    seed = await db_session.scalar(
        select(StyleGuideVersion).where(
            StyleGuideVersion.guide_key == "athletics-default"
        )
    )
    successor = await client.post(
        f"/api/v1/style-guides/{seed.id}/successors",
        json={
            "name": "Vandals Athletics guide",
            "instructions": "Use the successor shared athletics policy.",
            "rules": [
                _rule("headline-length", value=85),
                _rule(
                    "measured-language",
                    enforcement="forbidden_terms",
                    value=["statement win"],
                ),
            ],
        },
    )
    assert successor.status_code == 201
    activated = await client.post(
        f"/api/v1/style-guides/{successor.json()['id']}/activate",
        json={},
    )
    assert activated.status_code == 200

    unchanged = await client.get(f"/api/v1/articles/{brief['id']}")
    historical = unchanged.json()["latest_version"]
    assert historical["style_hash"] == original_hash
    assert historical["style_snapshot"] == original_snapshot
    assert historical["style_guide_version_id"] == seed.id
