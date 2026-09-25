"""Provider-neutral notification delivery with durable idempotency boundaries."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class NotificationKind(StrEnum):
    BRIEFING_READY = "briefing_ready"
    ACTIONABLE_MAIL = "actionable_mail"
    OPERATIONAL_FAILURE = "operational_failure"
    SOURCE_CATEGORY_QUESTION = "source_category_question"


class Notification(BaseModel):
    """A compact message that must never contain raw email or provider error text."""

    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-z0-9:_-]+$")
    kind: NotificationKind
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=500)
    link: str | None = Field(default=None, max_length=512)


class NotificationError(RuntimeError):
    """Safe notification failure category; never carries provider response data."""


SendNotification = Callable[[Notification], Awaitable[None]]
ClaimDelivery = Callable[[Notification], Awaitable[bool]]
RecordDelivery = Callable[[Notification, str | None], Awaitable[None]]


@dataclass(frozen=True)
class DeliveryResult:
    status: str
    category: str | None = None


class NotificationDispatcher:
    """Ensure a notification cannot undo or duplicate completed ingestion work."""

    def __init__(
        self,
        send: SendNotification,
        claim: ClaimDelivery,
        mark_delivered: RecordDelivery,
        mark_failed: RecordDelivery,
    ) -> None:
        self._send = send
        self._claim = claim
        self._mark_delivered = mark_delivered
        self._mark_failed = mark_failed

    async def deliver(self, notification: Notification) -> DeliveryResult:
        """Send one claimed notification; failures are isolated from the caller's completed work."""
        try:
            if not await self._claim(notification):
                return DeliveryResult("duplicate_skipped")
            await self._send(notification)
            await self._mark_delivered(notification, None)
            return DeliveryResult("delivered")
        except NotificationError as error:
            await self._safe_mark_failed(notification, type(error).__name__)
            return DeliveryResult("failed", type(error).__name__)
        except Exception:
            await self._safe_mark_failed(notification, "notification_delivery_error")
            return DeliveryResult("failed", "notification_delivery_error")

    async def _safe_mark_failed(self, notification: Notification, category: str) -> None:
        try:
            await self._mark_failed(notification, category)
        except Exception:
            return None


def notification_key(kind: NotificationKind, identity: str) -> str:
    """Create an opaque deterministic key without retaining a Gmail/event identifier in ntfy."""
    digest = sha256(f"{kind}:{identity}".encode()).hexdigest()[:32]
    return f"{kind}:{digest}"


async def deliver_ordered(
    dispatchers: list[NotificationDispatcher], notifications: list[Notification]
) -> list[DeliveryResult]:
    """Deliver each channel's messages in order while allowing separate channels to progress."""
    async def deliver_channel(dispatcher: NotificationDispatcher) -> list[DeliveryResult]:
        return [
            await dispatcher.deliver(notification)
            for notification in notifications
        ]

    per_channel = await asyncio.gather(*(deliver_channel(item) for item in dispatchers))
    return [result for channel_results in per_channel for result in channel_results]


def database_dispatcher(
    sessions: async_sessionmaker[AsyncSession], send: SendNotification, *, channel: str = "ntfy"
) -> NotificationDispatcher:
    """Persist per-channel delivery state and permit safe retries of failed logical messages."""
    allowed_characters = "abcdefghijklmnopqrstuvwxyz0123456789:_-"
    if not channel or len(channel) > 32 or any(char not in allowed_characters for char in channel):
        raise ValueError("notification channel must be a short safe identifier")

    async def claim(notification: Notification) -> bool:
        async with sessions.begin() as session:
            row = await session.execute(
                text(
                    "INSERT INTO notification_deliveries "
                    "(channel, idempotency_key, kind, status, attempts) "
                    "VALUES (:channel, :key, :kind, 'pending', 1) "
                    "ON CONFLICT (channel, idempotency_key) DO UPDATE "
                    "SET status = 'pending', attempts = notification_deliveries.attempts + 1, "
                    "failure_category = NULL, updated_at = now() "
                    "WHERE notification_deliveries.status = 'failed' "
                    "RETURNING idempotency_key"
                ),
                {
                    "channel": channel,
                    "key": notification.idempotency_key,
                    "kind": notification.kind.value,
                },
            )
        return row.scalar_one_or_none() is not None

    async def mark_delivered(notification: Notification, _: str | None) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE notification_deliveries SET status = 'delivered', "
                    "delivered_at = now(), "
                    "failure_category = NULL, updated_at = now() WHERE channel = :channel "
                    "AND idempotency_key = :key"
                ),
                {"channel": channel, "key": notification.idempotency_key},
            )

    async def mark_failed(notification: Notification, category: str | None) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE notification_deliveries SET status = 'failed', "
                    "failure_category = :category, "
                    "updated_at = now() WHERE channel = :channel AND idempotency_key = :key"
                ),
                {"channel": channel, "key": notification.idempotency_key, "category": category},
            )

    return NotificationDispatcher(send, claim, mark_delivered, mark_failed)


async def notification_delivery_status(
    sessions: async_sessionmaker[AsyncSession], idempotency_key: str, channel: str
) -> str | None:
    """Read a bounded per-channel receipt without returning notification or recipient data."""
    async with sessions() as session:
        value = await session.scalar(
            text(
                "SELECT status FROM notification_deliveries "
                "WHERE channel = :channel AND idempotency_key = :key"
            ),
            {"channel": channel, "key": idempotency_key},
        )
    return str(value) if value is not None else None


async def notification_delivery_state(
    sessions: async_sessionmaker[AsyncSession], idempotency_key: str, channel: str
) -> tuple[str | None, int, int | None]:
    """Read only the status, bounded attempt count, and age of one channel receipt."""
    async with sessions() as session:
        row = (
            await session.execute(
                text(
                    "SELECT status, attempts, "
                    "floor(extract(epoch FROM now() - updated_at))::integer AS age_seconds "
                    "FROM notification_deliveries "
                    "WHERE channel = :channel AND idempotency_key = :key"
                ),
                {"channel": channel, "key": idempotency_key},
            )
        ).mappings().one_or_none()
    if row is None:
        return None, 0, None
    return str(row["status"]), int(row["attempts"]), int(row["age_seconds"])


async def release_stale_pending_delivery(
    sessions: async_sessionmaker[AsyncSession],
    idempotency_key: str,
    channel: str,
    *,
    stale_after_seconds: int,
) -> bool:
    """Release a crashed pending claim so a bounded retry can recover after restart."""
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be positive")
    async with sessions.begin() as session:
        result = await session.execute(
            text(
                "UPDATE notification_deliveries SET status = 'failed', "
                "failure_category = 'notification_lease_expired', updated_at = now() "
                "WHERE channel = :channel AND idempotency_key = :key AND status = 'pending' "
                "AND updated_at < now() - (:stale_after_seconds * interval '1 second') "
                "RETURNING idempotency_key"
            ),
            {
                "channel": channel,
                "key": idempotency_key,
                "stale_after_seconds": stale_after_seconds,
            },
        )
    return result.scalar_one_or_none() is not None
