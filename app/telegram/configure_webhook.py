"""Explicit VDS-only webhook setup; it never runs during application startup."""

import asyncio

from app.config.settings import get_settings
from app.telegram.core import TelegramBotClient, TelegramDeliveryError


async def main() -> int:
    settings = get_settings()
    if not settings.telegram_enabled:
        print("Telegram is disabled; webhook was not changed.")
        return 2
    client = TelegramBotClient(
        settings.telegram_bot_token_value,
        timeout_seconds=settings.telegram_request_timeout_seconds,
        retries=settings.telegram_max_retries,
    )
    try:
        await client.configure_webhook(
            settings.telegram_webhook_url, settings.telegram_webhook_secret_value
        )
    except TelegramDeliveryError:
        print("Telegram webhook configuration failed safely; inspect protected operational logs.")
        return 1
    print("Telegram webhook configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
