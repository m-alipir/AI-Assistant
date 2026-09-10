"""Safe, bounded public article fetch and offline HTML extraction boundary."""

import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
import trafilatura

from app.collectors.rss import _validate_connected_peer, _validate_remote_url
from app.providers.contracts import ProviderError


@dataclass(frozen=True)
class ArticleContent:
    text: str
    final_url: str


class ArticleFetcher:
    """Fetch public HTML with redirect-by-redirect validation and response bounds."""

    def __init__(
        self,
        timeout_seconds: float = 12,
        max_response_bytes: int = 3_000_000,
        retries: int = 1,
        allow_private_hosts: bool = True,
        allow_insecure_http: bool = True,
        max_redirects: int = 3,
    ) -> None:
        self._timeout, self._max_bytes, self._retries = timeout_seconds, max_response_bytes, retries
        self._allow_private, self._allow_insecure, self._max_redirects = (
            allow_private_hosts,
            allow_insecure_http,
            max_redirects,
        )

    async def fetch(self, url: str) -> ArticleContent:
        for attempt in range(self._retries + 1):
            try:
                return await self._fetch_once(url)
            except (httpx.HTTPError, ProviderError):
                if attempt == self._retries:
                    raise ProviderError("article fetch failed") from None
                await asyncio.sleep(0.2 * (attempt + 1))
        raise AssertionError("unreachable")

    async def _fetch_once(self, url: str) -> ArticleContent:
        current = url
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout), follow_redirects=False
        ) as client:
            for redirects in range(self._max_redirects + 1):
                _validate_remote_url(
                    current,
                    allow_private_hosts=self._allow_private,
                    allow_insecure_http=self._allow_insecure,
                )
                async with client.stream(
                    "GET", current, headers={"Accept": "text/html,application/xhtml+xml"}
                ) as response:
                    _validate_connected_peer(response, allow_private_hosts=self._allow_private)
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or redirects == self._max_redirects:
                            raise ProviderError("article redirect could not be safely followed")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").casefold()
                    allowed_types = ("text/html", "application/xhtml+xml")
                    if not any(allowed in content_type for allowed in allowed_types):
                        raise ProviderError("article response has an unsupported content type")
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > self._max_bytes:
                            raise ProviderError("article response exceeds configured size limit")
                    return ArticleContent(_extract_html(bytes(payload)), current)
        raise ProviderError("article redirect could not be safely followed")


def _extract_html(payload: bytes) -> str:
    """Parse already-fetched HTML only; parsing never initiates another network request."""
    try:
        text = trafilatura.extract(
            payload.decode("utf-8", errors="replace"),
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception as error:
        raise ProviderError("article HTML extraction failed") from error
    if not text or len(text.strip()) < 80:
        raise ProviderError("article did not contain sufficient extractable text")
    return text.strip()
