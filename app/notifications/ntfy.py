"""Small ntfy HTTP adapter with bounded retries and deterministic sequence IDs."""

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import quote

import httpx

from app.notifications.core import Notification, NotificationError

HttpPublish = Callable[[str, dict[str, str], str], Awaitable[int]]


class NtfyNotifier:
    """Publish a privacy-minimized notification to one configured ntfy topic."""

    def __init__(
        self,
        base_url: str,
        topic: str,
        token: str,
        timeout_seconds: float = 10,
        retries: int = 1,
        publish: HttpPublish | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/{quote(topic, safe='')}"
        self._token = token
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._publish = publish or self._publish_once

    async def send(self, notification: Notification) -> None:
        """Publish or update the deterministic ntfy sequence for this logical notification."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Title": notification.title,
            "X-Sequence-ID": notification.idempotency_key,
        }
        if notification.link:
            headers["Click"] = notification.link
        for attempt in range(self._retries + 1):
            try:
                status = await self._publish(self._url, headers, notification.body)
                if 200 <= status < 300:
                    return
                if status < 500 or attempt == self._retries:
                    raise NotificationError("ntfy_http_error")
            except httpx.HTTPError as error:
                if attempt == self._retries:
                    raise NotificationError("ntfy_transport_error") from error
            await asyncio.sleep(0.2 * (attempt + 1))
        raise NotificationError("ntfy_delivery_error")

    async def _publish_once(self, url: str, headers: dict[str, str], body: str) -> int:
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(url, headers=headers, content=body.encode("utf-8"))
        return response.status_code
