"""Application configuration via environment variables."""

import json
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vandals Stats Pipeline"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    PROTOTYPE_AUTH_ENABLED: bool = False
    PROTOTYPE_AUTH_USERNAME: str = "prototype"
    PROTOTYPE_AUTH_PASSWORD: str = ""
    DEV_MODE: bool = True
    UPLOAD_DIR: str = "./uploads"
    CORS_ORIGINS: str = '["http://localhost:5173", "http://localhost:9200"]'
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_TRUST_PROXY_HEADERS: bool = False
    RATE_LIMIT_EXEMPT_PATHS: str = '["/api/v1/health", "/api/v1/ready"]'
    SIDEARM_REQUEST_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0)
    SIDEARM_FETCH_MAX_ATTEMPTS: int = Field(default=3, ge=1)
    SIDEARM_FETCH_BACKOFF_SECONDS: float = Field(default=0.5, ge=0)
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str | None = (
        None  # e.g. https://mindrouter.uidaho.edu/anthropic
    )
    CONTENT_MODEL: str = "claude-opus-4-7"
    ARTICLE_MODEL: str | None = None
    ARTICLE_GENERATION_MAX_TOKENS: int = Field(default=4000, ge=256, le=16000)
    ARTICLE_GENERATION_POLL_SECONDS: float = Field(default=2.0, ge=0.1, le=60)
    ARTICLE_GENERATION_LEASE_SECONDS: int = Field(default=300, ge=30, le=3600)
    ACHIEVEMENT_MODEL: str = "claude-opus-4-7"
    ACHIEVEMENT_AI_MAX_CANDIDATES: int = Field(default=100, ge=1, le=100)
    NLQ_MODEL: str | None = None

    @staticmethod
    def parse_cors_origins(value: str) -> list[str]:
        """Parse CORS origins from JSON arrays or comma-separated strings."""
        raw_value = value.strip()
        if not raw_value:
            return []

        if raw_value.startswith("["):
            try:
                parsed_value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "CORS_ORIGINS must be a JSON array or comma-separated list"
                ) from exc
            if not isinstance(parsed_value, list):
                raise ValueError("CORS_ORIGINS JSON value must be an array")
            origins = [str(origin).strip().rstrip("/") for origin in parsed_value]
        else:
            origins = [
                origin.strip().rstrip("/")
                for origin in raw_value.split(",")
                if origin.strip()
            ]

        origins = [origin for origin in origins if origin]
        for origin in origins:
            if origin == "*":
                continue

            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    "CORS_ORIGINS values must be absolute HTTP(S) origins or '*'"
                )
            if parsed.path not in {"", "/"} or parsed.params or parsed.query:
                raise ValueError(
                    "CORS_ORIGINS values must not include paths, params, or query "
                    "strings"
                )
            if parsed.fragment:
                raise ValueError("CORS_ORIGINS values must not include fragments")

        return origins

    @property
    def cors_origins_list(self) -> list[str]:
        return self.parse_cors_origins(self.CORS_ORIGINS)

    @staticmethod
    def parse_rate_limit_exempt_paths(value: str) -> list[str]:
        """Parse exempt path prefixes from JSON arrays or comma-separated strings."""
        raw_value = value.strip()
        if not raw_value:
            return []

        if raw_value.startswith("["):
            try:
                parsed_value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "RATE_LIMIT_EXEMPT_PATHS must be a JSON array or comma-separated "
                    "list"
                ) from exc
            if not isinstance(parsed_value, list):
                raise ValueError("RATE_LIMIT_EXEMPT_PATHS JSON value must be an array")
            paths = [str(path).strip() for path in parsed_value]
        else:
            paths = [path.strip() for path in raw_value.split(",") if path.strip()]

        for path in paths:
            if not path.startswith("/"):
                raise ValueError(
                    "RATE_LIMIT_EXEMPT_PATHS values must begin with '/' path prefixes"
                )

        return paths

    @property
    def rate_limit_exempt_paths_list(self) -> list[str]:
        return self.parse_rate_limit_exempt_paths(self.RATE_LIMIT_EXEMPT_PATHS)

    def check_security(self) -> None:
        """Raise if default secrets are used in production."""
        if self.PROTOTYPE_AUTH_ENABLED:
            if not self.PROTOTYPE_AUTH_USERNAME.strip():
                raise RuntimeError(
                    "PROTOTYPE_AUTH_USERNAME is required when "
                    "prototype auth is enabled."
                )
            if not self.PROTOTYPE_AUTH_PASSWORD:
                raise RuntimeError(
                    "PROTOTYPE_AUTH_PASSWORD is required when "
                    "prototype auth is enabled."
                )

        if self.DEV_MODE:
            return

        if self.SECRET_KEY == "change-me-in-production":
            raise RuntimeError(
                "SECRET_KEY must be changed from default in production. "
                "Set DEV_MODE=true for development or change SECRET_KEY."
            )

        cors_origins = self.cors_origins_list
        if not cors_origins:
            raise RuntimeError("CORS_ORIGINS must be configured in production.")

        if "*" in cors_origins:
            raise RuntimeError("CORS_ORIGINS must not include '*' in production.")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
