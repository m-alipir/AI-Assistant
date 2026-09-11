"""Offline Telegram boundary regressions; no Bot API or provider call is permitted."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings
from app.telegram.api import router
from app.telegram.core import (
    TelegramBotClient,
    TelegramDeliveryError,
    TelegramMessage,
    split_plain_text,
)
from app.telegram.service import Actor, TelegramWebhookHandler, _search_text

TOKEN = "123456789:telegram-token-for-offline-tests"
SECRET = "telegram_webhook_secret_with_adequate_entropy_123"


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


def test_plain_text_split_preserves_literal_content_without_format_mode() -> None:
    parts = split_plain_text("*not markdown*\n" + "x" * 4_100)
    assert len(parts) == 2
    assert parts[0].startswith("*not markdown*")
    assert all(len(part) <= 4_000 for part in parts)


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
        if "SELECT briefing_id, event_id FROM telegram_feedback_tokens" in query:
            token = str(values.get("token", ""))
            if token in self.expired_tokens or self.tokens.get(token) != values.get("actor_hash"):
                return _MappingResult(None)
            return _MappingResult({"briefing_id": "briefing-1", "event_id": "event-1"})
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
) -> tuple[TelegramWebhookHandler, list[dict[str, object]], list[tuple[int, str]]]:
    async def ask(_: object) -> dict[str, object]:
        raise AssertionError("callback must not invoke a model")

    async def claim(*_: object) -> bool:
        return True

    handler, sent, finished = _handler(ask=ask, claim=claim)
    handler._sessions = store  # type: ignore[assignment]
    handler._settings = _settings(telegram_allowed_actor_pairs=allowed_pairs)
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
    handler._settings = _settings(telegram_allowed_actor_pairs="42:42,43:43")
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
    handler, sent, _ = _callback_handler(store, allowed_pairs="42:42,43:43")
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
