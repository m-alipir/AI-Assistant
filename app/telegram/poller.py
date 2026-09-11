"""Outbound-only Telegram long-poll worker; it never starts an HTTP server."""

import asyncio
import contextlib
import signal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.settings import Settings, get_settings
from app.telegram.core import TelegramBotClient, TelegramDeliveryError
from app.telegram.service import TelegramUpdate, TelegramWebhookHandler


class _UpdateOffset(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: int = Field(ge=0, le=2**52 - 1)


class TelegramPollingCursor:
    """Persist only the next numeric Telegram offset, never update content or identities."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def load(self) -> int:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO telegram_polling_state (consumer_name, next_offset) "
                    "VALUES ('primary', 0) ON CONFLICT (consumer_name) DO NOTHING"
                )
            )
            return int(
                await session.scalar(
                    text(
                        "SELECT next_offset FROM telegram_polling_state "
                        "WHERE consumer_name = 'primary'"
                    )
                )
                or 0
            )

    async def advance(self, next_offset: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE telegram_polling_state SET next_offset = "
                    "greatest(next_offset, :offset), "
                    "updated_at = now() WHERE consumer_name = 'primary'"
                ),
                {"offset": next_offset},
            )


class TelegramPoller:
    """Sequentially poll and route updates through the existing authorization boundary."""

    def __init__(
        self,
        settings: Settings,
        bot: TelegramBotClient,
        handler: TelegramWebhookHandler,
        cursor: TelegramPollingCursor,
    ) -> None:
        self._settings = settings
        self._bot = bot
        self._handler = handler
        self._cursor = cursor

    async def run(self, stop_event: asyncio.Event) -> None:
        backoff = 1
        while not stop_event.is_set():
            try:
                await self._bot.delete_webhook()
                break
            except TelegramDeliveryError:
                await _wait_or_stop(stop_event, backoff)
                backoff = min(backoff * 2, self._settings.telegram_polling_max_backoff_seconds)
        if stop_event.is_set():
            return
        offset = await self._cursor.load()
        backoff = 1
        while not stop_event.is_set():
            try:
                updates = await self._bot.get_updates(
                    offset=offset,
                    timeout_seconds=self._settings.telegram_polling_timeout_seconds,
                    limit=self._settings.telegram_polling_batch_limit,
                )
                backoff = 1
                for raw_update in updates:
                    try:
                        envelope = _UpdateOffset.model_validate(raw_update)
                    except ValidationError:
                        continue
                    next_offset = envelope.update_id + 1
                    try:
                        update = TelegramUpdate.model_validate(raw_update)
                    except ValidationError:
                        await self._cursor.advance(next_offset)
                        offset = max(offset, next_offset)
                        continue
                    await self._handler.process_update(update)
                    await self._cursor.advance(next_offset)
                    offset = max(offset, next_offset)
            except TelegramDeliveryError:
                await _wait_or_stop(stop_event, backoff)
                backoff = min(backoff * 2, self._settings.telegram_polling_max_backoff_seconds)


async def _wait_or_stop(stop_event: asyncio.Event, seconds: int) -> None:
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)


async def main() -> int:
    settings = get_settings()
    if not settings.telegram_enabled or settings.telegram_mode != "polling":
        print("Telegram polling is disabled or not selected.")
        return 2
    from app.main import app

    handler = getattr(app.state, "telegram_command_handler", None)
    if handler is None or app.state.engine is None:
        print("Telegram polling runtime is unavailable.")
        return 1
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    bot = TelegramBotClient(
        settings.telegram_bot_token_value,
        timeout_seconds=settings.telegram_request_timeout_seconds,
        retries=settings.telegram_max_retries,
    )
    try:
        await TelegramPoller(
            settings,
            bot,
            handler,
            TelegramPollingCursor(app.state.sessions),
        ).run(stop_event)
    finally:
        await app.state.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
