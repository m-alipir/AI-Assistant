from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.rss import FeedFetcher, RssCollector
from app.config.sources import RssSourceConfig, load_source_catalog
from app.dedup.cache import InMemoryDedupCache
from app.ingestion.pipeline import DeterministicIngestionPipeline
from app.ingestion.schemas import SourceItem, SourceKind, SourceStream, TimestampConfidence
from app.normalize.source_items import content_fingerprint
from app.providers.contracts import ProviderError


class FixtureFeedFetcher(FeedFetcher):
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.urls: list[str] = []

    async def fetch(self, url: str) -> bytes:
        self.urls.append(url)
        return self.payload


@pytest.mark.asyncio
async def test_fixture_feed_processes_only_fresh_unique_items_before_downstream_work() -> None:
    payload = (Path(__file__).parent / "fixtures" / "rss.xml").read_bytes()
    fetcher = FixtureFeedFetcher(payload)
    collector = RssCollector(fetcher)
    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    fetched_at = datetime(2026, 9, 6, 12, tzinfo=UTC)
    items = await collector.collect(source, fetched_at=fetched_at)
    processed_titles: list[str] = []

    async def downstream_work(item_title: object) -> None:
        processed_titles.append(str(item_title))

    seed_catalog = load_source_catalog(Path("config/sources.example.yaml"))
    pipeline = DeterministicIngestionPipeline(seed_catalog.freshness_policy, InMemoryDedupCache())
    run = await pipeline.process(items, lambda item: downstream_work(item.title))

    assert fetcher.urls == ["https://example.test/feed.xml"]
    assert [item.title for item in run.accepted] == ["Fresh semiconductor announcement"]
    assert [item.title for item in run.duplicates] == ["Same story reposted"]
    assert [item.title for item in run.stale] == ["Old retained item"]
    assert [item.title for item in run.future_quarantined] == ["Future-dated item"]
    assert processed_titles == ["Fresh semiconductor announcement"]
    assert run.accepted[0].source_published_at == datetime(2026, 9, 6, 9, tzinfo=UTC)


def test_source_seed_loader_accepts_disabled_placeholders_and_rejects_enabled_invalid_sources(
    tmp_path,
) -> None:
    catalog = load_source_catalog(Path("config/sources.example.yaml"))

    assert len(catalog.rss) == 4
    assert catalog.youtube
    placeholder = next(
        source for source in catalog.youtube if source.name == "Example Tech Channel"
    )
    assert placeholder.enabled is False
    assert placeholder.language == "en"
    assert catalog.freshness_policy.news_freshness_hours == 48
    assert catalog.freshness_policy.world_freshness_hours == 48
    assert catalog.freshness_policy.youtube_freshness_hours == 72
    assert catalog.freshness_policy.future_tolerance_hours == 6

    invalid = tmp_path / "sources.yaml"
    invalid.write_text(
        "rss:\n  - name: Broken\n    url: REPLACE_ME\n    stream: tech\n    enabled: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="HTTP"):
        load_source_catalog(invalid)


def test_dedup_cache_uses_native_id_then_url_then_content_fingerprint() -> None:
    fetched_at = datetime(2026, 9, 6, 12, tzinfo=UTC)

    def item(
        external_id: str | None,
        url: str | None,
        title: str,
        snippet: str | None,
    ) -> SourceItem:
        return SourceItem(
            source_name="Fixture RSS",
            source_kind=SourceKind.RSS,
            stream=SourceStream.TECH,
            external_id=external_id,
            canonical_url=url,
            title=title,
            snippet=snippet,
            discovered_at=fetched_at,
            fetched_at=fetched_at,
            timestamp_confidence=TimestampConfidence.DISCOVERED_FALLBACK,
            content_hash=content_fingerprint(title, snippet),
        )

    cache = InMemoryDedupCache()

    assert cache.reserve(item("native-1", "https://example.test/one", "One", "First"))
    assert not cache.reserve(item("native-1", "https://example.test/two", "Two", "Second"))
    assert cache.reserve(item("native-2", "https://example.test/three", "Three", "Third"))
    assert not cache.reserve(
        item("native-3", "https://example.test/three", "Different", "Different")
    )
    assert cache.reserve(item(None, None, "Fingerprint", "Same compact content"))
    assert not cache.reserve(item(None, None, "Fingerprint", "Same compact content"))


@pytest.mark.asyncio
async def test_hostile_feed_is_item_and_field_bounded_and_rejects_dtd() -> None:
    entries = "".join(
        f"<item><guid>{index}</guid><title>{'T' * 700}</title>"
        f"<description>{'S' * 5000}</description></item>" for index in range(5)
    )
    payload = f"<rss><channel>{entries}</channel></rss>".encode()
    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    items = await RssCollector(FixtureFeedFetcher(payload), max_items=2).collect(source)
    assert len(items) == 2
    assert all(len(item.title) == 512 for item in items)
    assert all(item.snippet is not None and len(item.snippet) == 4_000 for item in items)

    dtd = b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel/></rss>'
    with pytest.raises(ProviderError, match="prohibited declaration"):
        await RssCollector(FixtureFeedFetcher(dtd)).collect(source)
