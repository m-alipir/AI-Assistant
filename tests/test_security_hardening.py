"""Offline regressions for production access and outbound-content hardening."""

import base64
import logging
import ssl
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.collectors.rss import _validate_connected_peer, _validate_remote_url
from app.config.settings import Settings
from app.db.session import create_engine
from app.main import create_app
from app.observability.logging import JsonFormatter
from app.providers.contracts import ProviderError

PROJECT_ROOT = Path(__file__).parents[1]


def _production_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="production",
        admin_auth_enabled=True,
        admin_username="operator",
        admin_password="a-long-test-password",
        admin_public_origin="https://admin.example.test",
        allowed_hosts="admin.example.test",
        allow_private_source_urls=False,
        allow_insecure_source_urls=False,
    )


def _basic_header() -> str:
    encoded = base64.b64encode(b"operator:a-long-test-password").decode("ascii")
    return f"Basic {encoded}"


def test_production_admin_is_authenticated_and_mutations_require_same_origin() -> None:
    app = create_app(
        settings=_production_settings(),
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    app.state.run_callback = lambda: {"status": "completed", "counts": {}, "message": "ok"}
    with TestClient(app, base_url="https://admin.example.test") as client:
        assert client.post("/admin/run-now").status_code == 401
        assert client.post(
            "/admin/run-now", headers={"Authorization": _basic_header(), "Origin": "https://evil.test"}
        ).status_code == 403
        response = client.post(
            "/admin/run-now",
            headers={"Authorization": _basic_header(), "Origin": "https://admin.example.test"},
        )
        health = client.get("/health")
        assert response.status_code == 200
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["content-security-policy"].startswith("default-src 'self'")


def test_admin_csp_uses_per_response_nonces_without_inline_handlers() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    with TestClient(app) as client:
        first = client.get("/admin")
        second = client.get("/admin")
    first_csp = first.headers["content-security-policy"]
    second_csp = second.headers["content-security-policy"]
    assert "unsafe-inline" not in first_csp
    assert "onclick=" not in first.text
    assert "nonce-" in first_csp
    assert first_csp != second_csp
    nonce = first_csp.split("script-src 'self' 'nonce-", 1)[1].split("'", 1)[0]
    assert f'nonce="{nonce}"' in first.text


def test_untrusted_host_never_becomes_an_https_redirect_target() -> None:
    app = create_app(
        settings=_production_settings().model_copy(update={"force_https": True}),
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    with TestClient(app, base_url="http://admin.example.test", follow_redirects=False) as client:
        response = client.get("/not-found", headers={"Host": "evil.example"})
    assert response.status_code == 400
    assert "location" not in response.headers


def test_forwarded_https_is_accepted_only_from_a_trusted_proxy() -> None:
    app = create_app(
        settings=_production_settings().model_copy(update={"force_https": True}),
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    with TestClient(
        app,
        base_url="http://admin.example.test",
        follow_redirects=False,
        client=("203.0.113.10", 50000),
    ) as client:
        untrusted = client.get("/not-found?x=1", headers={"X-Forwarded-Proto": "https"})
    assert untrusted.status_code == 307
    assert untrusted.headers["location"] == "https://admin.example.test/not-found?x=1"

    with TestClient(
        app,
        base_url="http://admin.example.test",
        follow_redirects=False,
        client=("127.0.0.1", 50000),
    ) as client:
        trusted = client.get("/not-found", headers={"X-Forwarded-Proto": "https"})
    assert trusted.status_code == 404


def test_admin_failed_authentication_is_process_limited() -> None:
    settings = _production_settings().model_copy(update={"admin_auth_rate_limit_per_minute": 1})
    app = create_app(
        settings=settings,
        readiness_check=lambda: __import__("asyncio").sleep(0, result=True),
    )
    with TestClient(app, base_url="https://admin.example.test") as client:
        assert client.get("/admin").status_code == 401
        assert client.get("/admin").status_code == 429


def test_production_configuration_fails_closed_without_admin_protection() -> None:
    with pytest.raises(ValidationError, match="ADMIN_AUTH_ENABLED"):
        Settings(_env_file=None, app_env="production")


def test_production_configuration_rejects_insecure_source_access() -> None:
    with pytest.raises(ValidationError, match="ALLOW_PRIVATE_SOURCE_URLS"):
        Settings(
            _env_file=None,
            app_env="production",
            admin_auth_enabled=True,
            admin_username="operator",
            admin_password="a-long-test-password",
            admin_public_origin="https://admin.example.test",
            allowed_hosts="admin.example.test",
        )


def test_remote_production_database_uses_hostname_verifying_tls(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.db.session.create_async_engine", fake_engine)
    settings = _production_settings().model_copy(
        update={
            "database_url": "postgresql+asyncpg://runtime:secret@db.example.test/intelligence"
        }
    )
    create_engine(settings)
    context = captured["connect_args"]["ssl"]  # type: ignore[index]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_remote_production_database_cannot_explicitly_disable_tls() -> None:
    with pytest.raises(ValidationError, match="cannot disable TLS"):
        Settings(
            _env_file=None,
            app_env="production",
            admin_auth_enabled=True,
            admin_username="operator",
            admin_password="a-long-test-password",
            admin_public_origin="https://admin.example.test",
            allowed_hosts="admin.example.test",
            allow_private_source_urls=False,
            allow_insecure_source_urls=False,
            database_url=(
                "postgresql+asyncpg://runtime:secret@db.example.test/intelligence?sslmode=disable"
            ),
        )


def test_secret_file_precedes_environment_value_without_rendering_it(tmp_path: Path) -> None:
    password_file = tmp_path / "admin-password"
    password_file.write_text("file-secret-password", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        admin_password="environment-secret-password",
        admin_password_file=password_file,
    )
    assert settings.admin_password_value == "file-secret-password"


def test_outbound_feed_validation_rejects_http_and_private_networks(monkeypatch) -> None:
    with pytest.raises(ProviderError, match="HTTPS"):
        _validate_remote_url(
            "http://feeds.example.test/feed.xml",
            allow_private_hosts=False,
            allow_insecure_http=False,
        )
    monkeypatch.setattr(
        "app.collectors.rss.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(ProviderError, match="non-public"):
        _validate_remote_url(
            "https://feeds.example.test/feed.xml",
            allow_private_hosts=False,
            allow_insecure_http=False,
        )


def test_connected_peer_validation_blocks_dns_rebinding_destination() -> None:
    class NetworkStream:
        def get_extra_info(self, name: str):
            assert name == "server_addr"
            return ("127.0.0.1", 443)

    response = type("Response", (), {"extensions": {"network_stream": NetworkStream()}})()
    with pytest.raises(ProviderError, match="non-public"):
        _validate_connected_peer(response, allow_private_hosts=False)  # type: ignore[arg-type]


def test_log_formatter_redacts_known_and_common_credentials() -> None:
    formatter = JsonFormatter(secrets=("very-secret-value",))
    record = logging.LogRecord(
        "test", logging.WARNING, __file__, 1,
        "token=abc bearer very-secret-value access_token=xyz", (), None
    )
    rendered = formatter.format(record)
    assert "very-secret-value" not in rendered
    assert "access_token=xyz" not in rendered
    assert "[REDACTED]" in rendered


def test_log_formatter_redacts_postgres_password_without_configured_secret() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "connect postgresql+asyncpg://runtime:database-secret@db.example.test/intelligence",
        (),
        None,
    )
    rendered = formatter.format(record)
    assert "database-secret" not in rendered
    assert "runtime:[REDACTED]@" in rendered


def test_production_secret_file_must_be_absolute_and_outside_workspace() -> None:
    settings = _production_settings()
    with pytest.raises(ValueError, match="unavailable or invalid"):
        settings._secret_or_file("", Path("config/local-secret"))


def test_production_compose_keeps_database_private_and_app_least_privileged() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]
    db = compose["services"]["db"]
    assert app["ports"] == ["127.0.0.1:8000:8000"]
    assert app["read_only"] is True
    assert "ALL" in app["cap_drop"]
    assert "no-new-privileges:true" in app["security_opt"]
    assert db["networks"] == ["backend"]
    assert "ALL" in db["cap_drop"]
    assert db["pids_limit"] == 256
    assert db["mem_limit"] == "1g"
    assert compose["networks"]["backend"]["internal"] is True


def test_production_separates_one_shot_migration_from_runtime_role() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]
    migrate = compose["services"]["migrate"]
    role_sql = (PROJECT_ROOT / "ops/bootstrap-database-roles.sql").read_text(encoding="utf-8")

    assert app["environment"]["DATABASE_URL_FILE"].endswith("database_runtime_url")
    assert migrate["environment"]["DATABASE_URL_FILE"].endswith("database_migration_url")
    assert migrate["command"] == ["alembic", "upgrade", "head"]
    assert app["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE" in role_sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE" in role_sql
    assert "GRANT CREATE" not in role_sql
