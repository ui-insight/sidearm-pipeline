"""Verify application settings validation and production safeguards."""

import pytest

from app.config import Settings
from app.main import app, lifespan


def build_settings(**overrides: object) -> Settings:
    """Build settings without reading a developer's local .env file."""
    return Settings(_env_file=None, **overrides)


def test_cors_origins_accept_json_string() -> None:
    settings = build_settings(
        CORS_ORIGINS='["http://localhost:5173", "https://example.edu"]'
    )

    assert settings.cors_origins_list == [
        "http://localhost:5173",
        "https://example.edu",
    ]


def test_cors_origins_accept_comma_separated_string() -> None:
    settings = build_settings(
        CORS_ORIGINS="http://localhost:5173, https://example.edu/"
    )

    assert settings.cors_origins_list == [
        "http://localhost:5173",
        "https://example.edu",
    ]


def test_cors_origins_accept_comma_separated_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:5173, https://example.edu/",
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins_list == [
        "http://localhost:5173",
        "https://example.edu",
    ]


def test_cors_origins_reject_paths() -> None:
    settings = build_settings(CORS_ORIGINS='["https://example.edu/app"]')

    with pytest.raises(ValueError, match="must not include paths"):
        settings.cors_origins_list


def test_rate_limit_exempt_paths_accept_comma_separated_string() -> None:
    settings = build_settings(RATE_LIMIT_EXEMPT_PATHS="/api/v1/health, /api/v1/ready")

    assert settings.rate_limit_exempt_paths_list == [
        "/api/v1/health",
        "/api/v1/ready",
    ]


def test_rate_limit_exempt_paths_reject_non_paths() -> None:
    settings = build_settings(RATE_LIMIT_EXEMPT_PATHS="health")

    with pytest.raises(ValueError, match="must begin with '/'"):
        settings.rate_limit_exempt_paths_list


def test_sidearm_fetch_policy_settings_validate() -> None:
    settings = build_settings(
        SIDEARM_REQUEST_TIMEOUT_SECONDS=5,
        SIDEARM_FETCH_MAX_ATTEMPTS=2,
        SIDEARM_FETCH_BACKOFF_SECONDS=0,
    )

    assert settings.SIDEARM_REQUEST_TIMEOUT_SECONDS == 5
    assert settings.SIDEARM_FETCH_MAX_ATTEMPTS == 2
    assert settings.SIDEARM_FETCH_BACKOFF_SECONDS == 0

    with pytest.raises(ValueError):
        build_settings(SIDEARM_FETCH_MAX_ATTEMPTS=0)


def test_security_check_rejects_default_secret_in_production() -> None:
    settings = build_settings(DEV_MODE=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        settings.check_security()


def test_security_check_requires_prototype_credentials_when_enabled() -> None:
    settings = build_settings(
        PROTOTYPE_AUTH_ENABLED=True,
        PROTOTYPE_AUTH_USERNAME="prototype",
        PROTOTYPE_AUTH_PASSWORD="",
    )

    with pytest.raises(RuntimeError, match="PROTOTYPE_AUTH_PASSWORD"):
        settings.check_security()


def test_security_check_rejects_wildcard_cors_in_production() -> None:
    settings = build_settings(
        DEV_MODE=False,
        SECRET_KEY="not-the-template-default",
        CORS_ORIGINS="*",
    )

    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        settings.check_security()


async def test_lifespan_runs_security_check(monkeypatch) -> None:
    def raise_security_error(self: Settings) -> None:
        raise RuntimeError("blocked by security check")

    monkeypatch.setattr("app.config.Settings.check_security", raise_security_error)

    with pytest.raises(RuntimeError, match="blocked by security check"):
        async with lifespan(app):
            pass
