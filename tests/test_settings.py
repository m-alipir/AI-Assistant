from app.config.settings import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_timezone == "Europe/Istanbul"
    assert settings.database_url_string == "postgresql+asyncpg://postgres:postgres@localhost:5433/intelligence"


def test_settings_read_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:password@db:5432/service")

    settings = Settings(_env_file=None)

    assert settings.database_url_string == "postgresql+asyncpg://user:password@db:5432/service"
