"""Narrow capability-gated entrypoints for external account handshakes."""

from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=["integrations"])


@router.get("/integrations/telegram/gmail/connect", include_in_schema=False)
async def telegram_gmail_connect(
    request: Request, intent: str = Query(min_length=40, max_length=64)
) -> RedirectResponse:
    """Consume a Telegram-issued one-time intent and start the existing Gmail OAuth flow."""
    start = getattr(request.app.state, "start_telegram_gmail_oauth", None)
    if not callable(start):
        raise HTTPException(404)
    url = await start(intent)
    target = urlsplit(url) if isinstance(url, str) else None
    if (
        target is None
        or target.scheme != "https"
        or target.netloc.casefold() != "accounts.google.com"
        or target.path != "/o/oauth2/v2/auth"
        or target.fragment
    ):
        raise HTTPException(404)
    response = RedirectResponse(url, status_code=302)
    response.headers["Cache-Control"] = "no-store"
    return response
