"""Webhook parsing, authorization, durable replay protection, and canonical command routing."""

import asyncio
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.briefing.presentation import safe_links
from app.config.settings import Settings
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
    ) -> None:
        self._settings = settings
        self._sessions = sessions
        self._bot = bot
        self._latest_briefing = latest_briefing
        self._search = search
        self._ask = ask
        self._status = status
        self._per_actor = ProcessRateLimiter(settings.telegram_rate_limit_per_minute)
        self._global = ProcessRateLimiter(settings.telegram_global_rate_limit_per_minute)
        self._semaphore = asyncio.Semaphore(settings.telegram_max_concurrent_commands)

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
        actor = _actor_for(update)
        if actor is None or (actor.user_id, actor.chat_id) not in set(
            self._settings.telegram_allowed_actor_pair_list
        ):
            # Do not make an unauthorized caller observable in an audit table or bot response.
            return Response(status_code=200)
        kind = "callback" if update.callback_query is not None else "message"
        if not await self._claim_update(update.update_id, actor, kind):
            return Response(status_code=200)
        if not await self._global.allow() or not await self._per_actor.allow(actor.pair_hash):
            await self._finish_update(update.update_id, "rate_limited")
            return Response(status_code=200)
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
            await self._finish_update(update.update_id, "command_timeout")
        except TelegramDeliveryError:
            await self._finish_update(update.update_id, "telegram_delivery_error")
        except Exception:
            # The command, provider response, and database exception never enter logs or Telegram.
            await self._finish_update(update.update_id, "command_unavailable")
        return Response(status_code=200)

    async def _handle_message(self, update: TelegramUpdate, actor: Actor) -> None:
        assert update.message is not None
        parsed = _command(update.message.text, self._settings.telegram_command_max_chars)
        if parsed is None:
            return
        command, argument = parsed
        if command == "start":
            await self._bot.send_message(
                actor.chat_id,
                TelegramMessage("Yetkili kullanıcılar için kişisel bilgi asistanı hazır."),
            )
            return
        if command == "ozet":
            await self._send_briefing(actor)
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
        await self._bot.send_message(
            actor.chat_id,
            TelegramMessage("Komut bulunamadı. /ozet, /ara, /sor veya /durum kullanın."),
        )

    async def _send_briefing(self, actor: Actor) -> None:
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
        usable_items = [item for item in items if isinstance(item, dict)][:5]
        feedback_event_ids = [
            str(item.get("event_id", ""))[:36]
            for item in usable_items
            if item.get("event_id") and item.get("email_action") is None
        ]
        tokens = await self._create_feedback_tokens(
            actor,
            briefing_id,
            feedback_event_ids,
        )
        header = "Son özet"
        created_at = briefing.get("created_at")
        if created_at:
            header = f"{header}\n{str(created_at)[:25]}"
        await self._bot.send_message(actor.chat_id, TelegramMessage(header))
        for item in usable_items:
            event_id = str(item.get("event_id", ""))[:36]
            message = TelegramMessage(
                _briefing_item_text(item),
                feedback_keyboard(tokens[event_id]) if event_id in tokens else None,
            )
            chunks = split_plain_text(message.text)
            await self._bot.send_messages(
                actor.chat_id,
                [
                    TelegramMessage(chunk, message.reply_markup if index == 0 else None)
                    for index, chunk in enumerate(chunks)
                ],
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
        self, actor: Actor, briefing_id: str, event_ids: list[str]
    ) -> dict[str, str]:
        if not briefing_id:
            return {}
        values: dict[str, str] = {}
        async with self._sessions.begin() as session:
            for event_id in event_ids:
                if not event_id:
                    continue
                token = secrets.token_urlsafe(12).replace("-", "A").replace("_", "B")[:20]
                await session.execute(
                    text(
                        "INSERT INTO telegram_feedback_tokens "
                        "(token, actor_pair_hash, briefing_id, event_id, expires_at) "
                        "VALUES (:token, :actor_hash, :briefing_id, :event_id, "
                        "now() + interval '24 hours')"
                    ),
                    {
                        "token": token,
                        "actor_hash": actor.pair_hash,
                        "briefing_id": briefing_id,
                        "event_id": event_id,
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
                        "SELECT briefing_id, event_id FROM telegram_feedback_tokens "
                        "WHERE token = :token AND actor_pair_hash = :actor_hash "
                        "AND expires_at > now() FOR UPDATE"
                    ),
                    {"token": token, "actor_hash": actor.pair_hash},
                )
            ).mappings().one_or_none()
            if row is None:
                return "Bu geri bildirim artık geçerli değil. Yeni bir /ozet isteyin."
            result = await record_briefing_feedback(
                session, str(row["briefing_id"]), str(row["event_id"]), action
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
    if command not in {"start", "ozet", "ara", "sor", "durum"}:
        return command, ""
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


def _briefing_item_text(item: dict[str, object]) -> str:
    parts = [str(item.get("section") or "Özet"), str(item.get("title") or "Kaydedilmiş olay")]
    summary = str(item.get("summary") or "")[:600]
    if summary:
        parts.append(summary)
    what_changed = item.get("what_changed")
    if what_changed:
        parts.append(f"Değişiklik: {str(what_changed)[:400]}")
    links = item.get("source_links")
    if isinstance(links, list):
        parts.extend(safe_links([str(link) for link in links])[:3])
    return "\n".join(parts)


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
