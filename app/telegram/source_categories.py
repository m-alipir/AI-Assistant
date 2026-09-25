"""Bounded, receipt-backed Telegram prompts for ambiguous managed-source categories."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import Settings
from app.config.source_repository import SourceRepository
from app.notifications.core import (
    DeliveryResult,
    Notification,
    NotificationKind,
    database_dispatcher,
    notification_delivery_state,
    notification_delivery_status,
    notification_key,
    release_stale_pending_delivery,
)
from app.telegram.core import TelegramBotClient

logger = logging.getLogger(__name__)
_SOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_QUESTION_SCAN_PAGE_SIZE = 100
_QUESTION_SEND_LIMIT = 3
_QUESTION_PENDING_LEASE_SECONDS = 15 * 60
_QUESTION_MAX_ATTEMPTS = 8
_QUESTION_RETRY_BASE_SECONDS = 30
_QUESTION_RETRY_MAX_SECONDS = 60 * 60
_QUESTION_SCAN_INTERVAL_SECONDS = 30


def telegram_delivery_channel(chat_id: int) -> str:
    """Return the existing channel-scoped receipt identifier without storing a chat ID."""
    digest = hashlib.sha256(str(chat_id).encode()).hexdigest()[:20]
    return f"tg-{digest}"


def source_category_question(source_id: str) -> Notification:
    """Build one short explicit command prompt; never include the endpoint or source content."""
    if not _SOURCE_ID.fullmatch(source_id):
        raise ValueError("invalid managed source id")
    return Notification(
        idempotency_key=notification_key(NotificationKind.SOURCE_CATEGORY_QUESTION, source_id),
        kind=NotificationKind.SOURCE_CATEGORY_QUESTION,
        title="Kaynak kategorisi gerekiyor",
        body=(
            f"Kaynak kimliği: {source_id}. Kategori yanıtı için "
            f"/kaynak_kategori {source_id} <kategori> komutunu kullanın "
            "(en fazla 128 karakter)."
        ),
    )


async def send_source_category_question(
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
    bot: TelegramBotClient | None,
    source_id: str,
) -> DeliveryResult:
    """Send one bounded question to the exact allow-listed operator chat."""
    if not settings.telegram_enabled or bot is None:
        return DeliveryResult("unavailable", "telegram_not_configured")
    target_chat = settings.telegram_source_operator_chat_id
    allowed_chats = {allowed_chat for _, allowed_chat in settings.telegram_allowed_actor_pair_list}
    if target_chat is None or target_chat not in allowed_chats:
        return DeliveryResult("unavailable", "telegram_chat_not_allowlisted")

    notification = source_category_question(source_id)
    channel = telegram_delivery_channel(target_chat)
    status, attempts, age_seconds = await notification_delivery_state(
        sessions, notification.idempotency_key, channel
    )
    if status == "delivered":
        return DeliveryResult("duplicate_skipped")
    if status == "pending":
        if age_seconds is None or age_seconds < _QUESTION_PENDING_LEASE_SECONDS:
            return DeliveryResult("duplicate_skipped")
        released = await release_stale_pending_delivery(
            sessions,
            notification.idempotency_key,
            channel,
            stale_after_seconds=_QUESTION_PENDING_LEASE_SECONDS,
        )
        if not released:
            return DeliveryResult("duplicate_skipped")
        status, attempts, age_seconds = "failed", attempts, 0
    if attempts >= _QUESTION_MAX_ATTEMPTS:
        return DeliveryResult("retry_exhausted", "category_question_attempt_limit")
    if status == "failed":
        retry_delay = min(
            _QUESTION_RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)),
            _QUESTION_RETRY_MAX_SECONDS,
        )
        if age_seconds is not None and age_seconds < retry_delay:
            return DeliveryResult("retry_deferred", "category_question_retry_backoff")

    async def send(message: Notification) -> None:
        await bot.send_notification(target_chat, message)

    dispatcher = database_dispatcher(sessions, send, channel=channel)
    result = await dispatcher.deliver(notification)
    if result.status == "failed":
        logger.warning(
            "telegram_source_category_question_failed",
            extra={"diagnostic_category": result.category or "notification_delivery_error"},
        )
    return result


async def source_category_question_was_delivered(
    sessions: async_sessionmaker[AsyncSession], source_id: str, chat_id: int
) -> bool:
    """Allow answers only from the exact chat whose durable question receipt is delivered."""
    notification = source_category_question(source_id)
    return (
        await notification_delivery_status(
            sessions,
            notification.idempotency_key,
            telegram_delivery_channel(chat_id),
        )
        == "delivered"
    )


async def dispatch_pending_source_category_questions(
    repository: SourceRepository,
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
    bot: TelegramBotClient | None,
    *,
    offset: int = 0,
) -> tuple[list[DeliveryResult], int]:
    """Scan one bounded page and send at most three due questions to the operator."""
    if not settings.telegram_enabled or bot is None:
        return [], 0
    rows = await repository.list_pending_categories(
        limit=_QUESTION_SCAN_PAGE_SIZE, offset=offset
    )
    if not rows:
        return [], 0

    results: list[DeliveryResult] = []
    attempts_this_pass = 0
    next_offset = offset
    for index, row in enumerate(rows):
        next_offset = offset + index + 1
        if row.get("category") is not None:
            continue
        source_id = str(row.get("id") or "")
        if not source_id:
            continue
        result = await send_source_category_question(sessions, settings, bot, source_id)
        results.append(result)
        if result.status == "failed":
            break
        if result.status == "delivered":
            attempts_this_pass += 1
            if attempts_this_pass >= _QUESTION_SEND_LIMIT:
                break
        elif result.status == "unavailable":
            break
    return results, next_offset


async def run_source_category_question_worker(
    repository: SourceRepository,
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
    bot: TelegramBotClient | None,
    stop_event: asyncio.Event,
) -> None:
    """Retry pending categories in a bounded page loop for webhook or polling operation."""
    offset = 0
    while not stop_event.is_set():
        try:
            _, offset = await dispatch_pending_source_category_questions(
                repository, sessions, settings, bot, offset=offset
            )
        except Exception:
            logger.warning(
                "telegram_source_category_scan_failed",
                extra={"diagnostic_category": "category_question_scan_unavailable"},
            )
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=_QUESTION_SCAN_INTERVAL_SECONDS
            )
        except TimeoutError:
            continue
