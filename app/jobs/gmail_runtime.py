"""Gmail job wiring that keeps credentials and message bodies outside persistence/logging."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.briefing.core import BriefingItem
from app.email.core import EmailClassification, EmailMessage, classify
from app.email.gmail_api import GmailBatch

FetchMessages = Callable[[], Awaitable[list[EmailMessage]]]


@dataclass(frozen=True)
class GmailAccountRecord:
    account_id: str
    encrypted_refresh_token: str
    history_id: str | None


FetchAccount = Callable[[GmailAccountRecord, str], Awaitable[GmailBatch]]
KnownMessage = Callable[[str], Awaitable[bool]]
PersistClassification = Callable[[str, EmailClassification], Awaitable[None]]
UpdateCheckpoint = Callable[[str, str | None, datetime], Awaitable[None]]
DecryptToken = Callable[[str], str]


@dataclass
class GmailRun:
    fetched: int = 0
    muted: int = 0
    relevant: int = 0
    processed: int = 0
    duplicates: int = 0
    failed: int = 0
    account_access_errors: int = 0
    classification_errors: int = 0
    checkpoint_errors: int = 0
    action_items: list[BriefingItem] = field(default_factory=list)

    def response(self, configured: bool) -> dict[str, object]:
        return {
            "gmail": {
                "status": "ready" if configured else "not_configured",
                "fetched": self.fetched,
                "muted": self.muted,
                "relevant": self.relevant,
                "action_items": len(self.action_items),
                "processed": self.processed,
                "duplicates": self.duplicates,
                "failed": self.failed,
                "failure_categories": {
                    "account_access_error": self.account_access_errors,
                    "classification_error": self.classification_errors,
                    "checkpoint_error": self.checkpoint_errors,
                },
            }
        }


class GmailRuntimeJob:
    """Run bounded account syncs independently so a Gmail failure cannot stop RSS."""

    def __init__(
        self,
        accounts: Callable[[], Awaitable[list[GmailAccountRecord]]],
        decrypt_token: DecryptToken,
        fetch_account: FetchAccount,
        known_message: KnownMessage,
        persist_classification: PersistClassification,
        update_checkpoint: UpdateCheckpoint,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._accounts = accounts
        self._decrypt_token = decrypt_token
        self._fetch_account = fetch_account
        self._known_message = known_message
        self._persist_classification = persist_classification
        self._update_checkpoint = update_checkpoint
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self) -> GmailRun:
        run = GmailRun()
        try:
            accounts = await self._accounts()
        except Exception:
            run.failed += 1
            run.account_access_errors += 1
            return run
        for account in accounts:
            try:
                refresh_token = self._decrypt_token(account.encrypted_refresh_token)
                batch = await self._fetch_account(account, refresh_token)
            except Exception:
                run.failed += 1
                run.account_access_errors += 1
                continue
            account_failed = False
            run.fetched += len(batch.messages)
            for message in batch.messages:
                source_item_id = f"gmail:{account.account_id}:{message.message_id}"
                try:
                    if await self._known_message(source_item_id):
                        run.duplicates += 1
                        continue
                    classification = classify(message)
                    await self._persist_classification(source_item_id, classification)
                    if classification.classification in {"recommendation", "newsletter"}:
                        run.muted += 1
                    else:
                        run.processed += 1
                        if classification.classification in _ACTIONABLE_CLASSES:
                            run.relevant += 1
                            run.action_items.append(
                                _briefing_item(source_item_id, message, classification)
                            )
                except Exception:
                    account_failed = True
                    run.failed += 1
                    run.classification_errors += 1
            if not account_failed:
                try:
                    await self._update_checkpoint(
                        account.account_id, batch.history_id, self._clock()
                    )
                except Exception:
                    run.failed += 1
                    run.checkpoint_errors += 1
        return run


_ACTIONABLE_CLASSES = {
    "action_required",
    "application_update",
    "recruiter",
    "security",
    "transactional",
}


def _briefing_item(
    source_item_id: str, message: EmailMessage, classification: EmailClassification
) -> BriefingItem:
    return BriefingItem(
        event_id=source_item_id,
        # A retained action summary is enough for the briefing; do not echo an email subject into
        # another persistence/recovery path.
        title=classification.action_summary or "Gmail action item",
        source_urls=[],
        importance=8 if classification.classification in {"security", "action_required"} else 6,
        interest=0,
        global_importance=0,
        actionable=True,
        source_type="gmail",
    )


async def sync_gmail(
    enabled: bool, configured: bool, fetch: FetchMessages | None = None
) -> dict[str, object]:
    """Compatibility helper for fixture tests; production uses ``GmailRuntimeJob``."""
    run = GmailRun()
    if not enabled or not configured or fetch is None:
        return run.response(configured)
    try:
        messages = await fetch()
    except Exception:
        run.failed += 1
        run.account_access_errors += 1
        return run.response(configured)
    run.fetched = len(messages)
    for message in messages:
        result = classify(message)
        if result.classification in {"recommendation", "newsletter"}:
            run.muted += 1
            continue
        run.processed += 1
        if result.classification in _ACTIONABLE_CLASSES:
            run.relevant += 1
            run.action_items.append(_briefing_item(message.message_id, message, result))
    return run.response(configured)
