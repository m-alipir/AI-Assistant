from datetime import UTC, datetime

import pytest

from app.email.core import EmailMessage
from app.email.gmail_api import GmailBatch
from app.jobs.gmail_runtime import GmailAccountRecord, GmailRuntimeJob, sync_gmail


def message(message_id: str, sender: str, subject: str, now: datetime) -> EmailMessage:
    return EmailMessage(
        message_id=message_id,
        sender=sender,
        subject=subject,
        body="private body that must not be persisted",
        received_at=now,
    )


@pytest.mark.asyncio
async def test_disabled_gmail_does_not_call_transport() -> None:
    async def fetch() -> list[EmailMessage]:
        raise AssertionError("disabled Gmail must not fetch")

    result = await sync_gmail(False, False, fetch)
    assert result["gmail"]["status"] == "not_configured"
    assert result["gmail"]["fetched"] == 0


@pytest.mark.asyncio
async def test_gmail_rules_mute_noise_before_any_llm_path() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    async def fetch() -> list[EmailMessage]:
        return [
            message("a", "jobs@linkedin.com", "Recommended jobs for you", now),
            message("b", "security@example.com", "Security sign-in alert", now),
        ]

    result = await sync_gmail(True, True, fetch)
    assert result["gmail"] == {
        "status": "ready",
        "fetched": 2,
        "muted": 1,
        "relevant": 1,
        "action_items": 1,
        "processed": 1,
        "duplicates": 0,
        "failed": 0,
        "failure_categories": {
            "account_access_error": 0,
            "classification_error": 0,
            "checkpoint_error": 0,
        },
    }


@pytest.mark.asyncio
async def test_runtime_persists_no_bodies_and_checkpoints_after_processing() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    persisted: list[tuple[str, str, str | None]] = []
    checkpoints: list[tuple[str, str | None]] = []

    async def accounts() -> list[GmailAccountRecord]:
        return [GmailAccountRecord("acct", "encrypted", "100")]

    def decrypt(value: str) -> str:
        assert value == "encrypted"
        return "refresh-token"

    async def fetch(account: GmailAccountRecord, token: str) -> GmailBatch:
        assert account.history_id == "100"
        assert token == "refresh-token"
        return GmailBatch(
            [
                message("noise", "jobs@linkedin.com", "Recommended jobs for you", now),
                message("alert", "security@example.com", "Security sign-in alert", now),
            ],
            "101",
        )

    async def known(source_item_id: str) -> bool:
        return False

    async def persist(source_item_id: str, classification: object) -> None:
        persisted.append(
            (source_item_id, classification.classification, classification.action_summary)
        )

    async def checkpoint(account_id: str, history_id: str | None, synced_at: datetime) -> None:
        assert synced_at == now
        checkpoints.append((account_id, history_id))

    run = await GmailRuntimeJob(
        accounts, decrypt, fetch, known, persist, checkpoint, clock=lambda: now
    ).run()
    assert run.response(True)["gmail"] == {
        "status": "ready",
        "fetched": 2,
        "muted": 1,
        "relevant": 1,
        "action_items": 1,
        "processed": 1,
        "duplicates": 0,
        "failed": 0,
        "failure_categories": {
            "account_access_error": 0,
            "classification_error": 0,
            "checkpoint_error": 0,
        },
    }
    assert persisted == [
        ("gmail:acct:noise", "recommendation", None),
        ("gmail:acct:alert", "security", "Review account security alert."),
    ]
    assert checkpoints == [("acct", "101")]
    assert run.action_items[0].source_type == "gmail"
    assert run.action_items[0].title == "Review account security alert."
    assert "private body" not in str(persisted)


@pytest.mark.asyncio
async def test_runtime_duplicate_messages_skip_processing_but_advance_checkpoint() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    persisted: list[str] = []
    checkpoints: list[str | None] = []

    async def accounts() -> list[GmailAccountRecord]:
        return [GmailAccountRecord("acct", "encrypted", "101")]

    async def fetch(account: GmailAccountRecord, token: str) -> GmailBatch:
        return GmailBatch([message("alert", "security@example.com", "Security", now)], "102")

    async def known(source_item_id: str) -> bool:
        return True

    async def persist(source_item_id: str, classification: object) -> None:
        persisted.append(source_item_id)

    async def checkpoint(account_id: str, history_id: str | None, synced_at: datetime) -> None:
        checkpoints.append(history_id)

    run = await GmailRuntimeJob(
        accounts, lambda value: "token", fetch, known, persist, checkpoint, clock=lambda: now
    ).run()
    assert run.duplicates == 1
    assert run.processed == 0
    assert not persisted
    assert checkpoints == ["102"]


@pytest.mark.asyncio
async def test_gmail_transport_failure_does_not_raise_from_runtime() -> None:
    async def accounts() -> list[GmailAccountRecord]:
        return [GmailAccountRecord("acct", "encrypted", None)]

    async def fetch(account: GmailAccountRecord, token: str) -> GmailBatch:
        raise RuntimeError("provider failure")

    async def should_not_run(*args: object) -> None:
        raise AssertionError("message persistence must not run")

    run = await GmailRuntimeJob(
        accounts,
        lambda value: "token",
        fetch,
        lambda value: should_not_run(),
        should_not_run,
        should_not_run,
    ).run()
    assert run.failed == 1
