import pytest

from app.notifications.core import (
    Notification,
    NotificationDispatcher,
    NotificationError,
    NotificationKind,
    notification_key,
)
from app.notifications.ntfy import NtfyNotifier


def _notification() -> Notification:
    return Notification(
        idempotency_key=notification_key(NotificationKind.BRIEFING_READY, "2026-09-10"),
        kind=NotificationKind.BRIEFING_READY,
        title="Günlük özet hazır",
        body="Yeni özet hazır.",
        link="https://admin.example.test/admin",
    )


@pytest.mark.asyncio
async def test_dispatcher_deduplicates_and_isolates_delivery_failure() -> None:
    claimed: set[str] = set()
    states: list[tuple[str, str | None]] = []

    async def claim(notification: Notification) -> bool:
        if notification.idempotency_key in claimed:
            return False
        claimed.add(notification.idempotency_key)
        return True

    async def send(_: Notification) -> None:
        return None

    async def record(notification: Notification, category: str | None) -> None:
        states.append((notification.idempotency_key, category))

    dispatcher = NotificationDispatcher(send, claim, record, record)

    assert (await dispatcher.deliver(_notification())).status == "delivered"
    assert (await dispatcher.deliver(_notification())).status == "duplicate_skipped"
    assert states == [(_notification().idempotency_key, None)]


@pytest.mark.asyncio
async def test_dispatcher_records_failure_without_raising_to_completed_caller() -> None:
    failures: list[str | None] = []

    async def claim(_: Notification) -> bool:
        return True

    async def fail(_: Notification) -> None:
        raise NotificationError("ntfy_http_error")

    async def record(_: Notification, category: str | None) -> None:
        failures.append(category)

    result = await NotificationDispatcher(fail, claim, record, record).deliver(_notification())

    assert result.status == "failed"
    assert result.category == "NotificationError"
    assert failures == ["NotificationError"]


@pytest.mark.asyncio
async def test_ntfy_uses_sequence_id_and_bounded_retry_without_response_body() -> None:
    calls: list[tuple[str, dict[str, str], str]] = []

    async def publish(url: str, headers: dict[str, str], body: str) -> int:
        calls.append((url, headers, body))
        return 503 if len(calls) == 1 else 200

    notifier = NtfyNotifier(
        "https://ntfy.example.test",
        "private_topic",
        "token-value-not-logged",
        retries=1,
        publish=publish,
    )

    await notifier.send(_notification())

    assert len(calls) == 2
    assert calls[-1][0] == "https://ntfy.example.test/private_topic"
    assert calls[-1][1]["X-Sequence-ID"] == _notification().idempotency_key
    assert calls[-1][1]["Click"] == "https://admin.example.test/admin"
    assert calls[-1][2] == "Yeni özet hazır."
