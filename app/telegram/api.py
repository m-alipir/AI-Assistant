"""Minimal webhook route; all authorization and parsing remain inside the Telegram boundary."""

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter(tags=["telegram"])


@router.post("/integrations/telegram/webhook", include_in_schema=False)
async def webhook(request: Request) -> Response:
    handler = getattr(request.app.state, "telegram_webhook_handler", None)
    if handler is None:
        return Response(status_code=404)
    return await handler.handle(request)
