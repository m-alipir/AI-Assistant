"""Small direct Telegram Bot API client with safe plain-text rendering."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.notifications.core import Notification

MAX_MESSAGE_CHARS = 4_000
MAX_CALLBACK_ANSWER_CHARS = 200

TelegramTransport = Callable[[str, dict[str, object]], Awaitable[tuple[int, bool, int | None]]]
PollingTransport = Callable[
    [str, dict[str, object]],
    Awaitable[tuple[int, bool, int | None, list[dict[str, object]] | None]],
]


class TelegramDeliveryError(RuntimeError):
    """Safe outbound error category; provider details must never leave the client."""


@dataclass(frozen=True)
class TelegramMessage:
    text: str
    reply_markup: dict[str, object] | None = None


class TelegramBotClient:
    """Send only bounded plain-text Bot API messages through a direct HTTP boundary."""

    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float,
        retries: int,
        transport: TelegramTransport | None = None,
        polling_transport: PollingTransport | None = None,
    ) -> None:
        self._base_url = f"https://api.telegram.org/bot{quote(token, safe=':_-')}/"
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._transport = transport or self._post
        self._polling_transport = polling_transport or self._poll_post

    async def send_message(
        self, chat_id: int, message: TelegramMessage, *, protect_content: bool = True
    ) -> None:
        """Send one message with no parse mode, previews, or unbounded provider error exposure."""
        if not message.text or len(message.text) > MAX_MESSAGE_CHARS:
            raise TelegramDeliveryError("telegram_message_invalid")
        payload: dict[str, object] = {
            "chat_id": chat_id,
            "text": message.text,
            "disable_web_page_preview": True,
            "protect_content": protect_content,
        }
        if message.reply_markup is not None:
            payload["reply_markup"] = message.reply_markup
        await self._call("sendMessage", payload)

    async def send_messages(self, chat_id: int, messages: list[TelegramMessage]) -> None:
        for message in messages:
            await self.send_message(chat_id, message)

    async def send_notification(self, chat_id: int, notification: Notification) -> None:
        """Map the existing minimized notification contract into one protected Telegram message."""
        parts = [notification.title, notification.body]
        if notification.link:
            parts.append(notification.link)
        await self.send_message(chat_id, TelegramMessage("\n".join(parts)))

    async def answer_callback_query(self, callback_query_id: str, text: str) -> None:
        """Dismiss Telegram's callback spinner with a fixed, non-sensitive status message."""
        if (
            not callback_query_id
            or len(callback_query_id) > 128
            or not text
            or len(text) > MAX_CALLBACK_ANSWER_CHARS
        ):
            raise TelegramDeliveryError("telegram_callback_answer_invalid")
        await self._call(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_query_id,
                "text": text,
            },
        )

    async def configure_webhook(self, webhook_url: str, secret_token: str) -> None:
        """Set approved update types through an explicit operator action, never at startup."""
        await self._call(
            "setWebhook",
            {
                "url": webhook_url,
                "secret_token": secret_token,
                "allowed_updates": ["message", "callback_query"],
                "max_connections": 2,
            },
        )

    async def delete_webhook(self) -> None:
        """Disable a prior webhook without discarding queued Telegram updates."""
        await self._call("deleteWebhook", {"drop_pending_updates": False})

    async def get_updates(
        self, *, offset: int, timeout_seconds: int, limit: int
    ) -> list[dict[str, object]]:
        """Receive one bounded long-poll batch without retaining provider response bodies."""
        payload: dict[str, object] = {
            "offset": offset,
            "timeout": timeout_seconds,
            "limit": limit,
            "allowed_updates": ["message", "callback_query"],
        }
        for attempt in range(self._retries + 1):
            try:
                status, ok, retry_after, updates = await self._polling_transport(
                    "getUpdates", payload
                )
            except httpx.HTTPError as error:
                if attempt == self._retries:
                    raise TelegramDeliveryError("telegram_transport_error") from error
            else:
                if 200 <= status < 300 and ok and updates is not None:
                    return updates[:limit]
                retryable = status >= 500 or status == 429
                if not retryable or attempt == self._retries:
                    raise TelegramDeliveryError("telegram_api_error")
                await asyncio.sleep(min(max(retry_after or 1, 1), 10))
                continue
            await asyncio.sleep(0.2 * (attempt + 1))
        raise TelegramDeliveryError("telegram_delivery_error")

    async def _call(self, method: str, payload: dict[str, object]) -> None:
        for attempt in range(self._retries + 1):
            try:
                status, ok, retry_after = await self._transport(method, payload)
            except httpx.HTTPError as error:
                if attempt == self._retries:
                    raise TelegramDeliveryError("telegram_transport_error") from error
            else:
                if 200 <= status < 300 and ok:
                    return
                retryable = status >= 500 or status == 429
                if not retryable or attempt == self._retries:
                    raise TelegramDeliveryError("telegram_api_error")
                delay = min(max(retry_after or 1, 1), 10)
                await asyncio.sleep(delay)
                continue
            await asyncio.sleep(0.2 * (attempt + 1))
        raise TelegramDeliveryError("telegram_delivery_error")

    async def _post(self, method: str, payload: dict[str, object]) -> tuple[int, bool, int | None]:
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(f"{self._base_url}{method}", json=payload)
        retry_after: int | None = None
        try:
            response_json: Any = response.json()
            if isinstance(response_json, dict):
                parameters = response_json.get("parameters")
                if isinstance(parameters, dict) and isinstance(parameters.get("retry_after"), int):
                    retry_after = parameters["retry_after"]
                ok = response_json.get("ok") is True
            else:
                ok = False
        except ValueError:
            ok = False
        return response.status_code, ok, retry_after

    async def _poll_post(
        self, method: str, payload: dict[str, object]
    ) -> tuple[int, bool, int | None, list[dict[str, object]] | None]:
        timeout = httpx.Timeout(self._timeout_seconds + int(payload["timeout"]) + 5)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(f"{self._base_url}{method}", json=payload)
        retry_after: int | None = None
        updates: list[dict[str, object]] | None = None
        try:
            response_json: Any = response.json()
            ok = isinstance(response_json, dict) and response_json.get("ok") is True
            if isinstance(response_json, dict):
                parameters = response_json.get("parameters")
                if isinstance(parameters, dict) and isinstance(parameters.get("retry_after"), int):
                    retry_after = parameters["retry_after"]
                result = response_json.get("result")
                if isinstance(result, list) and all(isinstance(item, dict) for item in result):
                    updates = result
        except ValueError:
            ok = False
        return response.status_code, ok, retry_after, updates


def split_plain_text(value: str, *, maximum: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split at a readable boundary while preserving literal, non-formatted text."""
    normalized = "\n".join(line.rstrip() for line in value.splitlines()).strip()
    if not normalized:
        return ["Kaydedilmiş içerik şu anda gösterilemiyor."]
    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > maximum:
        boundary = max(remaining.rfind("\n", 0, maximum), remaining.rfind(" ", 0, maximum))
        if boundary < maximum // 2:
            boundary = maximum
        chunks.append(remaining[:boundary].rstrip())
        remaining = remaining[boundary:].lstrip()
    chunks.append(remaining)
    return chunks


def feedback_keyboard(token: str) -> dict[str, object]:
    """Build fixed actions; server-side token lookup supplies the event and actor binding."""
    return {
        "inline_keyboard": [
            [
                {"text": "Daha fazla", "callback_data": f"f:{token}:more"},
                {"text": "Daha az", "callback_data": f"f:{token}:less"},
                {"text": "Faydalı değil", "callback_data": f"f:{token}:not_useful"},
            ]
        ]
    }
