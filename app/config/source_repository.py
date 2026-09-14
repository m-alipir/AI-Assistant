"""Canonical database-managed sources with a one-time YAML bootstrap path."""

from __future__ import annotations

import json
import re
import uuid
from typing import Literal
from urllib.parse import parse_qs, urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config.sources import RssSourceConfig, SourceCatalog, SourceDefaults, YouTubeSourceConfig
from app.ingestion.schemas import SourceStream

SourceKind = Literal["rss", "youtube"]
_YOUTUBE_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_MANAGED_COLUMNS = (
    "id, kind, name, canonical_endpoint, stream, enabled, priority, category, language, "
    "freshness_hours, health_status, last_attempt_at, last_success_at, consecutive_failures, "
    "last_error_category, next_retry_at, last_successful_strategy, detected_language, "
    "created_at, updated_at"
)


class SourceRepositoryError(RuntimeError):
    """Base class for safe managed-source repository failures."""


class SourceAlreadyExists(SourceRepositoryError):
    """The canonical source endpoint is already managed."""


class SourceNotFound(SourceRepositoryError):
    """The requested managed source does not exist."""


class EnabledSourceDeleteBlocked(SourceRepositoryError):
    """Enabled sources must be disabled before they can be deleted."""


class ManagedSourceCreate(BaseModel):
    """Validated metadata accepted at the managed-source persistence boundary."""

    kind: SourceKind
    name: str = Field(min_length=1, max_length=256)
    endpoint: str = Field(min_length=1, max_length=2048)
    stream: SourceStream = SourceStream.TECH
    enabled: bool = False
    priority: int = Field(default=0, ge=-100, le=100)
    category: str | None = Field(default=None, max_length=128)
    language: Literal["tr", "en"] | None = None
    freshness_hours: int | None = Field(default=None, ge=1, le=720)

    @field_validator("name", "category")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def canonicalize_and_validate(self) -> ManagedSourceCreate:
        self.endpoint = canonicalize_endpoint(self.kind, self.endpoint)
        if self.kind == "rss" and self.language is not None:
            raise ValueError("language preference is supported only for YouTube sources")
        return self


class ManagedSourceUpdate(BaseModel):
    """Patchable managed-source metadata; omitted fields remain unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=256)
    endpoint: str | None = Field(default=None, min_length=1, max_length=2048)
    stream: SourceStream | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)
    category: str | None = Field(default=None, max_length=128)
    language: Literal["tr", "en"] | None = None
    freshness_hours: int | None = Field(default=None, ge=1, le=720)

    @field_validator("name", "category")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def reject_null_for_required_columns(self) -> ManagedSourceUpdate:
        required = {"name", "endpoint", "stream", "enabled", "priority"}
        has_null = any(
            field in self.model_fields_set and getattr(self, field) is None for field in required
        )
        if has_null:
            raise ValueError("required source fields cannot be null")
        return self


def canonicalize_endpoint(kind: SourceKind, endpoint: str) -> str:
    """Return the stable endpoint identity used by the database uniqueness constraint."""
    value = endpoint.strip()
    if kind == "youtube":
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme.casefold() != "https" or (parsed.hostname or "").casefold() not in {
                "youtube.com",
                "www.youtube.com",
            }:
                raise ValueError("YouTube source must be a channel ID or official Atom feed URL")
            if parsed.path.rstrip("/") != "/feeds/videos.xml":
                raise ValueError("YouTube source URL must be the official channel Atom feed")
            values = parse_qs(parsed.query, keep_blank_values=True).get("channel_id", [])
            if len(values) != 1:
                raise ValueError("YouTube Atom feed must contain exactly one channel_id")
            value = values[0]
        if not _YOUTUBE_CHANNEL_ID.fullmatch(value):
            raise ValueError("invalid YouTube channel ID")
        return value

    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("RSS endpoint must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("RSS endpoint must not contain credentials")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("RSS endpoint contains an invalid port") from error
    host = parsed.hostname.casefold()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    default_port = (parsed.scheme.casefold() == "http" and port == 80) or (
        parsed.scheme.casefold() == "https" and port == 443
    )
    netloc = host if port is None or default_port else f"{host}:{port}"
    return urlunsplit((parsed.scheme.casefold(), netloc, parsed.path or "/", parsed.query, ""))


class SourceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def bootstrap_yaml(self, seed: SourceCatalog) -> bool:
        """Explicitly seed a pristine database once; existing rows are never changed."""
        async with self._sessions.begin() as session:
            completed = await session.scalar(
                text("SELECT completed_at FROM managed_source_bootstrap WHERE id FOR UPDATE")
            )
            if completed is not None:
                return False
            if await session.scalar(text("SELECT 1 FROM managed_sources LIMIT 1")):
                await session.execute(
                    text("UPDATE managed_source_bootstrap SET completed_at = now() WHERE id")
                )
                return False
            for source in seed.rss:
                await self._insert_seed(
                    session,
                    kind="rss",
                    name=source.name,
                    endpoint=source.url,
                    stream=source.stream.value,
                    enabled=source.enabled,
                    language=None,
                    freshness_hours=source.freshness_hours,
                )
            for source in seed.youtube:
                await self._insert_seed(
                    session,
                    kind="youtube",
                    name=source.name,
                    endpoint=source.channel_id,
                    stream=source.stream.value,
                    enabled=source.enabled,
                    language=source.language,
                    freshness_hours=source.freshness_hours,
                )
            await session.execute(
                text(
                    "UPDATE managed_source_bootstrap SET completed_at = now(), "
                    "defaults = CAST(:defaults AS json) WHERE id"
                ),
                {"defaults": json.dumps(seed.defaults.model_dump(mode="json"))},
            )
        return True

    async def needs_yaml_bootstrap(self) -> bool:
        """Claim the explicit lifecycle or mark pre-existing database sources complete."""
        async with self._sessions.begin() as session:
            completed = await session.scalar(
                text("SELECT completed_at FROM managed_source_bootstrap WHERE id FOR UPDATE")
            )
            if completed is not None:
                return False
            if not await session.scalar(text("SELECT 1 FROM managed_sources LIMIT 1")):
                return True
            await session.execute(
                text("UPDATE managed_source_bootstrap SET completed_at = now() WHERE id")
            )
            return False

    async def load_catalog(self) -> SourceCatalog:
        """Load runtime sources exclusively from the database."""
        async with self._sessions() as session:
            defaults = await session.scalar(
                text("SELECT defaults FROM managed_source_bootstrap WHERE id")
            )
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT id, kind, name, canonical_endpoint, stream, enabled, language, "
                            "freshness_hours FROM managed_sources ORDER BY created_at, id"
                        )
                    )
                )
                .mappings()
                .all()
            )
        default_values = json.loads(defaults) if isinstance(defaults, str) else defaults or {}
        return SourceCatalog(
            defaults=SourceDefaults.model_validate(default_values),
            rss=[
                RssSourceConfig(
                    name=str(row["name"]),
                    url=str(row["canonical_endpoint"]),
                    stream=str(row["stream"]),
                    enabled=bool(row["enabled"]),
                    freshness_hours=row["freshness_hours"],
                    managed_source_id=str(row["id"]),
                )
                for row in rows
                if row["kind"] == "rss"
            ],
            youtube=[
                YouTubeSourceConfig(
                    name=str(row["name"]),
                    channel_id=str(row["canonical_endpoint"]),
                    stream=str(row["stream"]),
                    enabled=bool(row["enabled"]),
                    language=row["language"],
                    freshness_hours=row["freshness_hours"],
                    managed_source_id=str(row["id"]),
                )
                for row in rows
                if row["kind"] == "youtube"
            ],
        )

    async def list(self) -> list[dict[str, object]]:
        async with self._sessions() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            f"SELECT {_MANAGED_COLUMNS} FROM managed_sources "
                            "ORDER BY created_at, id"
                        )
                    )
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows]

    async def get(self, source_id: str) -> dict[str, object] | None:
        async with self._sessions() as session:
            row = (
                (
                    await session.execute(
                        text(f"SELECT {_MANAGED_COLUMNS} FROM managed_sources WHERE id = :id"),
                        {"id": source_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
        return dict(row) if row is not None else None

    async def create(self, source: ManagedSourceCreate) -> dict[str, object]:
        source_id = str(uuid.uuid4())
        columns = (
            "id, kind, name, canonical_endpoint, stream, enabled, priority, category, language, "
            "freshness_hours"
        )
        try:
            async with self._sessions.begin() as session:
                row = (
                    (
                        await session.execute(
                            text(
                                f"INSERT INTO managed_sources ({columns}) VALUES "
                                "(:id, :kind, :name, :endpoint, :stream, :enabled, :priority, "
                                f":category, :language, :freshness) RETURNING {_MANAGED_COLUMNS}"
                            ),
                            {
                                "id": source_id,
                                "kind": source.kind,
                                "name": source.name,
                                "endpoint": source.endpoint,
                                "stream": source.stream.value,
                                "enabled": source.enabled,
                                "priority": source.priority,
                                "category": source.category,
                                "language": source.language,
                                "freshness": source.freshness_hours,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
        except IntegrityError as error:
            raise SourceAlreadyExists("source endpoint is already managed") from error
        return dict(row)

    async def update(
        self, source_id: str, update: ManagedSourceUpdate
    ) -> dict[str, object]:
        values = update.model_dump(exclude_unset=True)
        async with self._sessions.begin() as session:
            current = (
                (
                    await session.execute(
                        text("SELECT kind FROM managed_sources WHERE id = :id FOR UPDATE"),
                        {"id": source_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if current is None:
                raise SourceNotFound("managed source not found")
            kind: SourceKind = current["kind"]
            if "endpoint" in values:
                values["canonical_endpoint"] = canonicalize_endpoint(kind, values.pop("endpoint"))
            if "stream" in values and values["stream"] is not None:
                values["stream"] = values["stream"].value
            if kind == "rss" and values.get("language") is not None:
                raise ValueError("language preference is supported only for YouTube sources")
            if not values:
                existing = await session.execute(
                    text(f"SELECT {_MANAGED_COLUMNS} FROM managed_sources WHERE id = :id"),
                    {"id": source_id},
                )
                return dict(existing.mappings().one())
            assignments = ", ".join(f"{column} = :{column}" for column in values)
            try:
                result = await session.execute(
                    text(
                        f"UPDATE managed_sources SET {assignments}, updated_at = now() "
                        f"WHERE id = :id RETURNING {_MANAGED_COLUMNS}"
                    ),
                    {"id": source_id, **values},
                )
                row = result.mappings().one()
            except IntegrityError as error:
                raise SourceAlreadyExists("source endpoint is already managed") from error
        return dict(row)

    async def set_enabled(self, source_id: str, enabled: bool) -> bool:
        async with self._sessions.begin() as session:
            changed = await session.scalar(
                text(
                    "UPDATE managed_sources SET enabled = :enabled, updated_at = now() "
                    "WHERE id = :id RETURNING id"
                ),
                {"id": source_id, "enabled": enabled},
            )
        return changed is not None

    async def delete(self, source_id: str) -> None:
        """Delete only a disabled source so an accidental request cannot stop production input."""
        async with self._sessions.begin() as session:
            deleted = await session.scalar(
                text("DELETE FROM managed_sources WHERE id = :id AND NOT enabled RETURNING id"),
                {"id": source_id},
            )
            if deleted is not None:
                return
            exists = await session.scalar(
                text("SELECT enabled FROM managed_sources WHERE id = :id"), {"id": source_id}
            )
            if exists is None:
                raise SourceNotFound("managed source not found")
            raise EnabledSourceDeleteBlocked("disable the source before deleting it")

    async def record_success(
        self,
        source_id: str,
        *,
        strategy: str,
        detected_language: str | None = None,
    ) -> bool:
        async with self._sessions.begin() as session:
            changed = await session.scalar(
                text(
                    "UPDATE managed_sources SET health_status = 'healthy', "
                    "last_attempt_at = now(), last_success_at = now(), consecutive_failures = 0, "
                    "last_error_category = NULL, "
                    "next_retry_at = NULL, last_successful_strategy = :strategy, "
                    "detected_language = coalesce(:language, detected_language), "
                    "updated_at = now() "
                    "WHERE id = :id RETURNING id"
                ),
                {"id": source_id, "strategy": strategy, "language": detected_language},
            )
        return changed is not None

    async def record_failure(self, source_id: str, *, error_category: str) -> bool:
        """Persist bounded exponential cooldown without retaining provider/source payloads."""
        async with self._sessions.begin() as session:
            changed = await session.scalar(
                text(
                    "UPDATE managed_sources SET health_status = CASE "
                    "WHEN consecutive_failures >= 2 "
                    "THEN 'unhealthy' ELSE 'degraded' END, last_attempt_at = now(), "
                    "consecutive_failures = consecutive_failures + 1, "
                    "last_error_category = :error, "
                    "next_retry_at = now() + make_interval(mins => LEAST(360, "
                    "15 * POWER(2, LEAST(consecutive_failures, 5)))::int), updated_at = now() "
                    "WHERE id = :id RETURNING id"
                ),
                {"id": source_id, "error": error_category},
            )
        return changed is not None

    async def _insert_seed(
        self,
        session: AsyncSession,
        *,
        kind: SourceKind,
        name: str,
        endpoint: str,
        stream: str,
        enabled: bool,
        language: str | None,
        freshness_hours: int | None,
    ) -> None:
        try:
            canonical_endpoint = canonicalize_endpoint(kind, endpoint)
        except ValueError:
            if enabled:
                raise
            canonical_endpoint = endpoint.strip()
        await session.execute(
            text(
                "INSERT INTO managed_sources (id, kind, name, canonical_endpoint, stream, enabled, "
                "language, freshness_hours) VALUES (:id, :kind, :name, :endpoint, :stream, "
                ":enabled, :language, :freshness) "
                "ON CONFLICT (kind, canonical_endpoint) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "kind": kind,
                "name": name.strip(),
                "endpoint": canonical_endpoint,
                "stream": stream,
                "enabled": enabled,
                "language": language,
                "freshness": freshness_hours,
            },
        )
