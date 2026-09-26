import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.briefing.core import BriefingItem, build_sections, visible_briefing_items
from app.collectors.article import ArticleContent
from app.collectors.rss import ConditionalFeedResult, RssCollector
from app.config.sources import RssSourceConfig, SourceCatalog
from app.ingestion.schemas import SourceItem, SourceKind, SourceStream, TimestampConfidence
from app.jobs.rss_runtime import BriefingRenderError, RssRuntimeJob, database_persistence
from app.llm.core import (
    BudgetExceeded,
    BudgetPolicy,
    BudgetTracker,
    ExtractedClaim,
    ExtractorResult,
    GatekeeperResult,
    InMemoryResultCache,
    ModelSettings,
    OpenRouterClient,
    RoleConfig,
    Router,
)


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


class FakeSourceRepository:
    def __init__(self) -> None:
        self.successes: list[tuple[str, str]] = []
        self.failures: list[tuple[str, str]] = []

    async def record_success(
        self, source_id: str, *, strategy: str, detected_language: str | None = None
    ) -> bool:
        self.successes.append((source_id, strategy))
        return True

    async def record_failure(self, source_id: str, *, error_category: str) -> bool:
        self.failures.append((source_id, error_category))
        return True

@pytest.mark.asyncio
async def test_rss_metadata_fetches_are_bounded_and_processing_stays_safe() -> None:
    class DelayedCollector:
        def __init__(self) -> None:
            self.active = 0
            self.peak = 0

        async def collect(self, source, fetched_at):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0)
            self.active -= 1
            return []

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("empty fixture feeds must not persist events")

    async def persist_briefing(items) -> None:
        raise AssertionError("empty fixture feeds must not render a briefing")

    sources = [
        RssSourceConfig(
            name=f"Fixture {index}",
            url=f"https://example.test/{index}.xml",
            stream=SourceStream.TECH,
            enabled=True,
        )
        for index in range(3)
    ]
    collector = DelayedCollector()
    result = await RssRuntimeJob(
        SourceCatalog(rss=sources),
        FakeFlow(),
        persist_event,
        persist_briefing,
        collector=collector,
        max_concurrent_fetches=2,
    ).run()

    assert collector.peak == 2
    assert result["counts"]["fetched"] == 0


@pytest.mark.parametrize("stage", ["gate", "extract"])
@pytest.mark.asyncio
async def test_rss_budget_exhaustion_is_a_skip_not_a_processing_failure(stage: str) -> None:
    class BudgetFlow(FakeFlow):
        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            if stage == "gate":
                raise BudgetExceeded
            return await super().gate(title, snippet, digest)

        async def extract(self, content: str, digest: str) -> ExtractorResult:
            raise BudgetExceeded

    source = RssSourceConfig(
        name="Fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )

    async def persist_event(*_: object) -> str:
        raise AssertionError("budget-exhausted items must not be persisted")

    async def persist_briefing(*_: object) -> None:
        raise AssertionError("empty budget-exhausted run must not render a briefing")

    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        BudgetFlow(),
        persist_event,
        persist_briefing,
        collector=RssCollector(
            FixtureFetcher((Path(__file__).parent / "fixtures" / "rss.xml").read_bytes())
        ),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()

    counts = result["counts"]
    assert result["status"] == "completed"
    assert counts["failed"] == 0
    assert counts["budget_exhausted"] == 1
    assert "budget_exhausted" not in result["message"]


@pytest.mark.asyncio
async def test_rss_not_modified_skips_parse_and_downstream_work() -> None:
    class NotModifiedCollector:
        async def collect_conditional(self, source, etag, last_modified, fetched_at):
            return ConditionalFeedResult(None, None, None, not_modified=True)

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("304 response must not reach persistence")

    async def persist_briefing(items) -> None:
        raise AssertionError("304 response must not create a briefing")

    source = RssSourceConfig(
        name="Conditional fixture",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FakeFlow(),
        persist_event,
        persist_briefing,
        collector=NotModifiedCollector(),
    ).run()

    assert result["counts"]["not_modified"] == 1
    assert result["counts"]["llm_calls"] == 0

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
        "not_modified": 0,
        "stale": 1,
        "future_filtered": 1,
        "duplicates": 1,
        "relevant": 1,
        "processed": 1,
        "failed": 0,
        "budget_exhausted": 0,
        "failure_categories": {
            "briefing_render_error": 0,
            "briefing_persistence_error": 0,
            "gatekeeper_error": 0,
            "extractor_error": 0,
            "article_fetch_error": 0,
            "event_persistence_error": 0,
            "item_processing_error": 0,
            "source_fetch_error": 0,
            "source_cooldown": 0,
            "source_health_persistence_error": 0,
            "provider_busy": 0,
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
async def test_rss_editor_changes_only_the_ordered_visible_five() -> None:
    prompts: list[str] = []

    def editor_transport(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["messages"][0]["content"]
        prompts.append(prompt)
        encoded = prompt.split("<untrusted_items_json>\n", 1)[1].split(
            "\n</untrusted_items_json>", 1
        )[0]
        supplied = json.loads(encoded)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "items": [
                                        {
                                            "event_id": item["event_id"],
                                            "title": f"Türkçe {item['event_id']}",
                                            "summary": f"Türkçe özet {item['event_id']}.",
                                            "what_changed": None,
                                        }
                                        for item in supplied
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(editor_transport)),
        ModelSettings(
            roles={"editor": RoleConfig(model="fake/editor", max_input_chars=4_000)},
            budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
        ),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    flow = FakeFlow()
    flow._router = router
    feed_items = "".join(
        f"<item><title>news-{index}</title><link>https://example.test/news-{index}</link>"
        f"<guid>news-{index}</guid>"
        f"{f'<pubDate>Sun, 06 Sep 2026 {6 + index:02d}:00:00 GMT</pubDate>' if index < 5 else ''}"
        "<description>Fresh RSS description.</description></item>"
        for index in range(6)
    )
    feed = f"<rss><channel><title>fixture</title>{feed_items}</channel></rss>".encode()
    source = RssSourceConfig(
        name="Fresh fixture RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
    )
    unsectioned = BriefingItem(
        event_id="unsectioned",
        title="Unsectioned English item",
        source_urls=[],
        importance=4,
        interest=6,
        global_importance=0,
        summary_tr="Unsectioned English summary.",
    )
    persisted: list[list[BriefingItem]] = []

    async def persist_event(item, gate, extracted) -> str:
        return item.title

    async def persist_briefing(values: list[BriefingItem]) -> None:
        persisted.append(values)

    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        flow,
        persist_event,
        persist_briefing,
        collector=RssCollector(FixtureFetcher(feed)),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run([unsectioned])

    assert result["counts"]["processed"] == 6
    assert len(prompts) == 1
    selected = json.loads(
        prompts[0].split("<untrusted_items_json>\n", 1)[1].split(
            "\n</untrusted_items_json>", 1
        )[0]
    )
    expected_ids = [f"news-{index}" for index in range(5, 0, -1)]
    assert [item["event_id"] for item in selected] == expected_ids
    assert len(persisted) == 1
    assert {
        item.event_id: item.published_at
        for item in persisted[0]
        if item.event_id.startswith("news-")
    } == {
        **{
            f"news-{index}": datetime(2026, 9, 6, 6 + index, tzinfo=UTC)
            for index in range(5)
        },
        "news-5": datetime(2026, 9, 6, 12, tzinfo=UTC),
    }
    translated = {
        item.event_id for item in persisted[0] if (item.summary_tr or "").startswith("Türkçe")
    }
    assert translated == set(expected_ids)

    tied_feed_items = "".join(
        f"<item><title>news-{index}</title><link>https://example.test/news-{index}</link>"
        f"<guid>news-{index}</guid><pubDate>Sun, 06 Sep 2026 10:00:00 GMT</pubDate>"
        "<description>Fresh RSS description.</description></item>"
        for index in reversed(range(6))
    )
    tied_persisted: list[list[BriefingItem]] = []

    async def persist_tied_briefing(values: list[BriefingItem]) -> None:
        tied_persisted.append(values)

    await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        flow,
        persist_event,
        persist_tied_briefing,
        collector=RssCollector(
            FixtureFetcher(f"<rss><channel><title>fixture</title>{tied_feed_items}</channel></rss>".encode())
        ),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()

    tied_editor_items = json.loads(
        prompts[1].split("<untrusted_items_json>\n", 1)[1].split(
            "\n</untrusted_items_json>", 1
        )[0]
    )
    tied_ids = [item["event_id"] for item in tied_editor_items]
    detail_ids = [
        item.event_id for item in visible_briefing_items(build_sections(tied_persisted[0]))
    ]
    assert tied_ids == detail_ids == [f"news-{index}" for index in range(5)]


@pytest.mark.asyncio
async def test_briefing_editor_budget_skip_is_reported_in_run_counts(monkeypatch) -> None:
    async def skip_editor(sections, router):
        raise BudgetExceeded("safe fixture")

    monkeypatch.setattr("app.jobs.rss_runtime.edit_compact", skip_editor)
    router = Router(
        OpenRouterClient("test-key", "https://example.test", httpx.MockTransport(lambda _: None)),
        ModelSettings(
            roles={"editor": RoleConfig(model="fake/editor", max_input_chars=4_000)},
            budgets=BudgetPolicy(daily_soft_usd=1, daily_hard_usd=1),
        ),
        InMemoryResultCache(),
        BudgetTracker(),
    )
    flow = FakeFlow()
    flow._router = router
    item = BriefingItem(
        event_id="budget-item",
        title="English title",
        source_urls=[],
        importance=6,
        interest=7,
        global_importance=0,
        summary_tr="English summary.",
    )
    persisted: list[list[BriefingItem]] = []

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("additional items should skip RSS event extraction")

    async def persist_briefing(values: list[BriefingItem]) -> None:
        persisted.append(values)

    result = await RssRuntimeJob(
        SourceCatalog(), flow, persist_event, persist_briefing
    ).run([item])

    assert result["counts"]["budget_exhausted"] == 1
    assert result["counts"]["failed"] == 0
    assert len(persisted) == 1
    assert persisted[0][0].summary_tr == "English summary."


@pytest.mark.asyncio
async def test_rss_runtime_persists_source_success_and_safe_access_failure() -> None:
    source = RssSourceConfig(
        name="Managed RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
        managed_source_id="managed-rss",
    )
    repository = FakeSourceRepository()

    async def persist_event(item, gate, extracted) -> str:
        return "event"

    async def persist_briefing(items) -> None:
        return None

    async def known_item(content_hash: str) -> bool:
        return False

    successful = RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FakeFlow(),
        persist_event,
        persist_briefing,
        known_item,
        collector=RssCollector(FixtureFetcher(b"<rss><channel /></rss>")),
        source_repository=repository,
    )
    await successful.run()
    assert repository.successes == [("managed-rss", "rss_atom")]

    class BrokenCollector:
        async def collect(self, source, *, fetched_at):
            raise RuntimeError("safe fixture failure")

    failed = RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FakeFlow(),
        persist_event,
        persist_briefing,
        known_item,
        collector=BrokenCollector(),
        source_repository=repository,
    )
    failed_result = await failed.run()
    assert repository.failures == [("managed-rss", "rss_feed_access_error")]
    assert failed_result["counts"]["failed"] == 1
    assert failed_result["counts"]["failure_categories"]["source_fetch_error"] == 1


@pytest.mark.asyncio
async def test_fetch_failure_counts_source_health_persistence_errors_without_details() -> None:
    source = RssSourceConfig(
        name="Managed RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
        managed_source_id="managed-rss",
    )

    class BrokenCollector:
        async def collect(self, source, *, fetched_at):
            raise RuntimeError("provider response must stay private")

    class BrokenSourceRepository:
        async def record_failure(self, source_id: str, *, error_category: str) -> bool:
            raise RuntimeError("database detail must stay private")

    async def broken_source_failed(kind: str, name: str, error: BaseException) -> None:
        raise RuntimeError("health callback detail must stay private")

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("failed collection cannot persist events")

    async def persist_briefing(items) -> None:
        raise AssertionError("failed collection cannot persist a briefing")

    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FakeFlow(),
        persist_event,
        persist_briefing,
        collector=BrokenCollector(),
        source_failed=broken_source_failed,
        source_repository=BrokenSourceRepository(),
    ).run()

    categories = result["counts"]["failure_categories"]
    assert result["counts"]["failed"] == 1
    assert categories["source_fetch_error"] == 1
    assert categories["source_health_persistence_error"] == 2
    assert "provider response must stay private" not in result["message"]
    assert "database detail must stay private" not in result["message"]
    assert "health callback detail must stay private" not in result["message"]


@pytest.mark.asyncio
async def test_source_success_health_error_marks_run_failed_safely() -> None:
    source = RssSourceConfig(
        name="Managed RSS",
        url="https://example.test/feed.xml",
        stream=SourceStream.TECH,
        enabled=True,
        managed_source_id="managed-rss",
    )
    repository = FakeSourceRepository()

    async def source_succeeded(kind: str, name: str, strategy: str) -> None:
        raise RuntimeError("private health persistence detail")

    async def persist_event(item, gate, extracted) -> str:
        raise AssertionError("empty feed cannot persist events")

    async def persist_briefing(items) -> None:
        raise AssertionError("empty feed cannot persist a briefing")

    result = await RssRuntimeJob(
        SourceCatalog(rss=[source]),
        FakeFlow(),
        persist_event,
        persist_briefing,
        collector=RssCollector(FixtureFetcher(b"<rss><channel /></rss>")),
        source_succeeded=source_succeeded,
        source_repository=repository,
    ).run()

    assert repository.successes == [("managed-rss", "rss_atom")]
    assert result["status"] == "completed_with_errors"
    assert result["counts"]["failure_categories"]["source_health_persistence_error"] == 1
    assert "private health persistence detail" not in result["message"]


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
