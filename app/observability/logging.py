"""Minimal structured logging with no request/body capture."""

import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(value: str) -> Token[str | None]:
    """Associate a server-generated correlation ID with logs for one request."""
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    """Clear request context so background work never inherits a prior request ID."""
    _request_id.reset(token)


class JsonFormatter(logging.Formatter):
    """Render log records as JSON suitable for container log collection."""

    def __init__(self, *, secrets: tuple[str, ...] = ()) -> None:
        super().__init__()
        self._secrets = tuple(value for value in secrets if len(value) >= 4)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_log_value(record.getMessage(), self._secrets),
        }
        request_id = _request_id.get()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        oauth_error_category = getattr(record, "oauth_error_category", None)
        if oauth_error_category:
            payload["oauth_error_category"] = oauth_error_category
        search_error_category = getattr(record, "search_error_category", None)
        if search_error_category:
            payload["search_error_category"] = search_error_category
        diagnostic_category = getattr(record, "diagnostic_category", None)
        if diagnostic_category:
            payload["diagnostic_category"] = diagnostic_category
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str, *, secrets: tuple[str, ...] = ()) -> None:
    """Configure root logging once, emitting structured records to standard output."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(secrets=secrets))
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


def _redact_log_value(value: str, secrets: tuple[str, ...]) -> str:
    """Remove configured secrets and common URL/header credential shapes from log messages."""
    redacted = value
    for secret in secrets:
        redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(
        r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|"
        r"authorization|api[_-]?key|password|code|state)=)[^\s&]+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [REDACTED]", redacted)
    redacted = re.sub(
        r"(?i)\b(postgresql(?:\+asyncpg)?://[^:\s/@]+:)[^@\s/]+(@)",
        r"\1[REDACTED]\2",
        redacted,
    )
    return redacted
