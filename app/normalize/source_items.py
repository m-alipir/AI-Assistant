"""Deterministic URL, timestamp, and fingerprint normalization."""

import calendar
import hashlib
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import struct_time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(value: str | None) -> str | None:
    """Remove fragments and common tracking parameters while preserving article identity."""
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError:
        return None
    is_default_port = (parsed.scheme == "http" and port == 80) or (
        parsed.scheme == "https" and port == 443
    )
    if port and not is_default_port:
        host = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS and not key.lower().startswith("utm_")
        ),
        doseq=True,
    )
    return urlunsplit((parsed.scheme.lower(), host, path, query, ""))


def parse_source_datetime(value: object) -> datetime | None:
    """Parse common feed date representations to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(UTC)
    if isinstance(value, struct_time):
        return datetime.fromtimestamp(calendar.timegm(value), UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(candidate)
        except (TypeError, ValueError, IndexError):
            return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def content_fingerprint(title: str, snippet: str | None) -> str:
    """Hash normalized compact metadata when no source-native identity is available."""
    compact = re.sub(r"\s+", " ", f"{title}\n{snippet or ''}".strip().casefold())
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()
