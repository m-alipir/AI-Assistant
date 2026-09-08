from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from app.email.core import EmailMessage, InMemoryGmailSync, TokenCipher


def message(message_id: str, sender: str, subject: str, now: datetime) -> EmailMessage:
    return EmailMessage(
        message_id=message_id, sender=sender, subject=subject, body="private", received_at=now
    )


def test_m5_fixture_rules_and_independent_account_checkpoints() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    sync = InMemoryGmailSync()
    first = sync.sync(
        "personal",
        [
            message("a", "jobs@linkedin.com", "Recommended jobs for you", now),
            message("b", "hr@amd.com", "Interview at AMD by 2026-09-08", now),
        ],
        "10",
        now,
    )
    second = sync.sync(
        "work", [message("c", "security@example.com", "Security sign-in alert", now)], "20", now
    )
    assert [item.classification for item in first] == ["recommendation", "application_update"]
    assert first[1].application_company == "Amd"
    assert first[1].deadline == datetime(2026, 9, 8, tzinfo=UTC)
    assert [item.classification for item in second] == ["security"]
    assert sync.accounts["personal"].history_id == "10"
    assert sync.accounts["work"].history_id == "20"


def test_m5_bounded_sync_raw_retention_and_protected_token() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    sync = InMemoryGmailSync()
    sync.sync(
        "a", [message("old", "hr@example.com", "Rejection", now - timedelta(days=8))], "2", now
    )
    sync.raw_bodies["expired"] = ("private", now - timedelta(days=8))
    assert "old" not in sync.raw_bodies
    assert sync.expire_raw_bodies(now) == 1
    cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
    assert cipher.reveal(cipher.protect("refresh-token")) == "refresh-token"


def test_refresh_token_cipher_rejects_wrong_key_and_tampering() -> None:
    cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
    protected = cipher.protect("refresh-token")

    with pytest.raises(ValueError, match="cannot be decrypted"):
        TokenCipher(Fernet.generate_key().decode("ascii")).reveal(protected)
    with pytest.raises(ValueError, match="cannot be decrypted"):
        cipher.reveal(protected[:-1] + ("A" if protected[-1] != "A" else "B"))


def test_refresh_token_cipher_rejects_invalid_key_format() -> None:
    with pytest.raises(ValueError, match="Fernet key"):
        TokenCipher("not-a-fernet-key")
