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
