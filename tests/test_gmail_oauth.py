from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.email.core import TokenCipher
from app.email.oauth import GmailOAuth, OAuthFlowError, classify_token_endpoint_error
from app.email.telegram_link import TelegramGmailLinkIntents
from app.main import create_app


class _IntentResult:
    def __init__(self, scalar: object = None, row: dict[str, object] | None = None) -> None:
        self._scalar = scalar
        self._row = row

    def scalar_one_or_none(self) -> object:
        return self._scalar

    def mappings(self) -> "_IntentResult":
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self._row


class _IntentSessions:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    def begin(self) -> "_IntentSessions":
        return self

    async def __aenter__(self) -> "_IntentSessions":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: object, values: dict[str, object]) -> _IntentResult:
        query = " ".join(str(statement).lower().split())
        now = values.get("now", datetime.now(UTC))
        if query.startswith("delete from telegram_gmail_oauth_intents where expires_at"):
            self.rows = {
                key: row for key, row in self.rows.items() if row["expires_at"] > now
            }
            return _IntentResult()
        if query.startswith("insert into telegram_gmail_oauth_intents"):
            key = str(values["intent_hash"])
            self.rows[key] = {
                "actor_ciphertext": values["actor_ciphertext"],
                "oauth_state_hash": None,
                "consumed_at": None,
                "callback_claimed_at": None,
                "completed_at": None,
                "expires_at": values["expires_at"],
            }
            return _IntentResult()
        if "set consumed_at" in query:
            key = str(values["intent_hash"])
            row = self.rows.get(key)
            if (
                row
                and row["oauth_state_hash"] is None
                and row["consumed_at"] is None
                and row["expires_at"] > now
            ):
                row["consumed_at"] = now
                return _IntentResult(row["actor_ciphertext"])
            return _IntentResult()
        if "set oauth_state_hash" in query:
            key = str(values["intent_hash"])
            row = self.rows.get(key)
            if (
                row
                and row["consumed_at"] is not None
                and row["oauth_state_hash"] is None
                and row["expires_at"] > now
            ):
                row["oauth_state_hash"] = values["state_hash"]
                row["expires_at"] = values["expires_at"]
                return _IntentResult(key)
            return _IntentResult()
        if "set callback_claimed_at" in query:
            key = next(
                (
                    key
                    for key, row in self.rows.items()
                    if row["oauth_state_hash"] == values["state_hash"]
                ),
                None,
            )
            row = self.rows.get(key) if key else None
            if row and row["callback_claimed_at"] is None and row["expires_at"] > now:
                row["callback_claimed_at"] = now
                return _IntentResult(key)
            return _IntentResult()
        if query.startswith("select expires_at from telegram_gmail_oauth_intents"):
            row = next(
                (
                    row
                    for row in self.rows.values()
                    if row["oauth_state_hash"] == values["state_hash"]
                ),
                None,
            )
            return _IntentResult(row={"expires_at": row["expires_at"]} if row else None)
        if query.startswith("select actor_ciphertext from telegram_gmail_oauth_intents"):
            row = next(
                (
                    row
                    for row in self.rows.values()
                    if row["oauth_state_hash"] == values["state_hash"]
                ),
                None,
            )
            if row and row["callback_claimed_at"] is not None and row["completed_at"] is None:
                return _IntentResult(
                    row={"actor_ciphertext": row["actor_ciphertext"]}
                )
            return _IntentResult()
        if "set completed_at" in query:
            row = next(
                (
                    row
                    for row in self.rows.values()
                    if row["oauth_state_hash"] == values["state_hash"]
                ),
                None,
            )
            if row and row["callback_claimed_at"] is not None and row["completed_at"] is None:
                row["completed_at"] = now
                row["actor_ciphertext"] = None
            return _IntentResult()
        raise AssertionError("unexpected intent SQL")


def test_oauth_authorization_url_is_readonly_and_stateful() -> None:
    oauth = GmailOAuth("client", "secret", "http://localhost:8000/admin/gmail/callback")
    query = parse_qs(urlparse(oauth.authorization_url()).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert len(query["state"][0]) >= 32
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) >= 43
    assert "client_secret" not in query


@pytest.mark.asyncio
async def test_telegram_gmail_intent_is_encrypted_actor_bound_and_single_use() -> None:
    sessions = _IntentSessions()
    cipher = TokenCipher(Fernet.generate_key().decode("ascii"))
    intents = TelegramGmailLinkIntents(sessions, cipher)  # type: ignore[arg-type]
    token = await intents.issue(42, 42)
    row = next(iter(sessions.rows.values()))

    assert token not in sessions.rows
    assert "42" not in str(row["actor_ciphertext"])
    assert cipher.reveal(str(row["actor_ciphertext"])) == "[42,42]"
    assert await intents.claim("malformed") is None
    assert await intents.claim(token) == row["actor_ciphertext"]
    assert await intents.claim(token) is None

    state = "S" * 43
    assert await intents.bind(token, state)
    assert not await intents.bind(token, state)
    assert await intents.claim_oauth_state(state) == "active"
    assert await intents.claim_oauth_state(state) == "replayed"

    async def store(_: str) -> None:
        raise AssertionError("a denied OAuth exchange must not store a token")

    async def notify(actor: tuple[int, int], message: str) -> None:
        assert actor == (42, 42)
        assert "yeniden deneyin" in message

    assert await intents.complete(state, None, {(42, 42)}, store, notify) == "failed"
    assert await intents.claim_oauth_state(state) == "replayed"


@pytest.mark.asyncio
async def test_telegram_link_completion_rejects_mismatch_and_notifies_owner() -> None:
    sessions = _IntentSessions()
    intents = TelegramGmailLinkIntents(
        sessions, TokenCipher(Fernet.generate_key().decode("ascii"))  # type: ignore[arg-type]
    )
    stored: list[str] = []
    messages: list[tuple[tuple[int, int], str]] = []

    async def store(value: str) -> None:
        stored.append(value)

    async def notify(actor: tuple[int, int], message: str) -> None:
        messages.append((actor, message))

    token = await intents.issue(42, 42)
    await intents.claim(token)
    assert await intents.bind(token, "A" * 43)
    assert await intents.claim_oauth_state("A" * 43) == "active"
    assert (
        await intents.complete(
            "A" * 43, "refresh", {(42, 99)}, store, notify
        )
        == "unauthorized"
    )
    assert stored == [] and messages == []

    token = await intents.issue(43, 43)
    await intents.claim(token)
    assert await intents.bind(token, "B" * 43)
    assert await intents.claim_oauth_state("B" * 43) == "active"
    assert (
        await intents.complete(
            "B" * 43, "refresh", {(43, 43)}, store, notify
        )
        == "connected"
    )
    assert stored == ["refresh"]
    assert messages == [((43, 43), "Gmail hesabı bağlandı; erişim salt okunurdur.")]
    assert await intents.claim_oauth_state("B" * 43) == "replayed"


@pytest.mark.asyncio
async def test_telegram_gmail_oauth_intent_expires() -> None:
    sessions = _IntentSessions()
    intents = TelegramGmailLinkIntents(
        sessions, TokenCipher(Fernet.generate_key().decode("ascii"))  # type: ignore[arg-type]
    )
    token = await intents.issue(42, 42)
    await intents.claim(token)
    state = "E" * 43
    assert await intents.bind(token, state)
    next(iter(sessions.rows.values()))["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)

    assert await intents.claim_oauth_state(state) == "expired"


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


def test_telegram_gmail_connect_redirect_requires_single_use_intent_and_google_host() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    accepted = "I" * 43
    invalid = "J" * 43
    malicious_redirect = "K" * 43
    called: list[str] = []

    async def start(intent: str) -> str | None:
        called.append(intent)
        if intent == accepted:
            return "https://accounts.google.com/o/oauth2/v2/auth?state=state"
        if intent == invalid:
            return None
        return "https://accounts.google.com.evil.test/o/oauth2/v2/auth"

    app.state.start_telegram_gmail_oauth = start
    with TestClient(app, follow_redirects=False) as client:
        assert (
            client.get(f"/integrations/telegram/gmail/connect?intent={accepted}").status_code
            == 302
        )
        assert client.get(
            f"/integrations/telegram/gmail/connect?intent={invalid}"
        ).status_code == 404
        assert client.get(
            f"/integrations/telegram/gmail/connect?intent={malicious_redirect}"
        ).status_code == 404
    assert called == [accepted, invalid, malicious_redirect]


def test_admin_oauth_start_stays_protected_and_callback_accepts_only_oauth_state() -> None:
    settings = Settings(
        admin_auth_enabled=True,
        admin_username="operator",
        admin_password="long-test-password-value",
    )
    app = create_app(
        settings=settings,
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    stored: list[str] = []

    class FakeOAuth:
        configured = True

        async def exchange(self, code: str, state: str) -> dict[str, str]:
            if state != "verified-state":
                raise OAuthFlowError("oauth_state_invalid_or_expired")
            return {"refresh_token": "refresh"}

    async def store(refresh_token: str) -> None:
        stored.append(refresh_token)

    app.state.gmail_oauth = FakeOAuth()
    app.state.gmail_enabled = True
    app.state.gmail_encryption_ready = True
    app.state.store_gmail_token = store
    with TestClient(app) as client:
        assert client.post("/admin/gmail/connect").status_code == 401
        valid = client.get(
            "/admin/gmail/callback?code=code&state=verified-state"
        )
        invalid = client.get("/admin/gmail/callback?code=code&state=unknown-state")
    assert valid.status_code == 200
    assert invalid.status_code == 400
    assert stored == ["refresh"]


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


def test_telegram_oauth_callback_completes_bound_link_without_admin_account_store() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    completed: list[tuple[str, str | None]] = []

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            assert code == "authorization-code"
            assert state == "telegram-state"
            return {"refresh_token": "refresh-token"}

    async def finish(state: str, refresh_token: str | None) -> str:
        completed.append((state, refresh_token))
        return "connected"

    async def claim(state: str) -> str | None:
        return "active" if state == "telegram-state" else None

    async def store_admin_token(_: str) -> None:
        raise AssertionError("bound Telegram tokens use the actor-bound completion path")

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = store_admin_token
    app.state.claim_telegram_gmail_oauth = claim
    app.state.finish_telegram_gmail_oauth = finish
    with TestClient(app) as client:
        response = client.get(
            "/admin/gmail/callback?code=authorization-code&state=telegram-state"
        )

    assert response.status_code == 200
    assert "Telegram'a dönebilirsiniz." in response.text
    assert completed == [("telegram-state", "refresh-token")]


def test_replayed_telegram_callback_cannot_fall_through_to_admin_token_store() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    calls: list[str] = []

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            calls.append("exchange")
            return {"refresh_token": "refresh-token"}

    async def claim(_: str) -> str:
        return "replayed"

    async def store(_: str) -> None:
        calls.append("store")

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = store
    app.state.claim_telegram_gmail_oauth = claim
    with TestClient(app) as client:
        response = client.get("/admin/gmail/callback?code=code&state=telegram-state")

    assert response.status_code == 400
    assert calls == []


@pytest.mark.parametrize(
    ("claim_result", "finish_result", "expected_calls"),
    [
        ("expired", None, []),
        ("replayed", None, []),
        ("active", "unauthorized", ["exchange", "finish"]),
    ],
)
def test_denied_telegram_callback_never_falls_through_to_admin_token_store(
    claim_result: str, finish_result: str | None, expected_calls: list[str]
) -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    calls: list[str] = []

    class FakeOAuth:
        async def exchange(self, code: str, state: str) -> dict[str, str]:
            calls.append("exchange")
            return {"refresh_token": "refresh-token"}

    async def claim(_: str) -> str:
        return claim_result

    async def finish(_: str, refresh_token: str | None) -> str:
        assert refresh_token == "refresh-token"
        calls.append("finish")
        return finish_result or "failed"

    async def store_admin_token(_: str) -> None:
        calls.append("admin_store")

    app.state.gmail_oauth = FakeOAuth()
    app.state.store_gmail_token = store_admin_token
    app.state.claim_telegram_gmail_oauth = claim
    app.state.finish_telegram_gmail_oauth = finish
    with TestClient(app) as client:
        response = client.get("/admin/gmail/callback?code=code&state=telegram-state")

    assert response.status_code == 400
    assert calls == expected_calls
    assert "admin_store" not in calls


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
