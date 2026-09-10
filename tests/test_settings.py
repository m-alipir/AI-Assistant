import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_timezone == "Europe/Istanbul"
    assert settings.database_url_string == "postgresql+asyncpg://postgres:postgres@localhost:5433/intelligence"
    assert settings.gmail_initial_lookback_hours == 48
    assert settings.gmail_initial_max_messages == 25


def test_settings_read_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@db:5432/service")

    settings = Settings(_env_file=None)

    assert settings.database_url_string == "postgresql+asyncpg://user:password@db:5432/service"


def test_scheduler_configuration_requires_valid_timezone_and_hh_mm_time() -> None:
    assert Settings(_env_file=None, scheduler_daily_time="08:05").scheduler_daily_time == "08:05"
    with pytest.raises(ValidationError, match="APP_TIMEZONE"):
        Settings(_env_file=None, app_timezone="not/a-timezone")
    with pytest.raises(ValidationError, match="SCHEDULER_DAILY_TIME"):
        Settings(_env_file=None, scheduler_daily_time="08:00:30")


def test_ntfy_is_disabled_by_default_and_fails_closed_when_enabled() -> None:
    assert not Settings(_env_file=None).ntfy_enabled
    with pytest.raises(ValidationError, match="NTFY_BASE_URL"):
        Settings(
            _env_file=None,
            ntfy_enabled=True,
            ntfy_token="high-entropy-token-value-0123456789",
        )
    with pytest.raises(ValidationError, match="public ntfy.sh"):
        Settings(
            _env_file=None,
            ntfy_enabled=True,
            ntfy_base_url="https://ntfy.sh",
            ntfy_topic="short-topic",
            ntfy_token="high-entropy-token-value-0123456789",
        )
    settings = Settings(
        _env_file=None,
        ntfy_enabled=True,
        ntfy_base_url="https://ntfy.example.test",
        ntfy_topic="private_topic",
        ntfy_token="high-entropy-token-value-0123456789",
    )
    assert settings.ntfy_token_value == "high-entropy-token-value-0123456789"


def test_gmail_enabled_requires_client_credentials_and_valid_fernet_key() -> None:
    with pytest.raises(ValidationError, match="client credentials"):
        Settings(_env_file=None, gmail_enabled=True)
    with pytest.raises(ValidationError, match="APP_ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            gmail_enabled=True,
            gmail_client_id="client",
            gmail_client_secret="secret",
            app_encryption_key="not-a-fernet-key",
        )
