"""Logging helpers for request correlation."""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from logging.config import dictConfig

REQUEST_ID_HEADER = "X-Request-ID"
DEFAULT_REQUEST_ID = "-"

_request_id_context: ContextVar[str] = ContextVar(
    "request_id", default=DEFAULT_REQUEST_ID
)
_original_record_factory = logging.getLogRecordFactory()
_record_factory_configured = False
_logging_configured = False


def configure_logging() -> None:
    """Configure a simple stdout logging baseline for local and container use."""
    global _logging_configured
    if _logging_configured:
        return

    _configure_log_record_factory()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s %(levelname)s [%(name)s] "
                        "[request_id=%(request_id)s] %(message)s"
                    ),
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": "INFO"},
        }
    )
    _logging_configured = True


def get_request_id() -> str:
    """Return the current request ID for the active context."""
    return _request_id_context.get()


def bind_request_id(request_id: str) -> Token[str]:
    """Bind a request ID to the current execution context."""
    return _request_id_context.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    """Restore the previous request ID context."""
    _request_id_context.reset(token)


def _configure_log_record_factory() -> None:
    """Attach request_id to every log record."""
    global _record_factory_configured
    if _record_factory_configured:
        return

    def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        record = _original_record_factory(*args, **kwargs)
        record.request_id = get_request_id()
        return record

    logging.setLogRecordFactory(record_factory)
    _record_factory_configured = True
