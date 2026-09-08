"""Small Gmail REST client using only the existing read-only OAuth grant."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import ceil
from typing import Any

import httpx

from app.email.core import EmailMessage

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailApiError(Exception):
    """Safe transport error; response bodies and credentials are deliberately omitted."""

    def __init__(self, category: str, status_code: int | None = None) -> None:
        self.category = category
        self.status_code = status_code
        super().__init__(category)


@dataclass(frozen=True)
class GmailBatch:
    messages: list[EmailMessage]
    history_id: str | None


class GmailApiClient:
    """Bounded Gmail metadata collector with retry and history-based incremental sync."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        initial_lookback_hours: int = 48,
        initial_max_messages: int = 25,
        timeout_seconds: float = 15,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._initial_lookback_hours = initial_lookback_hours
        self._initial_max_messages = initial_max_messages
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport

    async def sync(self, refresh_token: str, history_id: str | None) -> GmailBatch:
        """Fetch a bounded initial batch or only message additions after a checkpoint."""
        access_token = await self._refresh_access_token(refresh_token)
        profile = await self._get_json(access_token, "/profile")
        current_history_id = _optional_string(profile.get("historyId"))
        if history_id:
            try:
                message_ids, incremental_history = await self._history_message_ids(
                    access_token, history_id
                )
                return GmailBatch(
                    await self._metadata_messages(access_token, message_ids),
                    incremental_history or current_history_id,
                )
            except GmailApiError as error:
                if error.status_code != 404:
                    raise
        message_ids = await self._initial_message_ids(access_token)
        return GmailBatch(
            await self._metadata_messages(access_token, message_ids), current_history_id
        )

    async def _refresh_access_token(self, refresh_token: str) -> str:
        response = await self._request(
            "POST",
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        payload = _json_mapping(response, "token_response_invalid")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise GmailApiError("access_token_missing")
        return token

    async def _initial_message_ids(self, access_token: str) -> list[str]:
        days = max(1, ceil(self._initial_lookback_hours / 24))
        payload = await self._get_json(
            access_token,
            "/messages",
            params={
                "labelIds": "INBOX",
                "q": f"newer_than:{days}d",
                "maxResults": str(self._initial_max_messages),
            },
        )
        return _message_ids(payload.get("messages"), self._initial_max_messages)

    async def _history_message_ids(
        self, access_token: str, history_id: str
    ) -> tuple[list[str], str | None]:
        payload = await self._get_json(
            access_token,
            "/history",
            params={
                "startHistoryId": history_id,
                "historyTypes": "messageAdded",
                "maxResults": str(self._initial_max_messages),
            },
        )
        message_ids: list[str] = []
        for entry in payload.get("history", []):
            if not isinstance(entry, dict):
                continue
            for added in entry.get("messagesAdded", []):
                if isinstance(added, dict) and isinstance(added.get("message"), dict):
                    message_id = added["message"].get("id")
                    if isinstance(message_id, str):
                        message_ids.append(message_id)
        return _deduplicated(message_ids, self._initial_max_messages), _optional_string(
            payload.get("historyId")
        )

    async def _metadata_messages(
        self, access_token: str, message_ids: Iterable[str]
    ) -> list[EmailMessage]:
        messages: list[EmailMessage] = []
        for message_id in message_ids:
            payload = await self._get_json(
                access_token,
                f"/messages/{message_id}",
                params={
                    "format": "metadata",
                    "metadataHeaders": ["From", "Subject", "Date"],
                },
            )
            labels = payload.get("labelIds")
            if isinstance(labels, list) and "INBOX" not in labels:
                continue
            messages.append(_metadata_message(payload, message_id))
        return messages

    async def _get_json(
        self, access_token: str, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"{GMAIL_API_URL}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        return _json_mapping(response, "gmail_response_invalid")

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: GmailApiError | None = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout_seconds, transport=self._transport
                ) as client:
                    response = await client.request(method, url, **kwargs)
                if response.status_code < 400:
                    return response
                last_error = GmailApiError("gmail_http_error", response.status_code)
                if response.status_code < 500 and response.status_code != 429:
                    raise last_error
            except httpx.HTTPError as error:
                last_error = GmailApiError("gmail_network_error")
                if attempt == self._max_retries:
                    raise last_error from error
            if attempt < self._max_retries:
                await asyncio.sleep(0.1 * (attempt + 1))
        assert last_error is not None
        raise last_error


def _json_mapping(response: httpx.Response, category: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise GmailApiError(category) from error
    if not isinstance(payload, dict):
        raise GmailApiError(category)
    return payload


def _metadata_message(payload: dict[str, Any], fallback_id: str) -> EmailMessage:
    message_payload = payload.get("payload")
    headers = message_payload.get("headers", []) if isinstance(message_payload, dict) else []
    values = {
        str(header.get("name", "")).casefold(): str(header.get("value", ""))
        for header in headers
        if isinstance(header, dict)
    }
    received_at = _received_at(payload, values.get("date"))
    return EmailMessage(
        message_id=_optional_string(payload.get("id")) or fallback_id,
        sender=values.get("from", ""),
        subject=values.get("subject", "(no subject)"),
        body="",
        received_at=received_at,
    )


def _received_at(payload: dict[str, Any], date_header: str | None) -> datetime:
    internal_date = _optional_string(payload.get("internalDate"))
    if internal_date and internal_date.isdigit():
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass
    return datetime.now(UTC)


def _message_ids(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return _deduplicated(
        [
            item["id"]
            for item in value
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ],
        limit,
    )


def _deduplicated(values: Iterable[str], limit: int) -> list[str]:
    return list(dict.fromkeys(values))[:limit]


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
