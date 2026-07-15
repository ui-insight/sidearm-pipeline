"""Tests for the bundled source registry."""

import pytest

from app.services.source_registry import get_source_registry, load_source_registry


def test_bundled_source_registry_loads_release_1_sports() -> None:
    registry = get_source_registry()

    assert registry.version == "1.1.0"
    assert registry.source_system == "sidearm"
    assert str(registry.base_url) == "https://govandals.com/"
    assert [sport.sport_slug for sport in registry.release_1_sports] == [
        "football",
        "mens-basketball",
        "womens-basketball",
        "womens-soccer",
        "womens-volleyball",
    ]


def test_source_registry_entries_have_required_source_shapes() -> None:
    registry = get_source_registry()

    for sport in registry.release_1_sports:
        assert sport.source_patterns.schedule_url.startswith("/sports/")
        assert "schedule_html" in sport.supported_source_types
        assert sport.parser_strategy == "sidearm_boxscore_html"
        assert sport.polling_policy.postgame_seconds > 0


def test_require_sport_returns_entry_or_clear_error() -> None:
    registry = get_source_registry()

    assert registry.require_sport("football").sport_name == "Football"

    with pytest.raises(KeyError, match="No source registry entry"):
        registry.require_sport("baseball")


def test_womens_basketball_registers_roster_sources() -> None:
    sport = get_source_registry().require_sport("womens-basketball")

    assert sport.source_patterns.roster_url == "/sports/womens-basketball/roster"
    assert "roster_html" in sport.supported_source_types
    assert "player_bio_html" in sport.supported_source_types


def test_source_registry_can_load_from_explicit_path(tmp_path) -> None:
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(
        """
        {
          "version": "test",
          "source_system": "sidearm",
          "base_url": "https://example.edu",
          "sports": []
        }
        """,
        encoding="utf-8",
    )

    registry = load_source_registry(registry_file)

    assert registry.version == "test"
    assert registry.sports == []
