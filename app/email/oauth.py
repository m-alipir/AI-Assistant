"""Bounded Google OAuth code flow; secrets are never logged or returned."""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode

import httpx

from app.email.core import GMAIL_READONLY_SCOPE

OAuthErrorCategory = Literal[
    "oauth_state_invalid_or_expired",
    "token_exchange_invalid_client",
    "token_exchange_redirect_mismatch",
    "token_exchange_upstream_http_error",
    "refresh_token_missing",
    "token_storage_error",
]


class OAuthFlowError(Exception):
    """A safe, user-actionable OAuth failure with no provider payload."""

    def __init__(self, category: OAuthErrorCategory) -> None:
        self.category = category
        super().__init__(category)


def classify_token_endpoint_error(error_code: object) -> OAuthFlowError:
    """Map only Google's non-secret ``error`` code to a safe diagnostic category."""
    if error_code == "invalid_client":
        return OAuthFlowError("token_exchange_invalid_client")
    if error_code == "redirect_uri_mismatch":
        return OAuthFlowError("token_exchange_redirect_mismatch")
    return OAuthFlowError("token_exchange_upstream_http_error")


class GmailOAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id, self.client_secret, self.redirect_uri = (
            client_id,
            client_secret,
            redirect_uri,
        )
        self.states: dict[str, tuple[datetime, str]] = {}

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def authorization_url(self) -> str:
        if not self.configured:
            raise ValueError("Gmail OAuth is not configured")
        now = datetime.now(UTC)
        self.states = {value: entry for value, entry in self.states.items() if entry[0] >= now}
        if len(self.states) >= 32:
            # An authenticated operator can start a fresh flow after old states expire; do not
            # allow repeated browser navigation to consume unbounded process memory.
            raise ValueError("too many active OAuth authorization attempts")
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode()
        self.states[state] = (now + timedelta(minutes=10), verifier)
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": GMAIL_READONLY_SCOPE,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge.rstrip("="),
                "code_challenge_method": "S256",
            }
        )

    async def exchange(self, code: str, state: str) -> dict[str, str]:
        entry = self.states.pop(state, None)
        if not entry or entry[0] < datetime.now(UTC):
            raise OAuthFlowError("oauth_state_invalid_or_expired")
        _, verifier = entry
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                        "code_verifier": verifier,
                    },
                )
        except httpx.HTTPError as error:
            raise OAuthFlowError("token_exchange_upstream_http_error") from error
        if response.is_error:
            error_code: object = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    error_code = payload.get("error")
            except ValueError:
                pass
            raise classify_token_endpoint_error(error_code)
        try:
            token = response.json()
        except ValueError as error:
            raise OAuthFlowError("token_exchange_upstream_http_error") from error
        refresh = token.get("refresh_token")
        if not isinstance(refresh, str) or not refresh:
            raise OAuthFlowError("refresh_token_missing")
        return {"refresh_token": refresh}
