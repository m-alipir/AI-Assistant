"""Offline Telegram boundary regressions; no Bot API or provider call is permitted."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings
from app.config.source_repository import (
    EnabledSourceDeleteBlocked,
    ManagedSourceCreate,
    SourceAlreadyExists,
    SourceNotFound,
)
from app.notifications.core import Notification
from app.telegram.api import router
from app.telegram.core import (
    TelegramBotClient,
    TelegramDeliveryError,
    TelegramMessage,
    split_plain_text,
)
from app.telegram.poller import TelegramPoller
from app.telegram.service import Actor, TelegramUpdate, TelegramWebhookHandler, _search_text
from app.telegram.source_categories import (
    dispatch_pending_source_category_questions,
    send_source_category_question,
    source_category_question,
    source_category_question_was_delivered,
    telegram_delivery_channel,
)

TOKEN = "123456789:telegram-token-for-offline-tests"
SECRET = "telegram_webhook_secret_with_adequate_entropy_123"


def _managed_source_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "source-1",
        "kind": "rss",
        "name": "Fixture Feed",
        "canonical_endpoint": "https://example.test/feed.xml",
        "stream": "tech",
        "enabled": False,
        "priority": 0,
        "category": None,
        "language": None,
        "freshness_hours": None,
        "health_status": "healthy",
        "last_error_category": None,
    }
    row.update(overrides)
    return row


class _SourceRepository:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = {str(row["id"]): dict(row) for row in rows or []}
        self.created = 0

    async def list(self) -> list[dict[str, object]]:
        return list(self.rows.values())

    async def get(self, source_id: str) -> dict[str, object] | None:
        row = self.rows.get(source_id)
        return dict(row) if row is not None else None

    async def create(self, source: ManagedSourceCreate) -> dict[str, object]:
        if any(
            row["kind"] == source.kind and row["canonical_endpoint"] == source.endpoint
            for row in self.rows.values()
        ):
            raise SourceAlreadyExists
        self.created += 1
        row = _managed_source_row(
            id=f"source-{self.created}",
            kind=source.kind,
            name=source.name,
            canonical_endpoint=source.endpoint,
            enabled=source.enabled,
            stream=source.stream.value,
            category=source.category,
        )
        self.rows[str(row["id"])] = row
        return dict(row)

    async def set_category_if_missing(self, source_id: str, category: str) -> str:
        row = self.rows.get(source_id)
        if row is None:
            return "not_found"
        if row["category"] is not None:
            return "already_set"
        row["category"] = category
        return "updated"

    async def set_enabled(self, source_id: str, enabled: bool) -> bool:
        row = self.rows.get(source_id)
        if row is None:
            return False
        row["enabled"] = enabled
        return True

    async def delete(self, source_id: str) -> None:
        row = self.rows.get(source_id)
        if row is None:
            raise SourceNotFound
        if row["enabled"]:
            raise EnabledSourceDeleteBlocked
        del self.rows[source_id]


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "telegram_enabled": True,
        "telegram_bot_token": TOKEN,
        "telegram_webhook_secret": SECRET,
        "telegram_webhook_url": "https://testserver/integrations/telegram/webhook",
        "telegram_allowed_actor_pairs": "42:42",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_telegram_is_disabled_by_default_and_requires_exact_actor_pairs() -> None:
    assert not Settings(_env_file=None).telegram_enabled
    with pytest.raises(ValidationError, match="TELEGRAM_ALLOWED_ACTOR_PAIRS"):
        _settings(telegram_allowed_actor_pairs="")
    with pytest.raises(ValidationError, match="user_id:chat_id"):
        _settings(telegram_allowed_actor_pairs="not-an-id")
    with pytest.raises(ValidationError, match="NOTIFICATION_CHAT_IDS"):
        _settings(telegram_notification_chat_ids="99")


def test_production_telegram_rejects_inline_secrets() -> None:
    with pytest.raises(ValidationError, match="production Telegram secrets"):
        Settings(
            _env_file=None,
            app_env="production",
            admin_auth_enabled=True,
            admin_username="operator",
            admin_password="adequately-long-production-password",
            admin_public_origin="https://intelligence.example.test",
            allowed_hosts="intelligence.example.test",
            allow_private_source_urls=False,
            allow_insecure_source_urls=False,
            telegram_enabled=True,
            telegram_bot_token=TOKEN,
            telegram_webhook_secret=SECRET,
            telegram_webhook_url="https://intelligence.example.test/integrations/telegram/webhook",
            telegram_allowed_actor_pairs="42:42",
        )


def test_polling_mode_requires_no_webhook_configuration() -> None:
    settings = Settings(
        _env_file=None,
        telegram_enabled=True,
        telegram_mode="polling",
        telegram_bot_token=TOKEN,
        telegram_allowed_actor_pairs="42:42",
    )

    assert settings.telegram_mode == "polling"


@pytest.mark.asyncio
async def test_telegram_client_retries_only_safe_transient_failures_and_never_uses_markup() -> None:
    calls: list[dict[str, object]] = []

    async def transport(_: str, payload: dict[str, object]) -> tuple[int, bool, int | None]:
        calls.append(payload)
        return (429, False, 0) if len(calls) == 1 else (200, True, None)

    client = TelegramBotClient(TOKEN, timeout_seconds=1, retries=1, transport=transport)
    await client.send_message(42, TelegramMessage("Merhaba https://example.test/source"))

    assert len(calls) == 2
    assert calls[-1]["disable_web_page_preview"] is True
    assert calls[-1]["protect_content"] is True
    assert "parse_mode" not in calls[-1]


@pytest.mark.asyncio
async def test_telegram_client_rejects_provider_error_without_exposing_body() -> None:
    async def transport(_: str, __: dict[str, object]) -> tuple[int, bool, int | None]:
        return 400, False, None

    client = TelegramBotClient(TOKEN, timeout_seconds=1, retries=1, transport=transport)
    with pytest.raises(TelegramDeliveryError, match="telegram_api_error"):
        await client.send_message(42, TelegramMessage("Merhaba"))


@pytest.mark.asyncio
async def test_callback_answer_retries_transient_failure_and_bounds_timeout() -> None:
    calls: list[str] = []

    async def transient(method: str, _: dict[str, object]) -> tuple[int, bool, int | None]:
        calls.append(method)
        return (500, False, None) if len(calls) == 1 else (200, True, None)

    client = TelegramBotClient(TOKEN, timeout_seconds=1, retries=1, transport=transient)
    await client.answer_callback_query("callback-1", "Geri bildirim kaydedildi.")
    assert calls == ["answerCallbackQuery", "answerCallbackQuery"]

    async def timeout(_: str, __: dict[str, object]) -> tuple[int, bool, int | None]:
        raise httpx.ReadTimeout("fixture timeout")

    timeout_client = TelegramBotClient(TOKEN, timeout_seconds=1, retries=0, transport=timeout)
    with pytest.raises(TelegramDeliveryError, match="telegram_transport_error"):
        await timeout_client.answer_callback_query("callback-2", "Bu buton artık geçerli değil.")


@pytest.mark.asyncio
async def test_polling_client_deletes_webhook_and_requests_bounded_updates() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    async def transport(method: str, payload: dict[str, object]) -> tuple[int, bool, int | None]:
        calls.append((method, payload))
        return 200, True, None

    async def poll_transport(
        method: str, payload: dict[str, object]
    ) -> tuple[int, bool, int | None, list[dict[str, object]] | None]:
        calls.append((method, payload))
        return 200, True, None, [{"update_id": 7}]

    client = TelegramBotClient(
        TOKEN,
        timeout_seconds=1,
        retries=0,
        transport=transport,
        polling_transport=poll_transport,
    )
    await client.delete_webhook()
    updates = await client.get_updates(offset=4, timeout_seconds=30, limit=25)

    assert calls == [
        ("deleteWebhook", {"drop_pending_updates": False}),
        (
            "getUpdates",
            {
                "offset": 4,
                "timeout": 30,
                "limit": 25,
                "allowed_updates": ["message", "callback_query"],
            },
        ),
    ]
    assert updates == [{"update_id": 7}]


def test_plain_text_split_preserves_literal_content_without_format_mode() -> None:
    parts = split_plain_text("*not markdown*\n" + "x" * 4_100)
    assert len(parts) == 2
    assert parts[0].startswith("*not markdown*")
    assert all(len(part) <= 4_000 for part in parts)


@pytest.mark.asyncio
async def test_telegram_control_commands_reuse_injected_runtime_callbacks() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("control command must not call a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)

    async def sources() -> str:
        return "Takip edilen kaynaklar\n- rss-example · RSS · Example (aktif)"

    async def add_source(kind: str, endpoint: str, name: str, chat_id: int) -> str:
        assert (kind, endpoint, name) == ("rss", "https://example.test/feed", "Example")
        assert chat_id == 42
        return "Example eklendi ve aktif edildi."

    async def set_interest(subject: str, enabled: bool) -> str:
        assert (subject, enabled) == ("GPU", True)
        return "GPU ilgi alanlarına eklendi."

    handler._sources = sources
    handler._add_source = add_source
    handler._set_interest = set_interest
    await handler.process_update(TelegramUpdate.model_validate(_payload(60, text="/kaynaklar")))
    await handler.process_update(
        TelegramUpdate.model_validate(
            _payload(61, text="/kaynak_ekle rss https://example.test/feed Example")
        )
    )
    await handler.process_update(TelegramUpdate.model_validate(_payload(62, text="/ilgi_ekle GPU")))
    await handler.process_update(TelegramUpdate.model_validate(_payload(63, text="/yardim")))

    messages = [str(call["text"]) for call in sent if call["method"] == "sendMessage"]
    assert messages[0].startswith("Takip edilen kaynaklar")
    assert messages[1] == "Example eklendi ve aktif edildi."
    assert messages[2] == "GPU ilgi alanlarına eklendi."
    assert "/kaynak_ekle rss" in messages[3]

@pytest.mark.asyncio
async def test_telegram_source_commands_complete_chat_first_safe_crud() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("source commands must not invoke a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, finished = _handler(ask=ask, claim=claim)
    repository = _SourceRepository()
    handler._source_repository = repository  # type: ignore[assignment]

    commands = [
        "/kaynak_ekle rss HTTPS://Example.Test:443/feed.xml#ignored Example Feed",
        "/kaynaklar",
        "/kaynak source-1",
        "/kaynak_ac source-1",
        "/kaynak_sil source-1",
        "/kaynak_kapat source-1",
        "/kaynak_ac source-1",
        "/kaynak_kapat source-1",
        "/kaynak_sil source-1",
    ]
    for update_id, command in enumerate(commands, start=60):
        await handler.process_update(
            TelegramUpdate.model_validate(_payload(update_id, text=command))
        )

    messages = [str(call["text"]) for call in sent if call["method"] == "sendMessage"]
    assert messages[0] == "Example Feed eklendi ve pasif bırakıldı. Kimlik: source-1"
    assert "source-1 · rss · Example Feed (pasif, sağlıklı)" in messages[1]
    assert "Adres: https://example.test/feed.xml" in messages[2]
    assert messages[3:] == [
        "Kaynak etkinleştirildi.",
        "Aktif kaynak silinemez. Önce /kaynak_kapat <kaynak-kimliği> kullanın.",
        "Kaynak devre dışı bırakıldı.",
        "Kaynak etkinleştirildi.",
        "Kaynak devre dışı bırakıldı.",
        "Kaynak silindi.",
    ]
    assert repository.rows == {}
    assert finished == [(update_id, "completed") for update_id in range(60, 69)]


@pytest.mark.asyncio
async def test_telegram_source_failures_have_concise_turkish_messages() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("source commands must not invoke a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)

    async def sources() -> str:
        return "Takip edilen kaynaklar\n- rss-example · RSS · Example (aktif)"

    async def add_source(kind: str, endpoint: str, name: str, chat_id: int) -> str:
        assert (kind, endpoint, name) == ("rss", "https://example.test/feed", "Example")
        assert chat_id == 42
        return "Example eklendi ve aktif edildi."

    async def set_interest(subject: str, enabled: bool) -> str:
        assert (subject, enabled) == ("GPU", True)
        return "GPU ilgi alanlarına eklendi."

    handler._sources = sources
    handler._add_source = add_source
    handler._set_interest = set_interest
    await handler.process_update(TelegramUpdate.model_validate(_payload(60, text="/kaynaklar")))
    await handler.process_update(
        TelegramUpdate.model_validate(
            _payload(61, text="/kaynak_ekle rss https://example.test/feed Example")
        )
    )
    await handler.process_update(TelegramUpdate.model_validate(_payload(62, text="/ilgi_ekle GPU")))
    await handler.process_update(TelegramUpdate.model_validate(_payload(63, text="/yardim")))

    messages = [str(call["text"]) for call in sent if call["method"] == "sendMessage"]
    assert messages[0].startswith("Takip edilen kaynaklar")
    assert messages[1] == "Example eklendi ve aktif edildi."
    assert messages[2] == "GPU ilgi alanlarına eklendi."
    assert "/kaynak_ekle rss" in messages[3]
    handler._sources = None
    handler._add_source = None
    handler._disable_source = None
    handler._source_repository = _SourceRepository(  # type: ignore[assignment]
        [_managed_source_row(id="existing", enabled=True)]
    )
    commands = [
        "/kaynak_ekle rss not-a-url Invalid",
        "/kaynak_ekle rss https://example.test/feed.xml Duplicate",
        "/kaynak missing",
        "/kaynak_sil existing",
    ]
    for update_id, command in enumerate(commands, start=80):
        await handler.process_update(
            TelegramUpdate.model_validate(_payload(update_id, text=command))
        )
    handler._source_repository = None
    await handler.process_update(TelegramUpdate.model_validate(_payload(84, text="/kaynaklar")))

    class UnavailableRepository:
        async def list(self) -> list[dict[str, object]]:
            raise RuntimeError("database details must not reach Telegram")

    handler._source_repository = UnavailableRepository()  # type: ignore[assignment]
    await handler.process_update(TelegramUpdate.model_validate(_payload(85, text="/kaynaklar")))

    messages = [str(call["text"]) for call in sent if call["method"] == "sendMessage"]
    assert messages[4:] == [
        "Kaynak bilgisi geçersiz. Geçerli bir RSS/Atom adresi veya YouTube kanal kimliği yazın.",
        "Bu kaynak zaten takip ediliyor.",
        "Kaynak bulunamadı. /kaynaklar ile kimliği kontrol edin.",
        "Aktif kaynak silinemez. Önce /kaynak_kapat <kaynak-kimliği> kullanın.",
        "Kaynak yönetimi şu anda kullanılamıyor.",
        "Kaynak yönetimi şu anda kullanılamıyor.",
    ]


def test_search_output_only_keeps_safe_https_provenance_links() -> None:
    text = _search_text(
        {
            "status": "ok",
            "answer_tr": "Yanıt",
            "events": [
                {
                    "title": "Olay",
                    "verified_facts": [],
                    "source_links": [
                        "https://example.test/source",
                        "http://example.test/plain-http",
                        "https://127.0.0.1/private",
                    ],
                }
            ],
        },
        "Arama",
    )

    assert "https://example.test/source" in text
    assert "plain-http" not in text
    assert "127.0.0.1" not in text


@pytest.mark.asyncio
async def test_proactive_briefing_reuses_the_ozet_renderer_and_calibration_buttons() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("proactive delivery must not call a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)

    async def tokens(
        actor: Actor,
        briefing_id: str,
        event_ids: list[str],
        subjects: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return {event_id: "a" * 20 for event_id in event_ids}

    handler._create_feedback_tokens = tokens  # type: ignore[method-assign]
    await handler.send_briefing(
        42,
        {
            "id": "briefing-1",
            "created_at": "2026-09-23T09:30:00+03:00",
            "items": [
                {
                    "event_id": "event-1",
                    "section": "For You",
                    "title": "GPU announcement",
                    "summary": "A compact summary.",
                    "source_links": ["https://example.test/story"],
                }
            ],
        },
        [{"event_id": "event-1", "subject": "GPU"}],
    )

    messages = [call for call in sent if call["method"] == "sendMessage"]
    assert any("GPU announcement" in str(call["text"]) for call in messages)
    assert any(
        "GPU hakkındaki haberler ve gelişmeler ilginizi çekiyor mu?" in str(call["text"])
        for call in messages
    )
    assert any("f:" in str(call.get("reply_markup")) for call in messages)


@pytest.mark.asyncio
async def test_late_proactive_briefing_header_explains_delivery_delay() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("proactive delivery must not call a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)

    async def tokens(
        actor: Actor,
        briefing_id: str,
        event_ids: list[str],
        subjects: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return {}

    handler._create_feedback_tokens = tokens  # type: ignore[method-assign]
    await handler.send_briefing(
        42,
        {"id": "briefing-1", "created_at": "2026-09-25T11:08:34Z", "items": []},
        delivery_note="Hedef 14:00 idi; 8 dk 34 sn gecikme.",
    )

    first_message = next(call for call in sent if call["method"] == "sendMessage")
    assert first_message["text"] == (
        "Günlük Özet · 25.09.2026 14:08 · Hedef 14:00 idi; 8 dk 34 sn gecikme."
    )


@pytest.mark.asyncio
async def test_briefing_delivery_is_concise_turkish_ordered_and_keeps_item_feedback() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("briefing delivery must not call a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)

    async def tokens(
        actor: Actor,
        briefing_id: str,
        event_ids: list[str],
        subjects: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return {event_id: "b" * 20 for event_id in event_ids}

    handler._create_feedback_tokens = tokens  # type: ignore[method-assign]
    await handler.send_briefing(
        42,
        {
            "id": "briefing-2",
            "created_at": "2026-09-25T11:00:00+00:00",
            "items": [
                {
                    "event_id": "world-event",
                    "section": "World in Brief",
                    "title": "Waymo expands its robotaxi fleet",
                    "summary": "Waymo is expanding its driverless taxi service to new cities.",
                    "what_changed": "Waymo expanded its driverless taxi service to new cities.",
                    "why_important": "It gives more riders access to autonomous transport.",
                    "source_links": ["https://example.test/waymo"],
                },
                {
                    "event_id": "tech-event",
                    "section": "Tech & Industry",
                    "title": "Google Photos adds AI collages",
                    "summary": "Google Photos is making AI collages available on Android and iOS.",
                    "what_changed": "AI collages are now available on Android and iOS.",
                    "why_important": "The feature is no longer limited to a small test group.",
                    "published_at": "2026-09-24T11:30:00+00:00",
                    "source_links": [
                        "http://example.test/unsafe",
                        "https://127.0.0.1/private",
                        "https://example.test/photos",
                    ],
                },
                {
                    "event_id": "you-event",
                    "section": "For You",
                    "title": "NVIDIA expands its developer tools",
                    "summary": "NVIDIA added new tools for developers.",
                    "source_links": ["https://example.test/nvidia"],
                },
                {
                    "event_id": "watch-event",
                    "section": "Worth Watching",
                    "title": "A useful robotics interview",
                    "summary": "The interview explains recent robotics work.",
                    "source_links": ["https://example.test/video"],
                },
                {
                    "event_id": "action-event",
                    "section": "Action Required",
                    "title": "Reply to the recruiter",
                    "summary": "The recruiter requested a response by Friday.",
                    "email_action": {"classification": "recruiter"},
                },
            ],
        },
        [{"event_id": "tech-event", "subject": "Google Photos"}],
    )

    messages = [call for call in sent if call["method"] == "sendMessage"]
    assert messages[0]["text"] == "Günlük Özet · 25.09.2026 14:00"
    item_messages = messages[1:6]
    assert [str(call["text"]).splitlines()[0] for call in item_messages] == [
        "Takip Etmen Gerekenler",
        "Senin İçin",
        "Teknoloji ve Endüstri",
        "Dünyada Neler Oldu?",
        "İzlemeye Değer",
    ]
    tech_text = str(item_messages[2]["text"])
    assert "Google Photos adds AI collages" in tech_text
    assert "Google Photos is making AI collages available on Android and iOS." in tech_text
    assert "Neden önemli: The feature is no longer limited to a small test group." in tech_text
    assert "AI collages are now available on Android and iOS." not in tech_text
    assert "Yayın: 24.09.2026 14:30" in tech_text
    assert "https://example.test/photos" in tech_text
    assert "http://example.test/unsafe" not in tech_text
    assert "https://127.0.0.1/private" not in tech_text
    assert item_messages[0].get("reply_markup") is None
    assert all(call.get("reply_markup") for call in item_messages[1:])
    assert "Google Photos hakkındaki haberler ve gelişmeler ilginizi çekiyor mu?" in str(
        messages[-1]["text"]
    )


def test_source_category_question_is_stable_chat_scoped_and_endpoint_free() -> None:
    first = source_category_question("source-1")
    duplicate = source_category_question("source-1")
    other = source_category_question("source-2")

    assert first.idempotency_key == duplicate.idempotency_key
    assert first.idempotency_key != other.idempotency_key
    assert first.kind.value == "source_category_question"
    assert "source-1" in first.body
    assert "https://" not in first.body
    assert telegram_delivery_channel(42) == telegram_delivery_channel(42)
    assert telegram_delivery_channel(42) != telegram_delivery_channel(43)


@pytest.mark.asyncio
async def test_pending_category_survives_disabled_telegram_then_delivers_once() -> None:
    receipts: dict[tuple[str, str], dict[str, object]] = {}
    sent: list[tuple[int, str]] = []

    class Result:
        def __init__(self, value: object = None) -> None:
            self.value = value

        def mappings(self) -> "Result":
            return self

        def one_or_none(self) -> object:
            return self.value

        def scalar_one_or_none(self) -> object:
            return self.value

    class Session:
        async def execute(self, statement: object, params: dict[str, object]) -> Result:
            query = str(statement)
            receipt_key = (str(params["channel"]), str(params["key"]))
            if query.startswith("SELECT status, attempts"):
                return Result(receipts.get(receipt_key))
            if query.startswith("INSERT INTO notification_deliveries"):
                if receipt_key not in receipts:
                    receipts[receipt_key] = {
                        "status": "pending",
                        "attempts": 1,
                        "age_seconds": 0,
                    }
                    return Result(receipt_key[1])
                if receipts[receipt_key]["status"] == "failed":
                    receipts[receipt_key]["status"] = "pending"
                    receipts[receipt_key]["attempts"] = int(receipts[receipt_key]["attempts"]) + 1
                    receipts[receipt_key]["age_seconds"] = 0
                    return Result(receipt_key[1])
                return Result()
            if "SET status = 'delivered'" in query:
                receipts[receipt_key]["status"] = "delivered"
            elif "SET status = 'failed'" in query:
                receipts[receipt_key]["status"] = "failed"
            return Result()

        async def scalar(self, statement: object, params: dict[str, object]) -> str | None:
            value = receipts.get((str(params["channel"]), str(params["key"])))
            return str(value["status"]) if value is not None else None

    class SessionContext:
        async def __aenter__(self) -> Session:
            return Session()

        async def __aexit__(self, *_: object) -> None:
            return None

    class Sessions:
        def begin(self) -> SessionContext:
            return SessionContext()

        def __call__(self) -> SessionContext:
            return SessionContext()

    class Bot:
        async def send_notification(self, chat_id: int, notification: Notification) -> None:
            sent.append((chat_id, notification.body))

    class PendingRepository:
        async def list_pending_categories(
            self, *, limit: int, offset: int
        ) -> list[dict[str, object]]:
            assert (limit, offset) == (100, 0)
            return [{"id": "source-1", "category": None}]

    repository = PendingRepository()
    disabled = _settings(telegram_enabled=False, telegram_allowed_actor_pairs="42:42")
    disabled_results, disabled_offset = await dispatch_pending_source_category_questions(
        repository, Sessions(), disabled, Bot()
    )  # type: ignore[arg-type]
    assert disabled_results == []
    assert disabled_offset == 0
    assert sent == []

    settings = _settings(telegram_allowed_actor_pairs="42:42")
    first, next_offset = await dispatch_pending_source_category_questions(
        repository, Sessions(), settings, Bot()
    )  # type: ignore[arg-type]
    duplicate = await send_source_category_question(
        Sessions(), settings, Bot(), "source-1"
    )  # type: ignore[arg-type]

    assert [result.status for result in first] == ["delivered"]
    assert next_offset == 1
    assert duplicate.status == "duplicate_skipped"
    assert await source_category_question_was_delivered(Sessions(), "source-1", 42)  # type: ignore[arg-type]
    assert not await source_category_question_was_delivered(Sessions(), "source-1", 43)  # type: ignore[arg-type]
    assert len(sent) == 1
    assert sent[0][0] == 42
    assert "https://" not in sent[0][1]


@pytest.mark.asyncio
async def test_telegram_source_category_answer_is_explicit_targeted_and_non_destructive() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("category handling must never call a model")

    async def claim(*_: object) -> bool:
        return True

    repository = _SourceRepository(
        [
            _managed_source_row(id="pending", enabled=False),
            _managed_source_row(id="assigned", enabled=True, category="Technology"),
        ]
    )
    handler, sent, _ = _handler(ask=ask, claim=claim)
    handler._source_repository = repository  # type: ignore[assignment]
    handler._settings = _settings(
        telegram_allowed_actor_pairs="42:42,43:43",
        telegram_source_operator_chat_id=42,
    )
    answered: list[tuple[str, int]] = []

    async def question_delivered(source_id: str, chat_id: int) -> bool:
        answered.append((source_id, chat_id))
        return (source_id, chat_id) in {
            ("pending", 42),
            ("assigned", 42),
            ("stale", 42),
        }

    handler._source_category_question_delivered = question_delivered
    commands = [
        (101, 42, 42, "/kaynak_kategori pending Technology > Artificial Intelligence"),
        (102, 42, 42, "/kaynak_kategori pending Science"),
        (103, 42, 42, "/kaynak_kategori stale Science"),
        (104, 42, 42, "/kaynak_kategori assigned Research"),
        (105, 43, 43, "/kaynak_kategori pending Finance"),
        (106, 42, 42, "/kaynak_kategori pending " + "x" * 129),
        (107, 99, 42, "/kaynak_kategori pending Finance"),
    ]
    for update_id, user_id, chat_id, command in commands:
        await handler.process_update(
            TelegramUpdate.model_validate(
                _payload(update_id, user_id=user_id, chat_id=chat_id, text=command)
            )
        )

    messages = [str(call["text"]) for call in sent if call["method"] == "sendMessage"]
    assert repository.rows["pending"]["category"] == "Technology > Artificial Intelligence"
    assert repository.rows["pending"]["enabled"] is False
    assert repository.rows["assigned"]["category"] == "Technology"
    assert answered == [
        ("pending", 42),
        ("pending", 42),
        ("stale", 42),
        ("assigned", 42),
        ("pending", 43),
    ]
    assert "Kategori kaydedildi" in messages[0]
    assert "zaten" in messages[1].casefold()
    assert "bulunamadı" in messages[2].casefold()
    assert "değiştirilmedi" in messages[3].casefold()
    assert "bu sohbet" in messages[4].casefold()
    assert "128" in messages[5]
    assert len(messages) == 6


@pytest.mark.asyncio
async def test_telegram_source_add_stays_disabled_and_queues_operator_category_question(
) -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("source management must never call a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, _ = _handler(ask=ask, claim=claim)
    repository = _SourceRepository()
    handler._source_repository = repository  # type: ignore[assignment]
    questions: list[str] = []

    async def queue_question(source_id: str) -> str:
        questions.append(source_id)
        return "delivered"

    handler._queue_source_category_question = queue_question
    await handler.process_update(
        TelegramUpdate.model_validate(
            _payload(108, text="/kaynak_ekle rss https://unknown.example.test/feed Unknown")
        )
    )

    row = repository.rows["source-1"]
    assert row["enabled"] is False
    assert row["category"] is None
    assert questions == ["source-1"]
    assert "pasif" in str(sent[0]["text"]).casefold()
    assert "https://unknown.example.test/feed" not in str(sent[0]["text"])


def _handler(
    *,
    ask: Callable[..., Awaitable[dict[str, object]]],
    claim: Callable[..., Awaitable[bool]],
) -> tuple[TelegramWebhookHandler, list[dict[str, object]], list[tuple[int, str]]]:
    sent: list[dict[str, object]] = []
    finished: list[tuple[int, str]] = []

    async def transport(method: str, payload: dict[str, object]) -> tuple[int, bool, int | None]:
        sent.append({"method": method, **payload})
        return 200, True, None

    async def latest() -> dict[str, object]:
        raise LookupError

    async def search(_: object) -> dict[str, object]:
        return {"status": "insufficient_sources", "answer_tr": "Yeterli kaynak bulunamadı."}

    async def status() -> dict[str, object]:
        return {"text": "Sistem: hazır"}

    handler = TelegramWebhookHandler(
        _settings(),
        None,  # type: ignore[arg-type]  # database calls are replaced in this route-isolation test.
        TelegramBotClient(TOKEN, timeout_seconds=1, retries=0, transport=transport),
        latest_briefing=latest,
        search=search,  # type: ignore[arg-type]
        ask=ask,  # type: ignore[arg-type]
        status=status,
    )
    handler._claim_update = claim  # type: ignore[method-assign]

    async def finish(update_id: int, category: str) -> None:
        finished.append((update_id, category))

    handler._finish_update = finish  # type: ignore[method-assign]
    return handler, sent, finished


def _client(handler: TelegramWebhookHandler) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.telegram_webhook_handler = handler
    return TestClient(app)


def _payload(
    update_id: int,
    *,
    user_id: int = 42,
    chat_id: int = 42,
    text: str = "/sor test",
) -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {"from": {"id": user_id}, "chat": {"id": chat_id}, "text": text},
    }


def _callback_payload(
    update_id: int,
    data: str,
    *,
    callback_id: str = "callback-fixture",
    user_id: int = 42,
    chat_id: int = 42,
) -> dict[str, object]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id},
            "message": {"from": {"id": 1}, "chat": {"id": chat_id}, "text": "Özet"},
            "data": data,
        },
    }


class _MappingResult:
    def __init__(self, row: dict[str, object] | None) -> None:
        self._row = row

    def mappings(self) -> "_MappingResult":
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self._row


@dataclass
class _FeedbackStore:
    tokens: dict[str, str]
    expired_tokens: set[str] | None = None
    feedback_events: int = 0
    completed_updates: list[int] | None = None

    def __post_init__(self) -> None:
        if self.expired_tokens is None:
            self.expired_tokens = set()
        if self.completed_updates is None:
            self.completed_updates = []

    def begin(self) -> "_FeedbackStore":
        return self

    async def __aenter__(self) -> "_FeedbackStore":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def execute(self, statement: object, parameters: object = None) -> _MappingResult:
        query = str(statement)
        values = parameters if isinstance(parameters, dict) else {}
        if "SELECT briefing_id, event_id" in query:
            token = str(values.get("token", ""))
            if token in self.expired_tokens or self.tokens.get(token) != values.get("actor_hash"):
                return _MappingResult(None)
            return _MappingResult(
                {"briefing_id": "briefing-1", "event_id": "event-1", "subject": None}
            )
        if "FROM briefing_items bi" in query:
            return _MappingResult(
                {"section": "For You", "canonical_title": "Fixture", "entities_json": "[]"}
            )
        if "INSERT INTO feedback_events" in query:
            self.feedback_events += 1
        elif "DELETE FROM telegram_feedback_tokens" in query:
            self.tokens.pop(str(values.get("token", "")), None)
        elif "UPDATE telegram_updates" in query:
            self.completed_updates.append(int(values["update_id"]))
        return _MappingResult(None)


def _callback_handler(
    store: _FeedbackStore,
    *,
    allowed_pairs: str = "42:42",
    operator_chat_id: int | None = None,
) -> tuple[TelegramWebhookHandler, list[dict[str, object]], list[tuple[int, str]]]:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("callback must not invoke a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, finished = _handler(ask=ask, claim=claim)
    handler._sessions = store  # type: ignore[assignment]
    handler._settings = _settings(
        telegram_allowed_actor_pairs=allowed_pairs,
        telegram_source_operator_chat_id=operator_chat_id,
    )
    return handler, sent, finished


def test_webhook_rejects_unauthorized_actor_before_claim_audit_or_model_work() -> None:
    calls = 0

    async def ask(_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"status": "ok", "answer_tr": "should not run"}

    async def claim(*_: object) -> bool:
        raise AssertionError("unauthorized request must not be persisted")

    handler, sent, finished = _handler(ask=ask, claim=claim)
    with _client(handler) as client:
        response = client.post(
            "/integrations/telegram/webhook",
            json=_payload(1, user_id=99),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )
    assert response.status_code == 200
    assert calls == 0
    assert sent == []
    assert finished == []


def test_exact_actor_pairs_do_not_create_a_cross_product_allow_list() -> None:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("cross-pair must not query")

    async def claim(*_: object) -> bool:
        raise AssertionError("cross-pair must not be persisted")

    handler, sent, _ = _handler(ask=ask, claim=claim)
    handler._settings = _settings(
        telegram_allowed_actor_pairs="42:42,43:43",
        telegram_source_operator_chat_id=42,
    )
    with _client(handler) as client:
        response = client.post(
            "/integrations/telegram/webhook",
            json=_payload(9, user_id=42, chat_id=43),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )
    assert response.status_code == 200
    assert sent == []


def test_duplicate_update_never_repeats_the_ask_model_call() -> None:
    claimed: set[int] = set()
    calls = 0

    async def ask(_: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "status": "ok",
            "answer_tr": "Kaynaklı yanıt.",
            "events": [{"title": "Olay", "verified_facts": [], "source_links": []}],
        }

    async def claim(update_id: int, *_: object) -> bool:
        if update_id in claimed:
            return False
        claimed.add(update_id)
        return True

    handler, sent, finished = _handler(ask=ask, claim=claim)
    with _client(handler) as client:
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        first = client.post("/integrations/telegram/webhook", json=_payload(2), headers=headers)
        second = client.post("/integrations/telegram/webhook", json=_payload(2), headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
    assert calls == 1
    assert len(sent) == 1
    assert finished == [(2, "completed")]


def test_webhook_requires_valid_secret_content_type_and_bounded_body() -> None:
    async def ask(_: object) -> dict[str, object]:
        return {"status": "ok", "answer_tr": "unused"}

    async def claim(*_: object) -> bool:
        return True

    handler, _, _ = _handler(ask=ask, claim=claim)
    with _client(handler) as client:
        assert client.post("/integrations/telegram/webhook", json=_payload(3)).status_code == 404
        assert client.post(
            "/integrations/telegram/webhook",
            content="{}",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": SECRET,
                "Content-Type": "text/plain",
            },
        ).status_code == 415
        assert client.post(
            "/integrations/telegram/webhook",
            content=b"x" * 9_000,
            headers={
                "X-Telegram-Bot-Api-Secret-Token": SECRET,
                "Content-Type": "application/json",
            },
        ).status_code == 413


def test_callback_success_acknowledges_and_records_feedback_once() -> None:
    token = "a" * 20
    store = _FeedbackStore({token: Actor(42, 42).pair_hash})
    handler, sent, finished = _callback_handler(store)
    with _client(handler) as client:
        response = client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(20, f"f:{token}:more", callback_id="callback-success"),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )

    assert response.status_code == 200
    assert store.feedback_events == 1
    assert token not in store.tokens
    assert store.completed_updates == [20]
    assert [call["method"] for call in sent] == ["answerCallbackQuery", "sendMessage"]
    assert sent[0] == {
        "method": "answerCallbackQuery",
        "callback_query_id": "callback-success",
        "text": "Geri bildirim kaydedildi.",
    }
    assert finished == [(20, "completed")]


@pytest.mark.parametrize(
    ("data", "user_id", "chat_id"),
    [
        ("malformed", 42, 42),
        (f"f:{'b' * 20}:less", 42, 42),
        (f"f:{'c' * 20}:more", 43, 43),
    ],
)
def test_invalid_expired_or_other_actor_callback_is_acknowledged_without_feedback(
    data: str, user_id: int, chat_id: int
) -> None:
    store = _FeedbackStore(
        {
            "b" * 20: Actor(42, 42).pair_hash,
            "c" * 20: Actor(42, 42).pair_hash,
        },
        expired_tokens={"b" * 20},
    )
    handler, sent, _ = _callback_handler(
        store, allowed_pairs="42:42,43:43", operator_chat_id=42
    )
    with _client(handler) as client:
        response = client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(30 + user_id, data, user_id=user_id, chat_id=chat_id),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )

    assert response.status_code == 200
    assert store.feedback_events == 0
    answer = next(call for call in sent if call["method"] == "answerCallbackQuery")
    assert answer["text"] == "Bu buton artık geçerli değil."


def test_second_callback_press_and_duplicate_update_do_not_repeat_feedback() -> None:
    token = "d" * 20
    store = _FeedbackStore({token: Actor(42, 42).pair_hash})
    seen_updates: set[int] = set()
    handler, sent, _ = _callback_handler(store)

    async def claim(update_id: int, *_: object) -> bool:
        if update_id in seen_updates:
            return False
        seen_updates.add(update_id)
        return True

    handler._claim_update = claim  # type: ignore[method-assign]
    headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
    with _client(handler) as client:
        assert client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(40, f"f:{token}:more"),
            headers=headers,
        ).status_code == 200
        assert client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(41, f"f:{token}:more"),
            headers=headers,
        ).status_code == 200
        assert client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(40, f"f:{token}:more"),
            headers=headers,
        ).status_code == 200

    assert store.feedback_events == 1
    answers = [call["text"] for call in sent if call["method"] == "answerCallbackQuery"]
    assert answers == ["Geri bildirim kaydedildi.", "Bu buton artık geçerli değil."]


def test_callback_answer_failure_is_safe_and_cannot_repeat_feedback() -> None:
    token = "e" * 20
    store = _FeedbackStore({token: Actor(42, 42).pair_hash})
    handler, _, finished = _callback_handler(store)

    async def failing_answer(_: str, __: dict[str, object]) -> tuple[int, bool, int | None]:
        return 500, False, None

    handler._bot = TelegramBotClient(  # type: ignore[assignment]
        TOKEN, timeout_seconds=1, retries=0, transport=failing_answer
    )
    with _client(handler) as client:
        response = client.post(
            "/integrations/telegram/webhook",
            json=_callback_payload(50, f"f:{token}:more"),
            headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        )

    assert response.status_code == 200
    assert store.feedback_events == 1
    assert finished == [(50, "telegram_delivery_error")]


@pytest.mark.asyncio
async def test_poller_reuses_handler_and_advances_cursor_after_safe_skips() -> None:
    processed: list[int] = []
    advanced: list[int] = []
    stop_event = asyncio.Event()

    class Cursor:
        async def load(self) -> int:
            return 0

        async def advance(self, offset: int) -> None:
            advanced.append(offset)

    class Handler:
        async def process_update(self, update: object) -> None:
            processed.append(update.update_id)  # type: ignore[attr-defined]

    async def transport(_: str, __: dict[str, object]) -> tuple[int, bool, int | None]:
        return 200, True, None

    calls = 0

    async def poll_transport(
        _: str, __: dict[str, object]
    ) -> tuple[int, bool, int | None, list[dict[str, object]] | None]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return 200, True, None, [{"update_id": 8}, _payload(9)]
        stop_event.set()
        return 200, True, None, []

    bot = TelegramBotClient(
        TOKEN,
        timeout_seconds=1,
        retries=0,
        transport=transport,
        polling_transport=poll_transport,
    )
    await TelegramPoller(
        _settings(telegram_mode="polling"),
        bot,
        Handler(),  # type: ignore[arg-type]
        Cursor(),  # type: ignore[arg-type]
    ).run(stop_event)

    assert processed == [8, 9]
    assert advanced == [9, 10]
