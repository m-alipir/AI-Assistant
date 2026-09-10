from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.email.core import TokenCipher
from app.email.oauth import GmailOAuth, OAuthFlowError, classify_token_endpoint_error
from app.main import create_app


def test_oauth_authorization_url_is_readonly_and_stateful() -> None:
    oauth = GmailOAuth("client", "secret", "http://localhost:8000/admin/gmail/callback")
    query = parse_qs(urlparse(oauth.authorization_url()).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert len(query["state"][0]) >= 32
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) >= 43
    assert "client_secret" not in query


@pytest.mark.asyncio
async def test_oauth_rejects_unknown_state_before_network() -> None:
    oauth = GmailOAuth("client", "secret", "http://localhost:8000/admin/gmail/callback")
    with pytest.raises(OAuthFlowError) as failure:
        await oauth.exchange("code", "unknown")
    assert failure.value.category == "oauth_state_invalid_or_expired"


@pytest.mark.parametrize(
    ("provider_code", "category"),
    [
        ("invalid_client", "token_exchange_invalid_client"),
        ("redirect_uri_mismatch", "token_exchange_redirect_mismatch"),
        ("invalid_grant", "token_exchange_upstream_http_error"),
        (None, "token_exchange_upstream_http_error"),
    ],
)
def test_token_endpoint_error_codes_have_safe_categories(
    provider_code: str | None, category: str
) -> None:
    assert classify_token_endpoint_error(provider_code).category == category


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "category"),
    [
        (
            httpx.Response(
                401, json={"error": "invalid_client", "error_description": "do not disclose"}
            ),
            "token_exchange_invalid_client",
        ),
        (
            httpx.Response(400, json={"error": "redirect_uri_mismatch"}),
            "token_exchange_redirect_mismatch",
        ),
        (httpx.Response(200, json={"access_token": "do-not-disclose"}), "refresh_token_missing"),
    ],
)
async def test_token_exchange_classifies_mock_google_responses(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response, category: str
) -> None:
    submitted: list[dict[str, str]] = []

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            submitted.append(kwargs["data"])  # type: ignore[arg-type]
            return response

    monkeypatch.setattr("app.email.oauth.httpx.AsyncClient", lambda **kwargs: FakeClient())
    oauth = GmailOAuth("client", "secret", "http://localhost:8000/admin/gmail/callback")
    state = parse_qs(urlparse(oauth.authorization_url()).query)["state"][0]
    with pytest.raises(OAuthFlowError) as failure:
        await oauth.exchange("authorization-code", state)
    assert failure.value.category == category
    assert len(submitted[0]["code_verifier"]) >= 64


def test_oauth_connect_is_a_post_only_state_change() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    class FakeOAuth:
        configured = True

        def authorization_url(self) -> str:
            return "https://accounts.google.com/o/oauth2/v2/auth?state=safe"

    app.state.gmail_oauth = FakeOAuth()
    app.state.gmail_enabled = True
    app.state.gmail_encryption_ready = True
    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/admin/gmail/connect").status_code == 405
        response = client.post("/admin/gmail/connect")
    assert response.status_code == 302
    assert response.headers["location"].startswith("https://accounts.google.com/")


def test_oauth_callback_stores_only_authenticated_ciphertext() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
    stored: list[str] = []

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            assert code == "authorization-code"
            assert state == "verified-state"
            return {"refresh_token": "refresh-token"}

    async def store(refresh_token: str) -> None:
        stored.append(cipher.protect(refresh_token))

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = store
    with TestClient(app) as client:
        response = client.get("/admin/gmail/callback?code=authorization-code&state=verified-state")
    assert response.status_code == 200
    assert stored and stored[0] != "refresh-token"
    assert cipher.reveal(stored[0]) == "refresh-token"
    assert "refresh-token" not in response.text


def test_oauth_callback_hides_token_when_secure_storage_is_unavailable() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            return {"refresh_token": "refresh-token"}

    async def unavailable_store(refresh_token: str) -> None:
        raise ValueError("APP_ENCRYPTION_KEY invalid: " + refresh_token)

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = unavailable_store
    with TestClient(app) as client:
        response = client.get("/admin/gmail/callback?code=code&state=state")
    assert response.status_code == 400
    assert "token_storage_error" in response.text
    assert "refresh-token" not in response.text


@pytest.mark.parametrize(
    "category",
    [
        "oauth_state_invalid_or_expired",
        "token_exchange_invalid_client",
        "token_exchange_redirect_mismatch",
        "token_exchange_upstream_http_error",
        "refresh_token_missing",
    ],
)
def test_oauth_callback_shows_safe_guidance_for_every_exchange_failure(category: str) -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            raise OAuthFlowError(category)  # type: ignore[arg-type]

    async def store(refresh_token: str) -> None:
        raise AssertionError("storage must not run after an exchange failure")

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = store
    with TestClient(app) as client:
        response = client.get("/admin/gmail/callback?code=authorization-code&state=state")
    assert response.status_code == 400
    assert category in response.text
    assert "authorization-code" not in response.text
