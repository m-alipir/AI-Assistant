"""Bounded RSS/Atom collection and compact item normalization."""

import asyncio
import ipaddress
import logging
import socket
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx

from app.config.sources import RssSourceConfig
from app.ingestion.schemas import SourceItem, SourceKind, TimestampConfidence
from app.normalize.source_items import content_fingerprint, normalize_url, parse_source_datetime
from app.providers.contracts import ProviderError

logger = logging.getLogger(__name__)


class FeedFetcher(Protocol):
    """Fetch a feed payload with an explicit response-size bound."""

    async def fetch(self, url: str) -> bytes:
        """Return one RSS or Atom XML payload."""


class HttpFeedFetcher:
    """Small HTTP client with timeout, bounded retry, and a payload-size limit."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 2_000_000,
        retries: int = 1,
        allow_private_hosts: bool = True,
        allow_insecure_http: bool = True,
        max_redirects: int = 3,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._retries = retries
        self._allow_private_hosts = allow_private_hosts
        self._allow_insecure_http = allow_insecure_http
        self._max_redirects = max_redirects

    async def fetch(self, url: str) -> bytes:
        """Fetch a feed without logging URL query values or untrusted response content."""
        timeout = httpx.Timeout(self._timeout_seconds)
        for attempt in range(self._retries + 1):
            try:
                return await self._fetch_once(url, timeout)
            except (httpx.HTTPError, ProviderError) as error:
                if attempt == self._retries:
                    logger.warning("feed_fetch_failed", extra={"attempts": attempt + 1})
                    raise ProviderError("feed fetch failed after bounded retries") from error
                await asyncio.sleep(0.2 * (attempt + 1))
        raise AssertionError("unreachable")

    async def _fetch_once(self, url: str, timeout: httpx.Timeout) -> bytes:
        """Fetch with explicit redirect validation so a feed cannot pivot into private networks."""
        current_url = url
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for redirect_count in range(self._max_redirects + 1):
                _validate_remote_url(
                    current_url,
                    allow_private_hosts=self._allow_private_hosts,
                    allow_insecure_http=self._allow_insecure_http,
                )
                async with client.stream(
                    "GET",
                    current_url,
                    headers={
                        "Accept": (
                            "application/atom+xml, application/rss+xml, application/xml, text/xml"
                        )
                    },
                ) as response:
                    _validate_connected_peer(
                        response, allow_private_hosts=self._allow_private_hosts
                    )
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirect_count == self._max_redirects:
                            raise ProviderError("feed redirect could not be safely followed")
                        current_url = urljoin(current_url, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type and not any(
                        allowed in content_type
                        for allowed in ("xml", "rss", "atom", "text/plain", "text/html")
                    ):
                        raise ProviderError("feed response has an unsupported content type")
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > self._max_response_bytes:
                            raise ProviderError("feed response exceeds configured size limit")
                    return bytes(payload)
        raise ProviderError("feed redirect could not be safely followed")


def _validate_remote_url(
    url: str, *, allow_private_hosts: bool, allow_insecure_http: bool
) -> None:
    """Reject non-web and private-network targets before every outbound feed request."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ProviderError("feed URL is not a safe absolute HTTP(S) URL")
    if parsed.scheme != "https" and not allow_insecure_http:
        raise ProviderError("production feed URLs must use HTTPS")
    if allow_private_hosts:
        return
    try:
        addresses = {address[4][0] for address in socket.getaddrinfo(parsed.hostname, None)}
    except socket.gaierror as error:
        raise ProviderError("feed hostname could not be resolved") from error
    if not addresses:
        raise ProviderError("feed hostname could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ProviderError("feed URL resolves to a non-public address")


def _validate_connected_peer(response: httpx.Response, *, allow_private_hosts: bool) -> None:
    """Fail closed when the actual connected peer is unavailable or non-public."""
    if allow_private_hosts:
        return
    stream = response.extensions.get("network_stream")
    peer = stream.get_extra_info("server_addr") if stream is not None else None
    if not peer or not isinstance(peer, tuple) or not peer:
        raise ProviderError("connected peer address could not be verified")
    try:
        address = ipaddress.ip_address(str(peer[0]).split("%", 1)[0])
    except ValueError as error:
        raise ProviderError("connected peer address could not be verified") from error
    if not address.is_global:
        raise ProviderError("connected peer is a non-public address")


class RssCollector:
    """Collect RSS/Atom metadata only; article-body fetching is deliberately out of scope."""

    def __init__(self, fetcher: FeedFetcher, max_items: int = 100) -> None:
        self._fetcher = fetcher
        self._max_items = max_items

    async def collect(
        self,
        source: RssSourceConfig,
        fetched_at: datetime | None = None,
    ) -> list[SourceItem]:
        """Fetch and normalize source entries into compact candidate items."""
        now = (fetched_at or datetime.now(UTC)).astimezone(UTC)
        payload = await self._fetcher.fetch(source.url)
        lowered = payload.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ProviderError("feed XML contains a prohibited declaration")
        parsed = feedparser.parse(payload)
        entries: list[Mapping[str, Any]] = list(parsed.entries[: self._max_items])
        if parsed.bozo and not entries:
            raise ProviderError("feed XML could not be parsed")
        return [self._normalize_entry(entry, source, now) for entry in entries]

    @staticmethod
    def _normalize_entry(
        entry: Mapping[str, Any],
        source: RssSourceConfig,
        fetched_at: datetime,
    ) -> SourceItem:
        title = str(entry.get("title") or "Untitled source item").strip()[:512]
        snippet = _entry_text(entry)
        source_published_at = parse_source_datetime(
            entry.get("published_parsed") or entry.get("published")
        )
        source_updated_at = parse_source_datetime(entry["updated"] if "updated" in entry else None)
        timestamp_confidence = (
            TimestampConfidence.SOURCE
            if source_published_at
            else TimestampConfidence.DISCOVERED_FALLBACK
        )
        return SourceItem(
            source_name=source.name,
            source_kind=SourceKind.RSS,
            stream=source.stream,
            external_id=_external_id(entry),
            canonical_url=normalize_url(str(entry.get("link") or "")),
            title=title,
            author=_author(entry),
            snippet=snippet,
            source_published_at=source_published_at,
            source_updated_at=source_updated_at,
            discovered_at=fetched_at,
            fetched_at=fetched_at,
            timestamp_confidence=timestamp_confidence,
            source_freshness_hours=source.freshness_hours,
            content_hash=content_fingerprint(title, snippet),
        )


def _entry_text(entry: Mapping[str, Any]) -> str | None:
    """Choose compact feed-provided summary text without fetching the linked article."""
    value = entry.get("summary") or entry.get("description")
    if value is None and entry.get("content"):
        content = entry["content"]
        if isinstance(content, list) and content and isinstance(content[0], Mapping):
            value = content[0].get("value")
    return str(value).strip()[:4_000] if value else None


def _external_id(entry: Mapping[str, Any]) -> str | None:
    """Prefer feed-native identifiers before falling back to URL/hash identity."""
    value = entry.get("id") or entry.get("guid")
    return str(value).strip()[:512] if value else None


def _author(entry: Mapping[str, Any]) -> str | None:
    """Extract an optional compact author value from common feedparser fields."""
    value = entry.get("author")
    return str(value).strip()[:256] if value else None
