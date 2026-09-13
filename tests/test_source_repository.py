"""Managed-source validation plus opt-in real PostgreSQL persistence coverage."""

import os
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config.source_repository import (
    EnabledSourceDeleteBlocked,
    ManagedSourceCreate,
    ManagedSourceUpdate,
    SourceAlreadyExists,
    SourceRepository,
    canonicalize_endpoint,
)
from app.config.sources import RssSourceConfig
from app.ingestion.schemas import SourceStream


def test_canonicalize_rss_endpoint_removes_identity_noise() -> None:
    assert (
        canonicalize_endpoint("rss", " HTTPS://Example.COM:443/feed.xml?b=2&a=1#section ")
        == "https://example.com/feed.xml?b=2&a=1"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "feed.example.com/rss",
        "ftp://example.com/feed",
        "https://user:secret@example.com/feed",
        "https://example.com:bad/feed",
    ],
)
def test_canonicalize_rss_endpoint_rejects_unsafe_or_invalid_values(endpoint: str) -> None:
    with pytest.raises(ValueError):
        canonicalize_endpoint("rss", endpoint)


def test_canonicalize_youtube_atom_url_to_channel_identity() -> None:
    channel_id = "UCVBX2n_5egE9XuJL8NUS0Xg"
    assert (
        canonicalize_endpoint(
            "youtube", f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        )
        == channel_id
    )
    with pytest.raises(ValueError):
        canonicalize_endpoint("youtube", "https://example.com/feeds/videos.xml?channel_id=x")


def test_managed_source_models_enforce_kind_metadata_and_patch_nullability() -> None:
    with pytest.raises(ValidationError):
        ManagedSourceCreate(
            kind="rss",
            name="Feed",
            endpoint="https://example.com/feed",
            stream=SourceStream.TECH,
            language="en",
        )
    with pytest.raises(ValidationError):
        ManagedSourceUpdate(name=None)
    assert ManagedSourceUpdate(category=None).model_dump(exclude_unset=True) == {"category": None}


def test_managed_source_database_id_is_runtime_only() -> None:
    source = RssSourceConfig(
        name="Feed",
        url="https://example.com/feed",
        stream=SourceStream.TECH,
        managed_source_id="database-id",
    )
    assert source.managed_source_id == "database-id"
    assert "managed_source_id" not in source.model_dump()


DATABASE_URL = os.environ.get("MANAGED_SOURCE_INTEGRATION_DATABASE_URL")


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="set MANAGED_SOURCE_INTEGRATION_DATABASE_URL to a disposable migrated PostgreSQL DB",
)
@pytest.mark.asyncio
async def test_managed_source_crud_health_and_safe_delete_in_postgres() -> None:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = SourceRepository(sessions)
    suffix = uuid.uuid4().hex
    endpoint = f"https://example.test/{suffix}/feed.xml"
    source_id: str | None = None
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "20260913_0024"

        created = await repository.create(
            ManagedSourceCreate(
                kind="rss",
                name="Managed integration feed",
                endpoint=endpoint,
                stream=SourceStream.TECH,
                enabled=True,
                priority=10,
                category="technology",
                freshness_hours=24,
            )
        )
        source_id = str(created["id"])
        assert created["canonical_endpoint"] == endpoint
        assert (await repository.get(source_id))["priority"] == 10

        with pytest.raises(SourceAlreadyExists):
            await repository.create(
                ManagedSourceCreate(
                    kind="rss",
                    name="Canonical duplicate",
                    endpoint=endpoint + "#ignored",
                )
            )

        updated = await repository.update(
            source_id,
            ManagedSourceUpdate(name="Updated feed", category=None, freshness_hours=48),
        )
        assert updated["name"] == "Updated feed"
        assert updated["category"] is None

        await repository.record_failure(source_id, error_category="rss_feed_access_error")
        await repository.record_failure(source_id, error_category="rss_feed_access_error")
        await repository.record_failure(source_id, error_category="rss_feed_access_error")
        unhealthy = await repository.get(source_id)
        assert unhealthy is not None
        assert unhealthy["health_status"] == "unhealthy"
        assert unhealthy["consecutive_failures"] == 3
        assert unhealthy["last_error_category"] == "rss_feed_access_error"
        assert unhealthy["next_retry_at"] > unhealthy["last_attempt_at"]

        await repository.record_success(source_id, strategy="rss_atom")
        healthy = await repository.get(source_id)
        assert healthy is not None
        assert healthy["health_status"] == "healthy"
        assert healthy["consecutive_failures"] == 0
        assert healthy["last_error_category"] is None
        assert healthy["next_retry_at"] is None
        assert healthy["last_successful_strategy"] == "rss_atom"

        with pytest.raises(EnabledSourceDeleteBlocked):
            await repository.delete(source_id)
        assert await repository.set_enabled(source_id, False)
        await repository.delete(source_id)
        assert await repository.get(source_id) is None
        source_id = None
    finally:
        if source_id is not None:
            async with engine.begin() as connection:
                await connection.execute(
                    text("DELETE FROM managed_sources WHERE id = :id"), {"id": source_id}
                )
        await engine.dispose()
