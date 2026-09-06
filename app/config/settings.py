"""Environment-backed runtime settings."""

from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or a local ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_timezone: str = Field(default="Europe/Istanbul", validation_alias="APP_TIMEZONE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5433/intelligence",
        validation_alias="DATABASE_URL",
    )

    @property
    def database_url_string(self) -> str:
        """Return the normalized SQLAlchemy connection URL without exposing it in logs."""
        return str(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
