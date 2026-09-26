"""Webhook parsing, authorization, durable replay protection, and canonical command routing."""

import asyncio
import hashlib
import logging
import re
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.briefing.presentation import (
    DAILY_BRIEFING_ITEM_LIMIT,
    order_briefing_items,
    safe_links,
)
from app.config.settings import Settings
from app.config.source_repository import (
    EnabledSourceDeleteBlocked,
    ManagedSourceCreate,
    ManagedSourceUpdate,
    SourceAlreadyExists,
    SourceNotFound,
    SourceRepository,
)
from app.interests.feedback import record_briefing_feedback
from app.knowledge.search import SearchFilters
from app.security import ProcessRateLimiter
from app.telegram.core import (
    TelegramBotClient,
    TelegramDeliveryError,
    TelegramMessage,
    feedback_keyboard,
    split_plain_text,
)

logger = logging.getLogger(__name__)

_BRIEFING_SECTION_ALIASES = {
    "For You": "Senin İçin / For You",
    "World in Brief": "Dünyada Neler Oldu? / World in Brief",
}
class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int


class TelegramInboundMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    from_user: TelegramUser = Field(validation_alias=AliasChoices("from", "from_user"))
    chat: TelegramChat
    text: str | None = None


class TelegramCallback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=128)
    from_user: TelegramUser = Field(validation_alias=AliasChoices("from", "from_user"))
    message: TelegramInboundMessage
    data: str = Field(min_length=1, max_length=64)


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: int = Field(ge=0, le=2**52 - 1)
    message: TelegramInboundMessage | None = None
    callback_query: TelegramCallback | None = None

    @model_validator(mode="after")
    def one_supported_payload(self) -> "TelegramUpdate":
        if self.message is not None and self.callback_query is not None:
            raise ValueError("multiple supported update payloads")
        return self


BriefingCallback = Callable[[], Awaitable[dict[str, object]]]
SearchCallback = Callable[[SearchFilters], Awaitable[dict[str, object]]]
StatusCallback = Callable[[], Awaitable[dict[str, object]]]
HistoryCallback = Callable[[int], Awaitable[list[dict[str, object]]]]
SourcesCallback = Callable[[], Awaitable[str]]
AddSourceCallback = Callable[[str, str, str, int], Awaitable[str]]
QueueSourceCategoryQuestionCallback = Callable[[str], Awaitable[str]]
SourceCategoryQuestionDeliveredCallback = Callable[[str, int], Awaitable[bool]]
DisableSourceCallback = Callable[[str], Awaitable[str]]
InterestsCallback = Callable[[], Awaitable[str]]
SetInterestCallback = Callable[[str, bool], Awaitable[str]]
DailyCallback = Callable[[], Awaitable[tuple[str, dict[str, object] | None]]]
GmailPollingCallback = Callable[[int | None], Awaitable[str]]
GmailConnectCallback = Callable[["Actor"], Awaitable[tuple[str, str | None]]]


@dataclass(frozen=True)
class Actor:
    user_id: int
    chat_id: int

    @property
    def pair_hash(self) -> str:
        return _hash(f"{self.user_id}:{self.chat_id}")

    @property
    def user_hash(self) -> str:
        return _hash(str(self.user_id))

    @property
    def chat_hash(self) -> str:
        return _hash(str(self.chat_id))


class TelegramWebhookHandler:
    """Keep Telegram untrusted until secret verification and actor-pair authorization succeed."""

    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker[AsyncSession],
        bot: TelegramBotClient,
        *,
        latest_briefing: BriefingCallback,
        search: SearchCallback,
        ask: SearchCallback,
        status: StatusCallback,
        history: HistoryCallback | None = None,
        sources: SourcesCallback | None = None,
        add_source: AddSourceCallback | None = None,
        disable_source: DisableSourceCallback | None = None,
        interests: InterestsCallback | None = None,
        set_interest: SetInterestCallback | None = None,
        source_repository: SourceRepository | None = None,
        queue_source_category_question: QueueSourceCategoryQuestionCallback | None = None,
        source_category_question_delivered: SourceCategoryQuestionDeliveredCallback | None = None,
        daily: DailyCallback | None = None,
        gmail_interval: GmailPollingCallback | None = None,
        gmail_connect: GmailConnectCallback | None = None,
    ) -> None:
        self._settings = settings
        self._sessions = sessions
        self._bot = bot
        self._latest_briefing = latest_briefing
        self._search = search
        self._ask = ask
        self._status = status
        self._history = history
        self._sources = sources
        self._add_source = add_source
        self._disable_source = disable_source
        self._interests = interests
        self._set_interest = set_interest
        self._source_repository = source_repository
        self._queue_source_category_question = queue_source_category_question
        self._source_category_question_delivered = source_category_question_delivered
        self._daily = daily
        self._gmail_interval = gmail_interval
        self._gmail_connect = gmail_connect
        self._per_actor = ProcessRateLimiter(settings.telegram_rate_limit_per_minute)
        self._global = ProcessRateLimiter(settings.telegram_global_rate_limit_per_minute)
        self._semaphore = asyncio.Semaphore(settings.telegram_max_concurrent_commands)
        self._daily_task: asyncio.Task[None] | None = None

    async def handle(self, request: Request) -> Response:
        """Always avoid reflecting provider input; accepted updates are terminally recorded."""
        if not self._settings.telegram_enabled:
            return Response(status_code=404)
        secret_values = request.headers.getlist("x-telegram-bot-api-secret-token")
        if len(secret_values) != 1 or not secrets.compare_digest(
            secret_values[0], self._settings.telegram_webhook_secret_value
        ):
            return Response(status_code=404)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].casefold()
        if content_type != "application/json":
            return Response(status_code=415)
        content_length = request.headers.get("content-length")
        if content_length and (
            not content_length.isdigit()
            or int(content_length) > self._settings.telegram_max_request_bytes
        ):
            return Response(status_code=413)
        try:
            body = await _bounded_body(request, self._settings.telegram_max_request_bytes)
            update = TelegramUpdate.model_validate_json(body)
        except (HTTPException, ValidationError, ValueError):
            return Response(status_code=400)
        await self.process_update(update)
        return Response(status_code=200)

    async def process_update(self, update: TelegramUpdate) -> None:
        """Run the canonical command/feedback boundary for webhook and polling transports."""
        actor = _actor_for(update)
        if actor is None or (actor.user_id, actor.chat_id) not in set(
            self._settings.telegram_allowed_actor_pair_list
        ):
            # Do not make an unauthorized caller observable in an audit table or bot response.
            return
        kind = "callback" if update.callback_query is not None else "message"
        if not await self._claim_update(update.update_id, actor, kind):
            return
        if not await self._global.allow() or not await self._per_actor.allow(actor.pair_hash):
            await self._finish_update(update.update_id, "rate_limited")
            return
        try:
            async with self._semaphore, asyncio.timeout(
                self._settings.telegram_command_timeout_seconds
            ):
                if update.callback_query is not None:
                    response = await self._record_callback(update, actor)
                    await self._bot.answer_callback_query(
                        update.callback_query.id,
                        _callback_answer_text(response),
                    )
                    await self._bot.send_message(actor.chat_id, TelegramMessage(response))
                else:
                    await self._handle_message(update, actor)
            await self._finish_update(update.update_id, "completed")
        except TimeoutError:
            logger.warning(
                "telegram_command_failed",
                extra={"diagnostic_category": "telegram_command_timeout"},
            )
            await self._finish_update(update.update_id, "command_timeout")
        except TelegramDeliveryError:
            logger.warning(
                "telegram_command_failed",
                extra={"diagnostic_category": "telegram_delivery_unavailable"},
            )
            await self._finish_update(update.update_id, "telegram_delivery_error")
        except Exception:
            # The command, provider response, and database exception never enter logs or Telegram.
            logger.warning(
                "telegram_command_failed",
                extra={"diagnostic_category": "telegram_command_unavailable"},
            )
            await self._finish_update(update.update_id, "command_unavailable")

    async def _handle_message(self, update: TelegramUpdate, actor: Actor) -> None:
        assert update.message is not None
        parsed = _command(update.message.text, self._settings.telegram_command_max_chars)
        if parsed is None:
            return
        command, argument = parsed
        if command == "start":
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage(_help_text()),
            )
            return
        if command == "yardim":
            await self._bot.send_message(actor.chat_id, TelegramMessage(_help_text()))
            return
        if command == "ozet":
            await self._send_briefing(actor)
            return
        if command == "daily":
            if self._daily is None:
                await self._bot.send_message(
                    actor.chat_id, TelegramMessage("Günlük özet şu anda çalıştırılamıyor.")
                )
                return
            if self._daily_task is not None and not self._daily_task.done():
                await self._bot.send_message(
                    actor.chat_id,
                    TelegramMessage("Başka bir işlem sürüyor. Biraz sonra tekrar deneyin."),
                )
                return
            await self._bot.send_message(
                actor.chat_id, TelegramMessage("Günlük özet hazırlanıyor.")
            )
            self._daily_task = asyncio.create_task(self._run_daily(actor))
            return
        if command == "gmail":
            if argument:
                if self._gmail_interval is None:
                    await self._bot.send_message(
                        actor.chat_id, TelegramMessage("Gmail ayarı şu anda alınamıyor.")
                    )
                    return
                if not argument.isascii() or not argument.isdecimal():
                    await self._bot.send_message(
                        actor.chat_id, TelegramMessage("Kullanım: /gmail [15–1440 dakika]")
                    )
                    return
                interval = int(argument)
                if not 15 <= interval <= 1440:
                    await self._bot.send_message(
                        actor.chat_id, TelegramMessage("Aralık 15 ile 1440 dakika arasında olmalı.")
                    )
                    return
                response = await self._gmail_interval(interval)
                await self._bot.send_message(actor.chat_id, TelegramMessage(response))
                return
            if self._gmail_connect is None:
                await self._bot.send_message(
                    actor.chat_id,
                    TelegramMessage(
                        "Google bağlantısı ayarlı değil. Sunucu yöneticisi şu ayar adlarını "
                        "kontrol etsin: GMAIL_ENABLED, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET veya "
                        "GMAIL_CLIENT_SECRET_FILE, GMAIL_OAUTH_REDIRECT_URI, APP_ENCRYPTION_KEY "
                        "veya APP_ENCRYPTION_KEY_FILE, ADMIN_PUBLIC_ORIGIN. Değerleri Telegram'da "
                        "paylaşmayın."
                    ),
                )
                return
            try:
                message, connect_url = await self._gmail_connect(actor)
            except Exception:
                logger.warning(
                    "telegram_command_failed",
                    extra={"diagnostic_category": "gmail_connect_unavailable"},
                )
                message, connect_url = (
                    "Google bağlantısı şu anda başlatılamıyor. Daha sonra tekrar deneyin.",
                    None,
                )
            reply_markup = (
                {"inline_keyboard": [[{"text": "Google ile bağla", "url": connect_url}]]}
                if connect_url
                else None
            )
            await self._bot.send_message(
                actor.chat_id, TelegramMessage(message, reply_markup)
            )
            return
        if command == "ara":
            await self._send_search(actor, argument, self._search, "Arama", "ara")
            return
        if command == "sor":
            await self._send_search(actor, argument, self._ask, "Yanıt", "sor")
            return
        if command == "durum":
            result = await self._status()
            text_value = str(result.get("text") or "Sistem durumu şu anda alınamıyor.")
            await self._bot.send_messages(
                actor.chat_id, [TelegramMessage(chunk) for chunk in split_plain_text(text_value)]
            )
            return
        if command == "gecmis":
            await self._send_history(actor, argument)
            return
        if command == "kaynaklar":
            if self._sources is not None:
                await self._send_control_text(actor, self._sources, "Kaynaklar şu anda alınamıyor.")
            else:
                await self._send_sources(actor)
            return
        if command == "kaynak_ekle":
            if self._add_source is not None:
                await self._add_source_command(actor, argument)
            else:
                await self._add_source_from_repository(actor, argument)
            return
        if command == "kaynak_kategori":
            await self._set_source_category(actor, argument)
            return
        if command == "kaynak_sil":
            if self._disable_source is not None:
                await self._disable_source_command(actor, argument)
            else:
                await self._delete_source(actor, argument)
            return
        if command == "ilgiler":
            await self._send_control_text(actor, self._interests, "İlgi alanları alınamıyor.")
            return
        if command in {"ilgi_ekle", "ilgi_sil"}:
            await self._set_interest_command(actor, argument, command == "ilgi_ekle")
            return
        if command == "kaynaklar":
            await self._send_sources(actor)
            return
        if command == "kaynak":
            await self._show_source(actor, argument)
            return
        if command == "kaynak_ekle":
            await self._add_source(actor, argument)
            return
        if command in {"kaynak_ac", "kaynak_kapat"}:
            await self._set_source_enabled(actor, argument, command == "kaynak_ac")
            return
        if command == "kaynak_sil":
            await self._delete_source(actor, argument)
            return
        await self._bot.send_message(
            actor.chat_id,
            TelegramMessage("Komut bulunamadı. Kullanılabilir komutlar için /yardim yazın."),
        )

    async def _run_daily(self, actor: Actor) -> None:
        try:
            if self._daily is None:
                return
            status, briefing = await self._daily()
            if status == "ok" and briefing is not None:
                await self._send_briefing(actor, briefing)
            elif status == "busy":
                await self._bot.send_message(
                    actor.chat_id,
                    TelegramMessage("Başka bir işlem sürüyor. Biraz sonra tekrar deneyin."),
                )
            else:
                await self._daily_unavailable(actor)
        except Exception:
            logger.warning(
                "telegram_command_failed",
                extra={"diagnostic_category": "telegram_command_unavailable"},
            )
            await self._daily_unavailable(actor)

    async def _daily_unavailable(self, actor: Actor) -> None:
        try:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Günlük özet tamamlanamadı. Daha sonra tekrar deneyin."),
            )
        except TelegramDeliveryError:
            logger.warning(
                "telegram_command_failed",
                extra={"diagnostic_category": "telegram_delivery_unavailable"},
            )

    async def send_briefing(
        self,
        chat_id: int,
        briefing: dict[str, object],
        calibration_candidates: list[dict[str, str]] | None = None,
        delivery_note: str | None = None,
    ) -> None:
        """Deliver a persisted briefing through the same renderer as ``/ozet``."""
        actor = next(
            (
                Actor(user_id, allowed_chat_id)
                for user_id, allowed_chat_id in self._settings.telegram_allowed_actor_pair_list
                if allowed_chat_id == chat_id
            ),
            None,
        )
        if actor is None:
            raise TelegramDeliveryError("telegram_destination_not_allowed")
        await self._send_briefing(actor, briefing, calibration_candidates, delivery_note)

    async def _send_briefing(
        self,
        actor: Actor,
        briefing: dict[str, object] | None = None,
        calibration_candidates: list[dict[str, str]] | None = None,
        delivery_note: str | None = None,
    ) -> None:
        if briefing is None:
            try:
                briefing = await self._latest_briefing()
            except LookupError:
                await self._bot.send_message(
                    actor.chat_id, TelegramMessage("Henüz kaydedilmiş özet yok.")
                )
                return
        items = briefing.get("items")
        if not isinstance(items, list):
            await self._bot.send_message(
                actor.chat_id, TelegramMessage("Özet şu anda kullanılamıyor.")
            )
            return
        briefing_id = str(briefing.get("id", ""))[:36]
        usable_items = [item for item in items if isinstance(item, dict)]
        usable_items = order_briefing_items(
            usable_items,
            section=lambda item: _briefing_section(item),
            published_at=lambda item: item.get("published_at"),
            event_id=lambda item: str(item.get("event_id") or ""),
            limit=DAILY_BRIEFING_ITEM_LIMIT,
        )
        message_text, visible_items = _render_daily_briefing(
            briefing.get("created_at"), usable_items, delivery_note
        )
        feedback_event_ids = [
            str(item.get("event_id", ""))[:36]
            for item in visible_items
            if item.get("event_id") and item.get("email_action") is None
        ]
        tokens = await self._create_feedback_tokens(
            actor,
            briefing_id,
            feedback_event_ids,
        )
        keyboard_rows: list[list[dict[str, str]]] = []
        for number, item in enumerate(visible_items, start=1):
            event_id = str(item.get("event_id", ""))[:36]
            if event_id not in tokens or item.get("email_action") is not None:
                continue
            buttons = feedback_keyboard(tokens[event_id])["inline_keyboard"][0]
            keyboard_rows.append(
                [
                    {
                        **button,
                        "text": f"{number}. {button['text']}",
                    }
                    for button in buttons
                ]
            )
        reply_markup = {"inline_keyboard": keyboard_rows} if keyboard_rows else None
        await self._bot.send_message(
            actor.chat_id, TelegramMessage(message_text, reply_markup)
        )
        if calibration_candidates:
            event_ids = [candidate["event_id"] for candidate in calibration_candidates]
            subjects = {
                candidate["event_id"]: candidate["subject"] for candidate in calibration_candidates
            }
            calibration_tokens = await self._create_feedback_tokens(
                actor, briefing_id, event_ids, subjects
            )
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage(
                    "İlk 14 günlük ayar: Bu konulardaki haberler ilginizi çekiyor mu? "
                    "Evet/Hayır seçin."
                ),
            )
            for candidate in calibration_candidates:
                event_id = candidate["event_id"]
                token = calibration_tokens.get(event_id)
                if token is None:
                    continue
                await self._bot.send_message(
                    actor.chat_id,
                    TelegramMessage(
                        f"{candidate['subject']} hakkındaki haberler ve gelişmeler "
                        "ilginizi çekiyor mu?",
                        feedback_keyboard(
                            token,
                            positive_text="Evet",
                            negative_text="Hayır",
                            include_not_useful=False,
                        ),
                    ),
                )

    async def _send_search(
        self, actor: Actor, argument: str, callback: SearchCallback, label: str, command: str
    ) -> None:
        if not argument:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage(f"/{command} için bir soru yazın."),
            )
            return
        result = await callback(SearchFilters(question=argument, limit=5))
        text_value = _search_text(result, label)
        await self._bot.send_messages(
            actor.chat_id, [TelegramMessage(chunk) for chunk in split_plain_text(text_value)]
        )

    async def _send_history(self, actor: Actor, argument: str) -> None:
        if self._history is None:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Geçmiş özetler kullanılamıyor."),
            )
            return
        try:
            limit = int(argument) if argument else 5
        except ValueError:
            limit = 5
        rows = await self._history(max(1, min(limit, 10)))
        if not rows:
            text_value = "Henüz kaydedilmiş özet yok."
        else:
            lines = ["Geçmiş özetler"]
            for row in rows:
                created_at = str(row.get("created_at") or "")[:25]
                title = str(row.get("title") or "Özet")[:200]
                lines.append(f"- {created_at}: {title}")
            text_value = "\n".join(lines)
        await self._bot.send_messages(
            actor.chat_id, [TelegramMessage(chunk) for chunk in split_plain_text(text_value)]
        )

    async def _send_control_text(
        self, actor: Actor, callback: SourcesCallback | InterestsCallback | None, unavailable: str
    ) -> None:
        if callback is None:
            await self._bot.send_message(actor.chat_id, TelegramMessage(unavailable))
            return
        text_value = await callback()
        await self._bot.send_messages(
            actor.chat_id, [TelegramMessage(chunk) for chunk in split_plain_text(text_value)]
        )

    async def _add_source_command(self, actor: Actor, argument: str) -> None:
        if self._add_source is None:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Kaynak yönetimi kullanılamıyor."),
            )
            return
        kind, separator, rest = argument.partition(" ")
        if kind.casefold() in {"rss", "youtube"}:
            endpoint, separator, name = (
                rest.strip().partition(" ") if separator else ("", "", "")
            )
        else:
            endpoint, separator, name = argument.partition(" ")
            kind = "auto"
        if not endpoint:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Kullanım: /kaynak_ekle <feed-url veya YouTube kanal-url> [ad]"),
            )
            return
        response = await self._add_source(kind, endpoint, name.strip(), actor.chat_id)
        await self._bot.send_message(actor.chat_id, TelegramMessage(response))

    async def _set_source_category(self, actor: Actor, argument: str) -> None:
        source_id, separator, category = argument.partition(" ")
        repository = self._source_repository
        if (
            not separator
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source_id)
            or not category.strip()
            or len(category.strip()) > 128
            or any(ord(char) < 32 for char in category)
        ):
            await self._send_source_reply(
                actor,
                "Kullanım: /kaynak_kategori <kaynak-kimliği> <kategori> (en fazla 128 karakter).",
            )
            return
        if repository is None or self._source_category_question_delivered is None:
            await self._send_source_reply(actor, "Kaynak kategorisi şu anda güncellenemiyor.")
            return
        try:
            update = ManagedSourceUpdate(category=category)
            if update.category is None:
                raise ValueError("category is required")
            delivered = await self._source_category_question_delivered(source_id, actor.chat_id)
            if not delivered:
                await self._send_source_reply(
                    actor, "Bu kaynak için bu sohbette bekleyen bir kategori sorusu yok."
                )
                return
            result = await repository.set_category_if_missing(source_id, update.category)
        except (ValidationError, ValueError):
            await self._send_source_reply(
                actor,
                "Kullanım: /kaynak_kategori <kaynak-kimliği> <kategori> (en fazla 128 karakter).",
            )
            return
        except Exception:
            await self._send_source_reply(actor, "Kaynak kategorisi şu anda güncellenemiyor.")
            return
        response = {
            "updated": "Kategori kaydedildi; kaynağın etkinlik durumu değişmedi.",
            "already_set": "Kategori zaten belirlenmiş; değiştirilmedi.",
            "not_found": "Kaynak bulunamadı; kategori yanıtı artık gerekli değil.",
        }.get(result, "Kaynak kategorisi şu anda güncellenemiyor.")
        await self._send_source_reply(actor, response)

    async def _disable_source_command(self, actor: Actor, argument: str) -> None:
        if self._disable_source is None:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Kaynak yönetimi kullanılamıyor."),
            )
            return
        if not argument:
            await self._bot.send_message(
                actor.chat_id, TelegramMessage("Kullanım: /kaynak_sil <kaynak-kimliği>"),
            )
            return
        result = await self._disable_source(argument)
        await self._bot.send_message(actor.chat_id, TelegramMessage(result))

    async def _set_interest_command(self, actor: Actor, argument: str, enabled: bool) -> None:
        if self._set_interest is None:
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("İlgi yönetimi kullanılamıyor."),
            )
            return
        if not argument:
            command = "/ilgi_ekle" if enabled else "/ilgi_sil"
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage(f"Kullanım: {command} <konu>"),
            )
            return
        result = await self._set_interest(argument, enabled)
        await self._bot.send_message(actor.chat_id, TelegramMessage(result))

    async def _send_sources(self, actor: Actor) -> None:
        repository = self._source_repository
        if repository is None:
            await self._send_source_reply(actor, _source_error_text(RuntimeError()))
            return
        try:
            rows = await repository.list()
        except Exception as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        if not rows:
            await self._send_source_reply(actor, "Henüz takip edilen kaynak yok.")
            return
        lines = ["Takip edilen kaynaklar"]
        for row in rows[:30]:
            state = "aktif" if row.get("enabled") else "pasif"
            health = _source_health_label(row.get("health_status"))
            lines.append(
                f"- {row.get('id')} · {row.get('kind')} · {row.get('name')} "
                f"({state}, {health})"
            )
        await self._send_source_reply(actor, "\n".join(lines))

    async def _show_source(self, actor: Actor, source_id: str) -> None:
        if not source_id:
            await self._send_source_reply(actor, "Kullanım: /kaynak <kaynak-kimliği>")
            return
        repository = self._source_repository
        if repository is None:
            await self._send_source_reply(actor, _source_error_text(RuntimeError()))
            return
        try:
            row = await repository.get(source_id)
            if row is None:
                raise SourceNotFound
        except Exception as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        state = "aktif" if row.get("enabled") else "pasif"
        lines = [
            str(row.get("name") or "Kaynak"),
            f"Kimlik: {row.get('id')}",
            f"Tür: {row.get('kind')}",
            f"Durum: {state}",
            f"Sağlık: {_source_health_label(row.get('health_status'))}",
            f"Adres: {row.get('canonical_endpoint')}",
        ]
        error_category = row.get("last_error_category")
        if error_category:
            lines.append(f"Son hata: {error_category}")
        await self._send_source_reply(actor, "\n".join(lines))

    async def _add_source_from_repository(self, actor: Actor, argument: str) -> None:
        try:
            parsed = _source_create(argument)
        except (ValidationError, ValueError) as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        if parsed is None:
            await self._send_source_reply(
                actor,
                "Kullanım: /kaynak_ekle [rss|youtube] <adres veya kanal-kimliği> [ad]",
            )
            return
        repository = self._source_repository
        if repository is None:
            await self._send_source_reply(actor, _source_error_text(RuntimeError()))
            return
        try:
            row = await repository.create(parsed)
        except Exception as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        if row.get("category") is None and self._queue_source_category_question is not None:
            try:
                await self._queue_source_category_question(str(row["id"]))
            except Exception:
                logger.warning(
                    "telegram_source_category_question_failed",
                    extra={"diagnostic_category": "category_question_queue_unavailable"},
                )
        await self._send_source_reply(
            actor,
            f"{row['name']} eklendi ve pasif bırakıldı. Kimlik: {row['id']}",
        )

    async def _set_source_enabled(
        self, actor: Actor, source_id: str, enabled: bool
    ) -> None:
        if not source_id:
            command = "/kaynak_ac" if enabled else "/kaynak_kapat"
            await self._send_source_reply(actor, f"Kullanım: {command} <kaynak-kimliği>")
            return
        repository = self._source_repository
        if repository is None:
            await self._send_source_reply(actor, _source_error_text(RuntimeError()))
            return
        try:
            if not await repository.set_enabled(source_id, enabled):
                raise SourceNotFound
        except Exception as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        state = "etkinleştirildi" if enabled else "devre dışı bırakıldı"
        await self._send_source_reply(actor, f"Kaynak {state}.")

    async def _delete_source(self, actor: Actor, source_id: str) -> None:
        if not source_id:
            await self._send_source_reply(actor, "Kullanım: /kaynak_sil <kaynak-kimliği>")
            return
        repository = self._source_repository
        if repository is None:
            await self._send_source_reply(actor, _source_error_text(RuntimeError()))
            return
        try:
            await repository.delete(source_id)
        except Exception as error:
            await self._send_source_reply(actor, _source_error_text(error))
            return
        await self._send_source_reply(actor, "Kaynak silindi.")

    async def _send_source_reply(self, actor: Actor, value: str) -> None:
        await self._bot.send_messages(
            actor.chat_id, [TelegramMessage(chunk) for chunk in split_plain_text(value)]
        )

    async def _claim_update(self, update_id: int, actor: Actor, kind: str) -> bool:
        async with self._sessions.begin() as session:
            row = await session.execute(
                text(
                    "INSERT INTO telegram_updates "
                    "(update_id, actor_hash, chat_hash, kind, status) "
                    "VALUES (:update_id, :actor_hash, :chat_hash, :kind, 'claimed') "
                    "ON CONFLICT (update_id) DO UPDATE SET status = 'claimed', "
                    "failure_category = NULL, updated_at = now() "
                    "WHERE telegram_updates.status = 'claimed' "
                    "AND telegram_updates.updated_at < now() - "
                    "(:lease * interval '1 second') RETURNING update_id"
                ),
                {
                    "update_id": update_id,
                    "actor_hash": actor.user_hash,
                    "chat_hash": actor.chat_hash,
                    "kind": kind,
                    "lease": self._settings.telegram_processing_lease_seconds,
                },
            )
        return row.scalar_one_or_none() is not None

    async def _finish_update(self, update_id: int, category: str) -> None:
        status = "completed" if category == "completed" else "failed"
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE telegram_updates SET status = :status, failure_category = :category, "
                    "updated_at = now() WHERE update_id = :update_id"
                ),
                {
                    "status": status,
                    "category": None if status == "completed" else category,
                    "update_id": update_id,
                },
            )

    async def _create_feedback_tokens(
        self,
        actor: Actor,
        briefing_id: str,
        event_ids: list[str],
        subjects: dict[str, str] | None = None,
    ) -> dict[str, str]:
        if not briefing_id:
            return {}
        values: dict[str, str] = {}
        async with self._sessions.begin() as session:
            for event_id in event_ids:
                if not event_id:
                    continue
                token = secrets.token_urlsafe(15)
                await session.execute(
                    text(
                        "INSERT INTO telegram_feedback_tokens "
                        "(token, actor_pair_hash, briefing_id, event_id, subject, expires_at) "
                        "VALUES (:token, :actor_hash, :briefing_id, :event_id, :subject, "
                        "now() + interval '24 hours')"
                    ),
                    {
                        "token": token,
                        "actor_hash": actor.pair_hash,
                        "briefing_id": briefing_id,
                        "event_id": event_id,
                        "subject": (subjects or {}).get(event_id),
                    },
                )
                values[event_id] = token
        return values

    async def _record_callback(self, update: TelegramUpdate, actor: Actor) -> str:
        assert update.callback_query is not None
        parsed = _feedback_data(update.callback_query.data)
        if parsed is None:
            return "Bu geri bildirim artık geçerli değil. Yeni bir /ozet isteyin."
        token, action = parsed
        async with self._sessions.begin() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT briefing_id, event_id, subject FROM telegram_feedback_tokens "
                        "WHERE token = :token AND actor_pair_hash = :actor_hash "
                        "AND expires_at > now() FOR UPDATE"
                    ),
                    {"token": token, "actor_hash": actor.pair_hash},
                )
            ).mappings().one_or_none()
            if row is None:
                return "Bu geri bildirim artık geçerli değil. Yeni bir /ozet isteyin."
            result = await record_briefing_feedback(
                session,
                str(row["briefing_id"]),
                str(row["event_id"]),
                action,
                subject=str(row["subject"]) if row.get("subject") else None,
            )
            await session.execute(
                text("DELETE FROM telegram_feedback_tokens WHERE token = :token"), {"token": token}
            )
            await session.execute(
                text(
                    "UPDATE telegram_updates "
                    "SET status = 'completed', failure_category = NULL, updated_at = now() "
                    "WHERE update_id = :update_id"
                ),
                {"update_id": update.update_id},
            )
        return result.message


async def _bounded_body(request: Request, maximum: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > maximum:
            raise HTTPException(status_code=413)
        body.extend(chunk)
    return bytes(body)


def _actor_for(update: TelegramUpdate) -> Actor | None:
    if update.callback_query is not None:
        return Actor(update.callback_query.from_user.id, update.callback_query.message.chat.id)
    if update.message is not None:
        return Actor(update.message.from_user.id, update.message.chat.id)
    return None


def _command(value: str | None, maximum: int) -> tuple[str, str] | None:
    has_control_character = value is not None and any(
        ord(char) < 32 and char not in "\n\r\t" for char in value
    )
    if value is None or len(value) > maximum or has_control_character:
        return None
    command, separator, argument = value.strip().partition(" ")
    if not command.startswith("/"):
        return None
    command = command[1:].partition("@")[0].casefold()
    if command not in {
        "start",
        "yardim",
        "ozet",
        "daily",
        "gmail",
        "gecmis",
        "ara",
        "sor",
        "durum",
        "kaynaklar",
        "kaynak",
        "kaynak_ekle",
        "kaynak_kategori",
        "kaynak_ac",
        "kaynak_kapat",
        "kaynak_sil",
        "ilgiler",
        "ilgi_ekle",
        "ilgi_sil",
    }:
        return None
    return command, argument.strip()


def _feedback_data(value: str) -> tuple[str, str] | None:
    parts = value.split(":")
    if len(parts) != 3 or parts[0] != "f" or len(parts[1]) != 20:
        return None
    if parts[2] not in {"more", "less", "not_useful"}:
        return None
    return parts[1], parts[2]


def _callback_answer_text(response: str) -> str:
    """Keep callback acknowledgements short and independent of stored feedback detail."""
    if response.startswith("Bu geri bildirim artık geçerli değil."):
        return "Bu buton artık geçerli değil."
    return "Geri bildirim kaydedildi."


def _briefing_section(item: dict[str, object]) -> str:
    section = str(item.get("section") or "")
    return _BRIEFING_SECTION_ALIASES.get(section, section)


def _render_daily_briefing(
    created_at: object, items: list[dict[str, object]], delivery_note: str | None
) -> tuple[str, list[dict[str, object]]]:
    visible: list[dict[str, object]] = []
    lines = ["Bugün şunlar oldu:"]
    for item in items:
        if len(visible) >= DAILY_BRIEFING_ITEM_LIMIT:
            break
        if item.get("original_text") and not item.get("what_changed"):
            continue
        body = _briefing_summary(item)
        if not body:
            continue
        number = len(visible) + 1
        current_length = len("\n\n".join(lines))
        budget = 3500 - current_length - len(f"\n\n{number}. ")
        if budget < 36:
            break
        body = _fit_briefing_sentence(body, min(420, budget))
        line = f"{number}. {body}"
        if len("\n\n".join([*lines, line])) > 3500:
            break
        lines.append(line)
        visible.append(item)
    if not visible:
        return "Bugün öne çıkan yeni bir gelişme yok.", visible
    return "\n\n".join(lines), visible


def _briefing_summary(item: dict[str, object]) -> str:
    body = str(
        (item.get("what_changed") if item.get("original_text") else item.get("summary"))
        or item.get("what_changed")
        or ""
    )
    body = re.sub(r"(?i)\s*\(\s*source:\s*title\s*,\s*snippet\s*\)", "", body)
    body = re.sub(r"(?i)\b(?:title|snippet)\s*:\s*", "", body)
    return " ".join(body.split())


def _fit_briefing_sentence(value: str, limit: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", value.strip())
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*kept, sentence])
        if len(candidate) > limit:
            if not kept:
                prefix = sentence[: limit - 1]
                clause = max(prefix.rfind(";"), prefix.rfind(" —"), prefix.rfind(" –"))
                boundary = clause + 1 if clause >= limit // 2 else prefix.rfind(" ")
                return prefix[:boundary].rstrip(" ,;:—–") + "…"
            break
        kept.append(sentence)
    if kept:
        return " ".join(kept)
    return value[:limit]


def _search_text(value: dict[str, object], label: str) -> str:
    if value.get("status") != "ok":
        return str(value.get("answer_tr") or "Yeterli kaynak bulunamadı.")[:1_000]
    parts = [label, str(value.get("answer_tr") or "")[:1_000]]
    events = value.get("events")
    if isinstance(events, list):
        for event in events[:5]:
            if not isinstance(event, dict):
                continue
            parts.append(str(event.get("title") or "Kaydedilmiş olay")[:320])
            for fact in event.get("verified_facts") or []:
                parts.append(f"- {str(fact)[:400]}")
            links = event.get("source_links")
            if isinstance(links, list):
                parts.extend(safe_links([str(link) for link in links])[:3])
    inferences = value.get("model_inferences")
    if isinstance(inferences, list) and inferences:
        parts.append("Model çıkarımı:")
        parts.extend(f"- {str(item)[:400]}" for item in inferences[:3])
    return "\n".join(part for part in parts if part)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _legacy_help_text() -> str:
    return (
        "Kişisel bilgi asistanı\n"
        "/ozet — son özet\n/gecmis [sayı] — geçmiş özetler\n"
        "/ara <konu> — hafızada ara\n/sor <soru> — kaynaklı soru sor\n"
        "/durum — sistem durumu\n/kaynaklar — takip edilen kaynaklar\n"
        "/kaynak_ekle <feed-url veya YouTube kanal-url> [ad]\n"
        "Gerekirse: /kaynak_ekle rss|youtube <adres> [ad]\n"
        "/kaynak_sil <kaynak-kimliği> — devre dışı bırak\n"
        "/ilgiler — ilgi alanları\n/ilgi_ekle <konu>\n/ilgi_sil <konu>"
    )


def _source_create(value: str) -> ManagedSourceCreate | None:
    argument = " ".join(value.split())
    if not argument:
        return None
    first, separator, remainder = argument.partition(" ")
    if first.casefold() in {"rss", "youtube"}:
        endpoint, endpoint_separator, name = remainder.partition(" ")
        if not separator or not endpoint:
            return None
        return ManagedSourceCreate(
            kind=first.casefold(),
            endpoint=endpoint,
            name=name.strip() if endpoint_separator else endpoint[:256],
            enabled=False,
        )
    endpoint, name_separator, name = argument.partition(" ")
    source_name = name.strip() if name_separator else endpoint[:256]
    for kind in ("youtube", "rss"):
        try:
            return ManagedSourceCreate(
                kind=kind,
                endpoint=endpoint,
                name=source_name,
                enabled=False,
            )
        except ValidationError:
            continue
    raise ValueError("invalid source")


def _source_health_label(value: object) -> str:
    return {
        "healthy": "sağlıklı",
        "degraded": "sorunlu",
        "unhealthy": "sağlıksız",
    }.get(str(value), "bilinmiyor")


def _source_error_text(error: Exception) -> str:
    if isinstance(error, SourceAlreadyExists):
        return "Bu kaynak zaten takip ediliyor."
    if isinstance(error, SourceNotFound):
        return "Kaynak bulunamadı. /kaynaklar ile kimliği kontrol edin."
    if isinstance(error, EnabledSourceDeleteBlocked):
        return "Aktif kaynak silinemez. Önce /kaynak_kapat <kaynak-kimliği> kullanın."
    if isinstance(error, (ValidationError, ValueError)):
        return (
            "Kaynak bilgisi geçersiz. Geçerli bir RSS/Atom adresi veya "
            "YouTube kanal kimliği yazın."
        )
    return "Kaynak yönetimi şu anda kullanılamıyor."


def _help_text() -> str:
    return (
        "Kişisel bilgi asistanı\n"
        "/daily — yeni günlük özet oluştur\n/ozet — son özet\n"
        "/gmail — Google hesabını salt okunur bağla\n"
        "/gmail [15–1440 dakika] — Gmail kontrol aralığı\n"
        "/ara <konu> — hafızada ara\n"
        "/sor <soru> — kaynaklı soru sor\n/durum — sistem durumu\n"
        "/kaynaklar — kaynakları göster\n/kaynak <kimlik> — kaynak durumu\n"
        "/kaynak_ekle rss|youtube <adres> [ad]\n"
        "/kaynak_kategori <kimlik> <kategori> — bekleyen kategori sorusunu yanıtla\n"
        "/kaynak_ac <kimlik>\n/kaynak_kapat <kimlik>\n/kaynak_sil <kimlik>\n"
        "/gecmis [sayÄ±], /ilgiler, /ilgi_ekle <konu>, /ilgi_sil <konu>"
    )
