"""Environment-backed runtime settings."""

import re
from datetime import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, PostgresDsn, field_validator, model_validator
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
    database_url_file: Path | None = Field(default=None, validation_alias="DATABASE_URL_FILE")
    admin_sources_path: Path = Field(
        default=Path("config/sources.example.yaml"), validation_alias="ADMIN_SOURCES_PATH"
    )
    admin_models_path: Path = Field(
        default=Path("config/models.example.yaml"), validation_alias="ADMIN_MODELS_PATH"
    )
    admin_interests_path: Path = Field(
        default=Path("config/interests.example.yaml"), validation_alias="ADMIN_INTERESTS_PATH"
    )
    scheduler_enabled: bool = Field(default=False, validation_alias="SCHEDULER_ENABLED")
    scheduler_daily_time: str = Field(default="08:00", validation_alias="SCHEDULER_DAILY_TIME")
    gmail_enabled: bool = Field(default=False, validation_alias="GMAIL_ENABLED")
    gmail_client_id: str = Field(default="", validation_alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(default="", validation_alias="GMAIL_CLIENT_SECRET")
    gmail_client_secret_file: Path | None = Field(
        default=None, validation_alias="GMAIL_CLIENT_SECRET_FILE"
    )
    gmail_oauth_redirect_uri: str = Field(
        default="http://localhost:8000/admin/gmail/callback",
        validation_alias="GMAIL_OAUTH_REDIRECT_URI",
    )
    gmail_initial_lookback_hours: int = Field(
        default=48, validation_alias="GMAIL_INITIAL_LOOKBACK_HOURS", ge=1, le=168
    )
    gmail_initial_max_messages: int = Field(
        default=25, validation_alias="GMAIL_INITIAL_MAX_MESSAGES", ge=1, le=100
    )
    gmail_request_timeout_seconds: float = Field(
        default=15, validation_alias="GMAIL_REQUEST_TIMEOUT_SECONDS", gt=0, le=60
    )
    gmail_max_retries: int = Field(default=2, validation_alias="GMAIL_MAX_RETRIES", ge=0, le=3)
    app_encryption_key: str = Field(default="", validation_alias="APP_ENCRYPTION_KEY")
    app_encryption_key_file: Path | None = Field(
        default=None, validation_alias="APP_ENCRYPTION_KEY_FILE"
    )
    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_api_key_file: Path | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY_FILE"
    )
    agent_api_enabled: bool = Field(default=False, validation_alias="AGENT_API_ENABLED")
    agent_api_token: str = Field(default="", validation_alias="AGENT_API_TOKEN")
    agent_api_token_file: Path | None = Field(
        default=None, validation_alias="AGENT_API_TOKEN_FILE"
    )
    agent_api_rate_limit_per_minute: int = Field(
        default=30, validation_alias="AGENT_API_RATE_LIMIT_PER_MINUTE", ge=1, le=120
    )
    agent_api_max_request_bytes: int = Field(
        default=2_048, validation_alias="AGENT_API_MAX_REQUEST_BYTES", ge=256, le=32_768
    )
    agent_api_max_response_bytes: int = Field(
        default=65_536, validation_alias="AGENT_API_MAX_RESPONSE_BYTES", ge=1_024, le=262_144
    )
    admin_auth_enabled: bool = Field(default=False, validation_alias="ADMIN_AUTH_ENABLED")
    admin_username: str = Field(default="", validation_alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    admin_password_file: Path | None = Field(default=None, validation_alias="ADMIN_PASSWORD_FILE")
    admin_public_origin: str = Field(default="", validation_alias="ADMIN_PUBLIC_ORIGIN")
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,testserver", validation_alias="ALLOWED_HOSTS"
    )
    force_https: bool = Field(default=False, validation_alias="FORCE_HTTPS")
    allow_private_source_urls: bool = Field(
        default=True, validation_alias="ALLOW_PRIVATE_SOURCE_URLS"
    )
    allow_insecure_source_urls: bool = Field(
        default=True, validation_alias="ALLOW_INSECURE_SOURCE_URLS"
    )
    article_request_timeout_seconds: float = Field(
        default=12, validation_alias="ARTICLE_REQUEST_TIMEOUT_SECONDS", gt=0, le=60
    )
    article_max_response_bytes: int = Field(
        default=3_000_000, validation_alias="ARTICLE_MAX_RESPONSE_BYTES", ge=32_768, le=10_000_000
    )
    article_max_retries: int = Field(default=1, validation_alias="ARTICLE_MAX_RETRIES", ge=0, le=3)
    ntfy_enabled: bool = Field(default=False, validation_alias="NTFY_ENABLED")
    ntfy_base_url: str = Field(default="", validation_alias="NTFY_BASE_URL")
    ntfy_topic: str = Field(default="", validation_alias="NTFY_TOPIC")
    ntfy_token: str = Field(default="", validation_alias="NTFY_TOKEN")
    ntfy_token_file: Path | None = Field(default=None, validation_alias="NTFY_TOKEN_FILE")
    ntfy_allow_public_topic: bool = Field(default=False, validation_alias="NTFY_ALLOW_PUBLIC_TOPIC")
    ntfy_request_timeout_seconds: float = Field(
        default=10, validation_alias="NTFY_REQUEST_TIMEOUT_SECONDS", gt=0, le=30
    )
    ntfy_max_retries: int = Field(default=1, validation_alias="NTFY_MAX_RETRIES", ge=0, le=3)

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("APP_TIMEZONE must be an IANA timezone") from error
        return value

    @field_validator("scheduler_daily_time")
    @classmethod
    def validate_scheduler_daily_time(cls, value: str) -> str:
        try:
            parsed = time.fromisoformat(value)
        except ValueError as error:
            raise ValueError("SCHEDULER_DAILY_TIME must use HH:MM") from error
        if parsed.second or parsed.microsecond:
            raise ValueError("SCHEDULER_DAILY_TIME must use HH:MM")
        return f"{parsed.hour:02d}:{parsed.minute:02d}"

    @field_validator("admin_public_origin")
    @classmethod
    def validate_admin_public_origin(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("ADMIN_PUBLIC_ORIGIN must be an absolute http(s) origin")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("ADMIN_PUBLIC_ORIGIN must not include credentials, a path, or query")
        return f"{parsed.scheme}://{parsed.netloc}"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Fail closed when a production process would expose its admin surface."""
        if self.ntfy_enabled:
            parsed_ntfy = urlsplit(self.ntfy_base_url)
            valid_ntfy_origin = (
                parsed_ntfy.scheme == "https"
                and bool(parsed_ntfy.netloc)
                and parsed_ntfy.path in {"", "/"}
            )
            if not valid_ntfy_origin:
                raise ValueError("NTFY_BASE_URL must be an HTTPS origin when NTFY_ENABLED=true")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.ntfy_topic):
                raise ValueError("NTFY_TOPIC must be a simple topic name when NTFY_ENABLED=true")
            if len(self.ntfy_token_value) < 12:
                raise ValueError("NTFY_TOKEN(_FILE) is required when NTFY_ENABLED=true")
            if parsed_ntfy.hostname in {"ntfy.sh", "www.ntfy.sh"} and (
                not self.ntfy_allow_public_topic or len(self.ntfy_topic) < 24
            ):
                raise ValueError(
                    "public ntfy.sh requires NTFY_ALLOW_PUBLIC_TOPIC=true and a 24+ character topic"
                )
        if self.agent_api_enabled and len(self.agent_api_token_value) < 24:
            raise ValueError(
                "AGENT_API_TOKEN(_FILE) must contain at least 24 characters when enabled"
            )
        if self.app_env.casefold() != "production":
            return self
        if not self.admin_auth_enabled:
            raise ValueError("ADMIN_AUTH_ENABLED=true is required when APP_ENV=production")
        if not self.admin_username.strip() or not self.admin_password_value:
            raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD(_FILE) are required in production")
        if len(self.admin_password_value) < 16:
            raise ValueError("ADMIN_PASSWORD must be at least 16 characters in production")
        hosts = self.allowed_host_list
        if not hosts or "*" in hosts:
            raise ValueError("ALLOWED_HOSTS must be an explicit production host allow-list")
        if not self.admin_public_origin:
            raise ValueError("ADMIN_PUBLIC_ORIGIN is required when APP_ENV=production")
        origin = urlsplit(self.admin_public_origin)
        if origin.scheme != "https" or origin.hostname not in hosts:
            raise ValueError(
                "ADMIN_PUBLIC_ORIGIN must use HTTPS and match ALLOWED_HOSTS in production"
            )
        redirect = urlsplit(self.gmail_oauth_redirect_uri)
        if self.gmail_enabled and (
            redirect.scheme != "https" or redirect.hostname not in hosts or redirect.query
        ):
            raise ValueError(
                "GMAIL_OAUTH_REDIRECT_URI must use HTTPS and an ALLOWED_HOSTS host in production"
            )
        if self.allow_private_source_urls or self.allow_insecure_source_urls:
            raise ValueError(
                "production requires ALLOW_PRIVATE_SOURCE_URLS=false and "
                "ALLOW_INSECURE_SOURCE_URLS=false"
            )
        return self

    @property
    def database_url_string(self) -> str:
        """Return the normalized SQLAlchemy connection URL without exposing it in logs."""
        if self.database_url_file is not None:
            return self._secret_or_file("", self.database_url_file)
        return str(self.database_url)

    @property
    def gmail_client_secret_value(self) -> str:
        """Return the OAuth secret from an environment value or mounted secret file."""
        return self._secret_or_file(self.gmail_client_secret, self.gmail_client_secret_file)

    @property
    def app_encryption_key_value(self) -> str:
        """Return the Fernet key without ever rendering it in diagnostics."""
        return self._secret_or_file(self.app_encryption_key, self.app_encryption_key_file)

    @property
    def openrouter_api_key_value(self) -> str:
        """Return the OpenRouter credential from an environment value or secret file."""
        return self._secret_or_file(self.openrouter_api_key, self.openrouter_api_key_file)

    @property
    def agent_api_token_value(self) -> str:
        """Return the dedicated Agent API secret only for constant-time request verification."""
        return self._secret_or_file(self.agent_api_token, self.agent_api_token_file)

    @property
    def admin_password_value(self) -> str:
        """Return the admin password only for constant-time request verification."""
        return self._secret_or_file(self.admin_password, self.admin_password_file)

    @property
    def ntfy_token_value(self) -> str:
        """Return the ntfy publishing token only when constructing its outbound request."""
        return self._secret_or_file(self.ntfy_token, self.ntfy_token_file)

    @property
    def allowed_host_list(self) -> list[str]:
        """Return normalized host allow-list entries for TrustedHost middleware."""
        return [
            entry.strip().casefold() for entry in self.allowed_hosts.split(",") if entry.strip()
        ]

    def logging_secret_values(self) -> tuple[str, ...]:
        """Supply known secret values to log redaction without exposing them elsewhere."""
        return tuple(
            value
            for value in (
                self.openrouter_api_key_value,
                self.gmail_client_secret_value,
                self.app_encryption_key_value,
                self.admin_password_value,
                self.agent_api_token_value,
                self.ntfy_token_value,
            )
            if value
        )

    @staticmethod
    def _secret_or_file(value: str, path: Path | None) -> str:
        if path is None:
            return value.strip()
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_file() or resolved.stat().st_size > 16_384:
                raise ValueError("invalid secret file")
            return resolved.read_text(encoding="utf-8").strip()
        except (OSError, ValueError) as error:
            raise ValueError("configured secret file is unavailable or invalid") from error


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
