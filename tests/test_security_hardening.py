"""Offline regressions for production access and outbound-content hardening."""

import base64
import logging
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.collectors.rss import _validate_remote_url
from app.config.settings import Settings
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


def test_production_compose_keeps_database_private_and_app_least_privileged() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8"))
    app = compose["services"]["app"]
    db = compose["services"]["db"]
    assert app["ports"] == ["127.0.0.1:8000:8000"]
    assert app["read_only"] is True
    assert "ALL" in app["cap_drop"]
    assert "no-new-privileges:true" in app["security_opt"]
    assert db["networks"] == ["backend"]
    assert compose["networks"]["backend"]["internal"] is True
