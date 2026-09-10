from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.briefing.core import BriefingItem
from app.collectors.article import ArticleContent
from app.collectors.rss import RssCollector
from app.config.sources import RssSourceConfig, SourceCatalog
from app.ingestion.schemas import SourceItem, SourceKind, SourceStream, TimestampConfidence
from app.jobs.rss_runtime import BriefingRenderError, RssRuntimeJob, database_persistence
from app.llm.core import ExtractedClaim, ExtractorResult, GatekeeperResult


class FixtureFetcher:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def fetch(self, url: str) -> bytes:
        return self.payload


class FakeFlow:
    def __init__(self) -> None:
        self._router = SimpleNamespace(calls=[])
        self.gated_titles: list[str] = []

    async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
        self.gated_titles.append(title)
        self._router.calls.append("gatekeeper")
        return GatekeeperResult(
            relevant=True,
            global_importance=2,
            personal_relevance=6,
            category_paths=["technology"],
            entities=["Example"],
            topics=["testing"],
            importance=6,
            needs_full_extraction=False,
        )

    async def extract(self, content: str, digest: str) -> ExtractorResult:
        self._router.calls.append("extractor")
        return ExtractorResult(
            compact_summary="A compact summary.",
            what_changed="A change.",
            claims=[ExtractedClaim(statement="A source-backed claim.")],
            entities=["Example"],
            topics=["testing"],
            uncertainty_markers=[],
        )


@pytest.mark.asyncio
async def test_rss_runtime_filters_before_llm_then_persists_event_and_briefing() -> None:
    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    catalog = SourceCatalog(rss=[source])
    flow = FakeFlow()
    events: list[str] = []
    briefings: list[list[object]] = []
    known_hashes: set[str] = set()

    async def persist_event(item, gate, extracted) -> str:
        events.append(item.title)
        known_hashes.add(item.content_hash)
        return "event-1"

    async def persist_briefing(items) -> None:
        briefings.append(items)

    async def known_item(content_hash: str) -> bool:
        return content_hash in known_hashes

    job = RssRuntimeJob(
        catalog,
        flow,
        persist_event,
        persist_briefing,
        known_item,
        RssCollector(FixtureFetcher((Path(__file__).parent / "fixtures" / "rss.xml").read_bytes())),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    )

    result = await job.run()

    assert result["status"] == "completed"
    assert result["counts"] == {
        "fetched": 4,
        "stale": 1,
        "future_filtered": 1,
        "duplicates": 1,
        "relevant": 1,
        "processed": 1,
        "failed": 0,
        "failure_categories": {
            "briefing_render_error": 0,
            "briefing_persistence_error": 0,
            "extractor_error": 0,
            "article_fetch_error": 0,
            "event_persistence_error": 0,
            "provider_busy": 0,
            "budget_exhausted": 0,
        },
        "post_llm_blocked": 0,
        "llm_calls": 2,
    }
    assert flow.gated_titles == ["Fresh semiconductor announcement"]
    assert events == ["Fresh semiconductor announcement"]
    assert len(briefings) == 1

    second = await job.run()
    assert second["counts"]["processed"] == 0
    assert second["counts"]["llm_calls"] == 0
    assert second["counts"]["duplicates"] == 2


@pytest.mark.asyncio
async def test_runtime_exposes_safe_briefing_render_category() -> None:
    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("no RSS item should be processed")

    async def broken_briefing(items) -> None:
        raise BriefingRenderError("source content must not appear")

    item = BriefingItem(
        event_id="video-1",
        title="Video",
        source_urls=["https://example.test/video"],
        importance=7,
        interest=7,
        global_importance=0,
        video=True,
    )
    result = await RssRuntimeJob(SourceCatalog(), FakeFlow(), persist_event, broken_briefing).run(
        [item]
    )

    assert result["counts"]["failure_categories"]["briefing_render_error"] == 1
    assert result["message"] == "briefing_render_error"


@pytest.mark.asyncio
async def test_rss_post_llm_failure_blocks_a_repeat_before_another_provider_attempt() -> None:
    class FailingExtractionFlow(FakeFlow):
        async def extract(self, content: str, digest: str) -> ExtractorResult:
            self._router.calls.append("extractor")
            raise RuntimeError("safe fixture failure")

    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    blocked: set[str] = set()

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("extraction failure must not persist an event")

    async def persist_briefing(items) -> None:
        raise AssertionError("a failed item must not create a briefing")

    async def mark_failed(item, category: str, language: str | None) -> None:
        assert category == "extractor_error"
        assert language is None
        blocked.add(item.content_hash)

    async def is_blocked(content_hash: str) -> bool:
        return content_hash in blocked

    job = RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FailingExtractionFlow(),
        persist_event,
        persist_briefing,
        collector=RssCollector(
            FixtureFetcher((Path(__file__).parent / "fixtures" / "rss.xml").read_bytes())
        ),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
        post_llm_failure=mark_failed,
        is_post_llm_failed=is_blocked,
    )

    first = await job.run()
    second = await job.run()

    assert first["counts"]["failure_categories"]["extractor_error"] == 1
    assert second["counts"]["post_llm_blocked"] == 1
    assert second["counts"]["llm_calls"] == 0


@pytest.mark.asyncio
async def test_pending_briefing_recovery_runs_without_new_source_items() -> None:
    persisted: list[list[BriefingItem]] = []

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("there are no source items in recovery")

    async def persist_briefing(items: list[BriefingItem]) -> None:
        persisted.append(items)

    async def pending() -> bool:
        return True

    await RssRuntimeJob(
        SourceCatalog(), FakeFlow(), persist_event, persist_briefing, has_pending_briefing=pending
    ).run()

    assert persisted == [[]]


@pytest.mark.asyncio
async def test_explicit_rss_retry_bypasses_only_its_post_llm_block() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    item = SourceItem(
        source_name="Fixture RSS",
        source_kind=SourceKind.RSS,
        stream=SourceStream.TECH,
        canonical_url="https://example.test/item",
        title="Retryable item",
        source_published_at=now,
        discovered_at=now,
        fetched_at=now,
        timestamp_confidence=TimestampConfidence.SOURCE,
        content_hash="retry-hash",
    )
    persisted: list[list[BriefingItem]] = []

    async def persist_event(item, gate, extracted) -> str:
        return "event-retry"

    async def persist_briefing(items: list[BriefingItem]) -> None:
        persisted.append(items)

    async def known(content_hash: str) -> bool:
        return False

    async def blocked(content_hash: str) -> bool:
        return True

    result = await RssRuntimeJob(
        SourceCatalog(),
        FakeFlow(),
        persist_event,
        persist_briefing,
        known,
        is_post_llm_failed=blocked,
    ).run(retry_item=item)

    assert result["counts"]["processed"] == 1
    assert result["counts"]["post_llm_blocked"] == 0
    assert len(persisted) == 1


@pytest.mark.asyncio
async def test_durable_outbox_is_locked_and_deleted_only_with_briefing_persistence() -> None:
    class Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "event_id": "event-1",
                    "title": "Recovered briefing item",
                    "source_urls_json": '["https://example.test/item"]',
                    "importance": 8,
                    "interest": 7,
                    "global_importance": 0,
                    "actionable": False,
                    "video": False,
                    "source_type": "rss",
                    "published_at": None,
                    "why_watch": None,
                }
            ]

    class Session:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def execute(self, statement, params=None):
            sql = str(statement)
            self.statements.append(sql)
            return Result()

    class Sessions:
        def __init__(self) -> None:
            self.session = Session()

        def begin(self) -> Session:
            return self.session

        def __call__(self) -> Session:
            return self.session

    sessions = Sessions()
    _, persist_briefing, *_ = database_persistence(sessions)  # type: ignore[arg-type]
    await persist_briefing([])

    statements = "\n".join(sessions.session.statements)
    assert "FOR UPDATE SKIP LOCKED" in statements
    assert "INSERT INTO briefings" in statements
    assert "DELETE FROM briefing_outbox" in statements


@pytest.mark.asyncio
async def test_irrelevant_rss_item_never_fetches_article_body() -> None:
    class IrrelevantFlow(FakeFlow):
        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            return GatekeeperResult(
                relevant=False,
                global_importance=1,
                personal_relevance=0,
                category_paths=[],
                entities=[],
                topics=[],
                importance=1,
                needs_full_extraction=True,
            )

    class ProbeFetcher:
        calls = 0

        async def fetch(self, url: str) -> ArticleContent:
            self.calls += 1
            return ArticleContent("fixture article text", url)

    now = datetime(2026, 9, 10, tzinfo=UTC)
    item = SourceItem(
        source_name="Fixture RSS",
        source_kind=SourceKind.RSS,
        stream=SourceStream.TECH,
        canonical_url="https://example.test/article",
        title="Irrelevant fixture",
        discovered_at=now,
        fetched_at=now,
        timestamp_confidence=TimestampConfidence.DISCOVERED_FALLBACK,
        content_hash="irrelevant-fixture",
    )

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("irrelevant item must not persist")

    async def persist_briefing(items) -> None:
        return None

    probe = ProbeFetcher()
    result = await RssRuntimeJob(
        SourceCatalog(),
        IrrelevantFlow(),
        persist_event,
        persist_briefing,
        article_fetcher=probe,  # type: ignore[arg-type]
    ).run(retry_item=item)
    assert probe.calls == 0
    assert result["counts"]["processed"] == 0


@pytest.mark.asyncio
async def test_full_article_is_used_only_after_gate_and_fetch_failure_uses_feed_metadata() -> None:
    class FullArticleFlow(FakeFlow):
        def __init__(self) -> None:
            super().__init__()
            self.extraction_inputs: list[str] = []

        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            return GatekeeperResult(
                relevant=True,
                global_importance=2,
                personal_relevance=6,
                category_paths=["technology"],
                entities=["Example"],
                topics=["testing"],
                importance=6,
                needs_full_extraction=True,
            )

        async def extract(self, content: str, digest: str) -> ExtractorResult:
            self.extraction_inputs.append(content)
            return await super().extract(content, digest)

    class Fetcher:
        def __init__(self, fail: bool = False) -> None:
            self.fail = fail
            self.calls = 0

        async def fetch(self, url: str) -> ArticleContent:
            self.calls += 1
            if self.fail:
                raise RuntimeError("fixture fetch failure")
            return ArticleContent("Useful article body with source-backed detail.", url)

    now = datetime(2026, 9, 10, tzinfo=UTC)
    item = SourceItem(
        source_name="Fixture RSS", source_kind=SourceKind.RSS, stream=SourceStream.TECH,
        canonical_url="https://example.test/article", title="Full article fixture",
        snippet="Feed fallback", discovered_at=now, fetched_at=now,
        timestamp_confidence=TimestampConfidence.DISCOVERED_FALLBACK, content_hash="full-article",
    )

    async def persist_event(item, gate, extracted) -> str:
        return "event-full"

    async def persist_briefing(items) -> None:
        return None

    flow, fetcher = FullArticleFlow(), Fetcher()
    result = await RssRuntimeJob(
        SourceCatalog(), flow, persist_event, persist_briefing, article_fetcher=fetcher  # type: ignore[arg-type]
    ).run(retry_item=item)
    assert fetcher.calls == 1
    assert "ARTICLE:\nUseful article body" in flow.extraction_inputs[0]
    assert result["counts"]["failure_categories"]["article_fetch_error"] == 0

    fallback_flow, failing_fetcher = FullArticleFlow(), Fetcher(fail=True)
    fallback = await RssRuntimeJob(
        SourceCatalog(), fallback_flow, persist_event, persist_briefing,
        article_fetcher=failing_fetcher,  # type: ignore[arg-type]
    ).run(retry_item=item.model_copy(update={"content_hash": "full-article-fallback"}))
    assert "SNIPPET: Feed fallback" in fallback_flow.extraction_inputs[0]
    assert fallback["counts"]["failure_categories"]["article_fetch_error"] == 1


@pytest.mark.asyncio
async def test_duplicate_rss_item_never_fetches_article_body() -> None:
    class FullArticleFlow(FakeFlow):
        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            raise AssertionError("duplicate item must not reach the gatekeeper")

    class ProbeFetcher:
        calls = 0

        async def fetch(self, url: str) -> ArticleContent:
            self.calls += 1
            raise AssertionError("duplicate item must not fetch an article")

    now = datetime(2026, 9, 10, tzinfo=UTC)
    item = SourceItem(
        source_name="Fixture RSS", source_kind=SourceKind.RSS, stream=SourceStream.TECH,
        canonical_url="https://example.test/article", title="Duplicate fixture",
        discovered_at=now, fetched_at=now,
        timestamp_confidence=TimestampConfidence.DISCOVERED_FALLBACK, content_hash="duplicate",
    )

    async def known(content_hash: str) -> bool:
        return True

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("duplicate item must not persist")

    async def persist_briefing(items) -> None:
        return None

    probe = ProbeFetcher()
    result = await RssRuntimeJob(
        SourceCatalog(), FullArticleFlow(), persist_event, persist_briefing, known,
        article_fetcher=probe,  # type: ignore[arg-type]
    ).run(retry_item=item)
    assert probe.calls == 0
    assert result["counts"]["duplicates"] == 1


@pytest.mark.asyncio
async def test_stale_rss_item_never_fetches_article_body() -> None:
    class FullArticleFlow(FakeFlow):
        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            raise AssertionError("stale item must not reach the gatekeeper")

    class ProbeFetcher:
        calls = 0

        async def fetch(self, url: str) -> ArticleContent:
            self.calls += 1
            raise AssertionError("stale item must not fetch an article")

    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    payload = b"""<rss><channel><item><title>Stale article</title>
    <link>https://example.test/article</link><pubDate>Mon, 01 Sep 2026 12:00:00 +0000</pubDate>
    <description>Old fixture.</description></item></channel></rss>"""

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("stale item must not persist")

    async def persist_briefing(items) -> None:
        return None

    probe = ProbeFetcher()
    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FullArticleFlow(),
        persist_event,
        persist_briefing,
        collector=RssCollector(FixtureFetcher(payload)),
        clock=lambda: datetime(2026, 9, 10, 12, tzinfo=UTC),
        article_fetcher=probe,  # type: ignore[arg-type]
    ).run()
    assert probe.calls == 0
    assert result["counts"]["stale"] == 1
