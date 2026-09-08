"""Bounded, read-only email classification without live Gmail access in tests."""

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict

from app.llm.core import Router

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str
    history_id: str | None = None
    last_sync_at: datetime | None = None


class EmailMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    sender: str
    subject: str
    body: str
    received_at: datetime


class EmailClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    classification: Literal[
        "action_required",
        "application_update",
        "recruiter",
        "security",
        "transactional",
        "recommendation",
        "newsletter",
        "personal",
        "other",
    ]
    action_summary: str | None = None
    deadline: datetime | None = None
    application_company: str | None = None


class TokenCipher:
    """Encrypt OAuth refresh tokens with authenticated Fernet encryption."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("APP_ENCRYPTION_KEY is required for OAuth token storage")
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as error:
            raise ValueError(
                "APP_ENCRYPTION_KEY must be a valid URL-safe base64 Fernet key"
            ) from error

    def protect(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def reveal(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as error:
            raise ValueError(
                "stored Gmail token cannot be decrypted; reconnect the account"
            ) from error


def classify(message: EmailMessage) -> EmailClassification:
    """Deterministic sender/subject rules run before any optional cheap-model fallback."""
    text = f"{message.sender} {message.subject}".casefold()
    deadline_match = re.search(r"(?:by|deadline)\s+(\d{4}-\d{2}-\d{2})", text)
    deadline = (
        datetime.fromisoformat(deadline_match.group(1)).replace(tzinfo=UTC)
        if deadline_match
        else None
    )
    company_match = re.search(r"\bat\s+([a-z0-9][a-z0-9 .&-]{1,40})", message.subject.casefold())
    company = company_match.group(1).split(" by ", 1)[0].strip().title() if company_match else None
    if "linkedin" in text and ("recommended" in text or "jobs for you" in text):
        return EmailClassification(classification="recommendation")
    if any(word in text for word in ("security", "password", "sign-in", "login")):
        return EmailClassification(
            classification="security", action_summary="Review account security alert."
        )
    if any(word in text for word in ("invoice", "receipt", "payment", "transaction")):
        return EmailClassification(classification="transactional")
    if "recruiter" in text:
        return EmailClassification(classification="recruiter", action_summary="Recruiter message.")
    if any(word in text for word in ("urgent", "action required", "respond by")):
        return EmailClassification(
            classification="action_required", action_summary="Review required action."
        )
    if "interview" in text:
        return EmailClassification(
            classification="application_update",
            action_summary="Interview update.",
            deadline=deadline,
            application_company=company,
        )
    if any(word in text for word in ("rejection", "not moving forward", "application update")):
        return EmailClassification(
            classification="application_update",
            action_summary="Application status update.",
            application_company=company,
        )
    if "newsletter" in text:
        return EmailClassification(classification="newsletter")
    if any(word in text for word in ("mom", "family", "personal")):
        return EmailClassification(classification="personal")
    return EmailClassification(classification="other")


async def classify_unknown(message: EmailMessage, router: Router) -> EmailClassification:
    """Use the configured cheap role only after deterministic rules leave a message unknown."""
    deterministic = classify(message)
    if deterministic.classification != "other":
        return deterministic
    return await router.structured(
        "gatekeeper",
        f"Classify email metadata only. SENDER: {message.sender}\nSUBJECT: {message.subject}",
        message.message_id,
        EmailClassification,
        "email-v1",
        "v1",
        email_action=True,
    )


class InMemoryGmailSync:
    """Independent account checkpoints and bounded initial/recovery sync for fixture clients."""

    def __init__(self) -> None:
        self.accounts: dict[str, GmailAccount] = {}
        self.raw_bodies: dict[str, tuple[str, datetime]] = {}

    def sync(
        self, account_id: str, messages: list[EmailMessage], history_id: str, now: datetime
    ) -> list[EmailClassification]:
        account = self.accounts.get(account_id, GmailAccount(account_id=account_id))
        cutoff = now.astimezone(UTC) - timedelta(hours=48)
        selected = [
            message for message in messages if message.received_at.astimezone(UTC) >= cutoff
        ]
        self.accounts[account_id] = account.model_copy(
            update={"history_id": history_id, "last_sync_at": now}
        )
        for message in selected:
            self.raw_bodies[message.message_id] = (message.body, message.received_at)
        return [classify(message) for message in selected]

    def expire_raw_bodies(self, now: datetime) -> int:
        cutoff = now.astimezone(UTC) - timedelta(days=7)
        expired = [
            message_id for message_id, (_, received) in self.raw_bodies.items() if received < cutoff
        ]
        for message_id in expired:
            del self.raw_bodies[message_id]
        return len(expired)
