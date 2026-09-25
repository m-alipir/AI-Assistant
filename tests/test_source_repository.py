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
from app.config.sources import RssSourceConfig, SourceCatalog, SourceDefaults
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


@pytest.mark.parametrize(
    ("endpoint", "expected_category"),
    [
        ("https://openai.com/news/rss.xml", "Technology > Artificial Intelligence"),
        ("https://feeds.arstechnica.com/arstechnica/index", "Technology"),
        ("https://www.sciencedaily.com/rss/top/science.xml", "Science"),
    ],
)
def test_managed_source_create_infers_only_clear_known_rss_categories(
    endpoint: str, expected_category: str
) -> None:
    source = ManagedSourceCreate(
        kind="rss", name="Known publisher", endpoint=endpoint, stream=SourceStream.WORLD
    )

    assert source.category == expected_category
    assert source.stream is SourceStream.WORLD


def test_managed_source_create_leaves_ambiguous_and_youtube_categories_pending() -> None:
    unknown = ManagedSourceCreate(
        kind="rss", name="Unknown publisher", endpoint="https://example.test/feed"
    )
    lookalike = ManagedSourceCreate(
        kind="rss",
        name="Lookalike publisher",
        endpoint="https://openai.com.example.test/feed",
    )
    youtube = ManagedSourceCreate(
        kind="youtube", name="Unknown channel", endpoint="UCVBX2n_5egE9XuJL8NUS0Xg"
    )
    explicit = ManagedSourceCreate(
        kind="rss",
        name="Named category",
        endpoint="https://example.test/another-feed",
        category="Research > Robotics",
    )

    assert unknown.category is None
    assert lookalike.category is None
    assert youtube.category is None
    assert explicit.category == "Research > Robotics"


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
        assert revision == "20260923_0028"

        created = await repository.create(
            ManagedSourceCreate(
                kind="rss",
                name="Managed integration feed",
                endpoint=endpoint,
                stream=SourceStream.WORLD,
                enabled=False,
                priority=10,
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
        assert (
            await repository.set_category_if_missing(source_id, "Research > Robotics")
            == "updated"
        )
        assert await repository.set_category_if_missing(source_id, "Science") == "already_set"
        assert await repository.set_category_if_missing(str(uuid.uuid4()), "Science") == "not_found"
        categorized = await repository.get(source_id)
        assert categorized is not None
        assert categorized["category"] == "Research > Robotics"
        assert categorized["enabled"] is False
        assert categorized["stream"] == SourceStream.WORLD.value

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

        assert await repository.set_enabled(source_id, True)
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


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="set MANAGED_SOURCE_INTEGRATION_DATABASE_URL to a disposable migrated PostgreSQL DB",
)
@pytest.mark.asyncio
async def test_yaml_bootstrap_is_one_time_and_runtime_catalog_is_database_only() -> None:
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = SourceRepository(sessions)
    suffix = uuid.uuid4().hex
    first_endpoint = f"https://example.test/{suffix}/first.xml"
    duplicate_endpoint = first_endpoint + "#ignored"
    second_endpoint = f"https://example.test/{suffix}/second.xml"
    existing_endpoint = f"https://example.test/{suffix}/existing.xml"
    try:
        assert not await repository.list(), "use a disposable empty integration database"
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE managed_source_bootstrap SET completed_at = NULL WHERE id")
            )

        seed = SourceCatalog(
            defaults=SourceDefaults(news_freshness_hours=12),
            rss=[
                RssSourceConfig(name="First", url=first_endpoint, stream=SourceStream.TECH),
                RssSourceConfig(name="Duplicate", url=duplicate_endpoint, stream=SourceStream.TECH),
            ]
        )
        assert await repository.bootstrap_yaml(seed)
        assert not await repository.needs_yaml_bootstrap()
        catalog = await repository.load_catalog()
        assert [source.url for source in catalog.rss] == [first_endpoint]
        assert catalog.defaults.news_freshness_hours == 12

        changed_seed = SourceCatalog(
            rss=[RssSourceConfig(name="Second", url=second_endpoint, stream=SourceStream.WORLD)]
        )
        assert not await repository.bootstrap_yaml(changed_seed)
        assert [source.url for source in (await repository.load_catalog()).rss] == [first_endpoint]

        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM managed_sources WHERE canonical_endpoint = :endpoint"),
                {"endpoint": first_endpoint},
            )
            await connection.execute(
                text("UPDATE managed_source_bootstrap SET completed_at = NULL WHERE id")
            )
        await repository.create(
            ManagedSourceCreate(kind="rss", name="Existing", endpoint=existing_endpoint)
        )
        assert not await repository.bootstrap_yaml(seed)
        assert not await repository.needs_yaml_bootstrap()
        catalog = await repository.load_catalog()
        assert [source.url for source in catalog.rss] == [existing_endpoint]
    finally:
        async with engine.begin() as connection:
            for endpoint in (first_endpoint, second_endpoint, existing_endpoint):
                await connection.execute(
                    text("DELETE FROM managed_sources WHERE canonical_endpoint = :endpoint"),
                    {"endpoint": endpoint},
                )
            await connection.execute(
                text("UPDATE managed_source_bootstrap SET completed_at = NULL WHERE id")
            )
        await engine.dispose()
