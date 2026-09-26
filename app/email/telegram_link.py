"""Short-lived, actor-bound Gmail OAuth intents initiated from Telegram."""

import hashlib
import json
import re
import secrets
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.email.core import TokenCipher

IntentStatus = Literal["missing", "active", "expired", "replayed", "invalid_actor"]
_TOKEN = re.compile(r"[A-Za-z0-9_-]{40,64}\Z")
_TTL = timedelta(minutes=10)


class TelegramGmailLinkIntents:
    """Persist only a token hash and encrypted actor IDs across the Telegram worker boundary."""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], cipher: TokenCipher
    ) -> None:
        self._sessions = sessions
        self._cipher = cipher

    async def issue(self, user_id: int, chat_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        actor = self._cipher.protect(json.dumps([user_id, chat_id], separators=(",", ":")))
        async with self._sessions.begin() as session:
            await session.execute(
                text("DELETE FROM telegram_gmail_oauth_intents WHERE expires_at <= :now"),
                {"now": now},
            )
            await session.execute(
                text(
                    "INSERT INTO telegram_gmail_oauth_intents "
                    "(intent_hash, actor_ciphertext, expires_at) "
                    "VALUES (:intent_hash, :actor_ciphertext, :expires_at)"
                ),
                {
                    "intent_hash": _digest(token),
                    "actor_ciphertext": actor,
                    "expires_at": now + _TTL,
                },
            )
        return token

    async def claim(self, token: str) -> str | None:
        if not _TOKEN.fullmatch(token):
            return None
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            actor = await session.execute(
                text(
                    "UPDATE telegram_gmail_oauth_intents SET consumed_at = :now "
                    "WHERE intent_hash = :intent_hash AND oauth_state_hash IS NULL "
                    "AND consumed_at IS NULL AND expires_at > :now "
                    "RETURNING actor_ciphertext"
                ),
                {"intent_hash": _digest(token), "now": now},
            )
            return actor.scalar_one_or_none()

    async def bind(self, token: str, oauth_state: str) -> bool:
        if not _TOKEN.fullmatch(token) or not _TOKEN.fullmatch(oauth_state):
            return False
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            result = await session.execute(
                text(
                    "UPDATE telegram_gmail_oauth_intents "
                    "SET oauth_state_hash = :state_hash, expires_at = :expires_at "
                    "WHERE intent_hash = :intent_hash AND consumed_at IS NOT NULL "
                    "AND oauth_state_hash IS NULL AND expires_at > :now "
                    "RETURNING intent_hash"
                ),
                {
                    "state_hash": _digest(oauth_state),
                    "intent_hash": _digest(token),
                    "expires_at": now + _TTL,
                    "now": now,
                },
            )
            return result.scalar_one_or_none() is not None

    async def claim_oauth_state(self, oauth_state: str) -> IntentStatus:
        if not _TOKEN.fullmatch(oauth_state):
            return "missing"
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            result = await session.execute(
                text(
                    "UPDATE telegram_gmail_oauth_intents SET callback_claimed_at = :now "
                    "WHERE oauth_state_hash = :state_hash AND callback_claimed_at IS NULL "
                    "AND expires_at > :now RETURNING intent_hash"
                ),
                {"state_hash": _digest(oauth_state), "now": now},
            )
            if result.scalar_one_or_none() is not None:
                return "active"
            row = (
                await session.execute(
                    text(
                        "SELECT expires_at FROM telegram_gmail_oauth_intents "
                        "WHERE oauth_state_hash = :state_hash"
                    ),
                    {"state_hash": _digest(oauth_state)},
                )
            ).mappings().one_or_none()
        if row is None:
            return "missing"
        return "expired" if row["expires_at"] <= now else "replayed"

    async def complete(
        self,
        oauth_state: str,
        refresh_token: str | None,
        allowed_pairs: Collection[tuple[int, int]],
        store_token: Callable[[str], Awaitable[None]],
        notify: Callable[[tuple[int, int], str], Awaitable[None]],
    ) -> str | None:
        if not _TOKEN.fullmatch(oauth_state):
            return "invalid_actor"
        now = datetime.now(UTC)
        async with self._sessions.begin() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT actor_ciphertext FROM telegram_gmail_oauth_intents "
                        "WHERE oauth_state_hash = :state_hash "
                        "AND callback_claimed_at IS NOT NULL AND completed_at IS NULL "
                        "FOR UPDATE"
                    ),
                    {"state_hash": _digest(oauth_state)},
                )
            ).mappings().one_or_none()
            if row is None:
                return "invalid_actor"
            await session.execute(
                text(
                    "UPDATE telegram_gmail_oauth_intents "
                    "SET completed_at = :now, actor_ciphertext = NULL "
                    "WHERE oauth_state_hash = :state_hash AND callback_claimed_at IS NOT NULL "
                    "AND completed_at IS NULL"
                ),
                {"state_hash": _digest(oauth_state), "now": now},
            )
            actor_ciphertext = row["actor_ciphertext"]
        if not isinstance(actor_ciphertext, str):
            return "invalid_actor"
        try:
            actor = json.loads(self._cipher.reveal(actor_ciphertext))
            if (
                not isinstance(actor, list)
                or len(actor) != 2
                or type(actor[0]) is not int
                or actor[0] <= 0
                or type(actor[1]) is not int
                or actor[1] == 0
            ):
                raise ValueError("invalid Telegram actor")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return "invalid_actor"
        actor_pair = (actor[0], actor[1])
        if actor_pair not in allowed_pairs:
            return "unauthorized"
        if refresh_token is None:
            await notify(actor_pair, _RETRY_MESSAGE)
            return "failed"
        try:
            await store_token(refresh_token)
        except Exception:
            await notify(actor_pair, _STORE_FAILURE_MESSAGE)
            return "storage_error"
        await notify(actor_pair, "Gmail hesabı bağlandı; erişim salt okunurdur.")
        return "connected"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


_RETRY_MESSAGE = "Gmail bağlantısı tamamlanamadı. Telegram'dan /gmail komutuyla yeniden deneyin."
_STORE_FAILURE_MESSAGE = (
    "Gmail bağlantısı kaydedilemedi. Sunucu yöneticisi yapılandırmayı kontrol etmeli."
)
