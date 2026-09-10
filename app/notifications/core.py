"""Provider-neutral notification delivery with durable idempotency boundaries."""

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


def database_dispatcher(
    sessions: async_sessionmaker[AsyncSession], send: SendNotification
) -> NotificationDispatcher:
    """Persist delivery state and permit only safe retries of a failed logical message."""

    async def claim(notification: Notification) -> bool:
        async with sessions.begin() as session:
            row = await session.execute(
                text(
                    "INSERT INTO notification_deliveries "
                    "(idempotency_key, kind, status, attempts) "
                    "VALUES (:key, :kind, 'pending', 1) "
                    "ON CONFLICT (idempotency_key) DO UPDATE "
                    "SET status = 'pending', attempts = notification_deliveries.attempts + 1, "
                    "failure_category = NULL, updated_at = now() "
                    "WHERE notification_deliveries.status = 'failed' "
                    "RETURNING idempotency_key"
                ),
                {"key": notification.idempotency_key, "kind": notification.kind.value},
            )
        return row.scalar_one_or_none() is not None

    async def mark_delivered(notification: Notification, _: str | None) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE notification_deliveries SET status = 'delivered', "
                    "delivered_at = now(), "
                    "failure_category = NULL, updated_at = now() WHERE idempotency_key = :key"
                ),
                {"key": notification.idempotency_key},
            )

    async def mark_failed(notification: Notification, category: str | None) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE notification_deliveries SET status = 'failed', "
                    "failure_category = :category, "
                    "updated_at = now() WHERE idempotency_key = :key"
                ),
                {"key": notification.idempotency_key, "category": category},
            )

    return NotificationDispatcher(send, claim, mark_delivered, mark_failed)
