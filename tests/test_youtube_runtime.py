from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.collectors.youtube import SubtitleTrack, YouTubeDiscovery
from app.config.sources import SourceCatalog, YouTubeSourceConfig
from app.ingestion.schemas import SourceStream
from app.jobs.youtube_runtime import YouTubeRuntimeJob
from app.llm.core import ExtractedClaim, ExtractorResult, GatekeeperResult


class FixtureFetcher:
    async def fetch(self, url: str) -> bytes:
        return (Path(__file__).parent / "fixtures" / "youtube.xml").read_bytes()


class FakeSubtitles:
    def __init__(self, tracks: list[SubtitleTrack]) -> None:
        self.tracks = tracks
        self.urls: list[str] = []
        self.requested_languages: list[str | None] = []

    async def fetch_subtitles(
        self, video_url: str, preferred_language: str | None = None
    ) -> list[SubtitleTrack]:
        self.urls.append(video_url)
        self.requested_languages.append(preferred_language)
        return self.tracks


class FakeFlow:
    def __init__(self) -> None:
        self._router = SimpleNamespace(calls=[])
        self.extracted_content: list[str] = []

    async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
        self._router.calls.append("gatekeeper")
        return GatekeeperResult(
            relevant=True,
            global_importance=0,
            personal_relevance=5,
            category_paths=["technology"],
            entities=[],
            topics=[],
            importance=7,
            needs_full_extraction=True,
        )

    async def extract(self, content: str, digest: str) -> ExtractorResult:
        self._router.calls.append("extractor")
        self.extracted_content.append(content)
        return ExtractorResult(
            compact_summary="Video summary.",
            what_changed="Explains a new graphics technique.",
            claims=[ExtractedClaim(statement="Caption-backed claim.")],
            entities=[],
            topics=[],
            uncertainty_markers=[],
        )


def catalog(language: str | None = None) -> SourceCatalog:
    return SourceCatalog(
        youtube=[
            YouTubeSourceConfig(
                name="Fixture Channel",
                channel_id="UCfixture",
                stream=SourceStream.TECH,
                enabled=True,
                language=language,
            )
        ]
    )


@pytest.mark.asyncio
async def test_youtube_runtime_fresh_captioned_video_becomes_worth_watching() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    flow = FakeFlow()
    known: set[str] = set()
    vtt = (Path(__file__).parent / "fixtures" / "sample.vtt").read_text(encoding="utf-8")
    subtitles = FakeSubtitles([SubtitleTrack("en", False, vtt)])

    async def persist(item, gate, extracted) -> str:
        known.add(item.content_hash)
        return "video-event"

    async def known_item(content_hash: str) -> bool:
        return content_hash in known

    job = YouTubeRuntimeJob(
        catalog(),
        flow,
        persist,
        known_item,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=subtitles,
        clock=lambda: now,
    )
    result = await job.run()

    assert result.response() == {
        "status": "completed",
        "fetched": 1,
        "stale": 0,
        "duplicates": 0,
        "relevant": 1,
        "processed": 1,
        "captions_available": 1,
        "preferred_language_captions": 0,
        "skipped_no_captions": 0,
        "skipped_no_preferred_language_caption": 0,
        "failed": 0,
        "post_llm_blocked": 0,
        "failure_categories": {
            "youtube_feed_access_error": 0,
            "yt_dlp_caption_access_error": 0,
            "gatekeeper_error": 0,
            "extractor_error": 0,
            "event_persistence_error": 0,
            "briefing_item_error": 0,
            "processing_error": 0,
            "provider_busy": 0,
            "budget_exhausted": 0,
        },
        "llm_calls": 2,
    }
    item = result.briefing_items[0]
    assert item.video is True
    assert item.source_type == "youtube"
    assert item.published_at is not None
    assert item.why_watch == "Explains a new graphics technique."
    assert item.source_urls == ["https://www.youtube.com/watch?v=abc123"]
    assert "Welcome to graphics programming" in flow.extracted_content[0]

    repeated = await job.run()
    assert repeated.duplicates == 1
    assert repeated.processed == 0
    assert repeated.llm_calls == 0


@pytest.mark.asyncio
async def test_youtube_runtime_skips_stale_before_caption_or_llm() -> None:
    subtitles = FakeSubtitles([])

    async def persist(item, gate, extracted) -> str:
        raise AssertionError("stale video must not persist")

    async def unknown(content_hash: str) -> bool:
        return False

    result = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        persist,
        unknown,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=subtitles,
        clock=lambda: datetime(2026, 9, 9, 12, tzinfo=UTC),
    ).run()
    assert result.stale == 1
    assert not subtitles.urls
    assert result.llm_calls == 0


@pytest.mark.asyncio
async def test_youtube_runtime_no_captions_is_safe_skip() -> None:
    subtitles = FakeSubtitles([])

    async def persist(item, gate, extracted) -> str:
        raise AssertionError("captionless video must not persist")

    async def unknown(content_hash: str) -> bool:
        return False

    result = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        persist,
        unknown,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=subtitles,
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()
    assert result.skipped_no_captions == 1
    assert result.failed == 0
    assert result.llm_calls == 0


@pytest.mark.asyncio
async def test_youtube_runtime_skips_wrong_caption_language_before_llm() -> None:
    subtitles = FakeSubtitles(
        [SubtitleTrack("en-US", False, "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi")]
    )

    async def persist(item, gate, extracted) -> str:
        raise AssertionError("wrong-language captions must not persist")

    async def unknown(content_hash: str) -> bool:
        return False

    flow = FakeFlow()
    result = await YouTubeRuntimeJob(
        catalog("tr"),
        flow,
        persist,
        unknown,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=subtitles,
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()
    assert result.skipped_no_preferred_language_caption == 1
    assert result.failed == 0
    assert result.llm_calls == 0
    assert subtitles.urls == ["https://www.youtube.com/watch?v=abc123"]
    assert subtitles.requested_languages == ["tr"]


@pytest.mark.asyncio
async def test_youtube_runtime_classifies_caption_access_failure_safely() -> None:
    class BrokenSubtitles:
        async def fetch_subtitles(
            self, video_url: str, preferred_language: str | None = None
        ) -> list[SubtitleTrack]:
            raise RuntimeError("provider payload must not be exposed")

    async def persist(item, gate, extracted) -> str:
        raise AssertionError("caption failure must not persist")

    async def unknown(content_hash: str) -> bool:
        return False

    result = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        persist,
        unknown,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=BrokenSubtitles(),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()
    assert result.failed == 1
    assert result.caption_access_errors == 1
    assert result.errors == ["Fixture Channel: yt_dlp_caption_access_error"]


@pytest.mark.asyncio
async def test_youtube_runtime_classifies_gatekeeper_and_extractor_failures() -> None:
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCaption"

    class BrokenGateFlow(FakeFlow):
        async def gate(self, title: str, snippet: str, digest: str) -> GatekeeperResult:
            raise RuntimeError("unsafe provider detail")

    class BrokenExtractorFlow(FakeFlow):
        async def extract(self, content: str, digest: str) -> ExtractorResult:
            raise RuntimeError("unsafe provider detail")

    async def persist(item, gate, extracted) -> str:
        raise AssertionError("LLM failures must not persist")

    async def unknown(content_hash: str) -> bool:
        return False

    marked: list[str] = []

    async def mark_failed(item, category: str, language: str | None) -> None:
        marked.append(category)

    gate = await YouTubeRuntimeJob(
        catalog(),
        BrokenGateFlow(),
        persist,
        unknown,
        mark_failed,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()
    extractor = await YouTubeRuntimeJob(
        catalog(),
        BrokenExtractorFlow(),
        persist,
        unknown,
        mark_failed,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()

    assert gate.gatekeeper_errors == 1
    assert gate.llm_calls == 0
    assert extractor.extractor_errors == 1
    assert extractor.errors == ["Fixture Channel: extractor_error"]
    assert marked == ["extractor_error"]


@pytest.mark.asyncio
async def test_event_persistence_failure_blocks_another_costly_attempt() -> None:
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCaption"
    blocked: set[str] = set()

    async def broken_persist(item, gate, extracted) -> str:
        raise RuntimeError("database detail must not be exposed")

    async def unknown(content_hash: str) -> bool:
        return False

    async def mark_failed(item, category: str, language: str | None) -> None:
        assert category == "event_persistence_error"
        blocked.add(item.content_hash)

    async def is_blocked(content_hash: str) -> bool:
        return content_hash in blocked

    first = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        broken_persist,
        unknown,
        mark_failed,
        is_blocked,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()
    second = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        broken_persist,
        unknown,
        mark_failed,
        is_blocked,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()

    assert first.event_persistence_errors == 1
    assert first.llm_calls == 2
    assert second.post_llm_blocked == 1
    assert second.llm_calls == 0


@pytest.mark.asyncio
async def test_youtube_runtime_classifies_briefing_item_failure_safely(monkeypatch) -> None:
    import app.jobs.youtube_runtime as youtube_runtime

    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCaption"

    class BrokenBriefingItem:
        def __init__(self, **kwargs: object) -> None:
            raise ValueError("do not expose source content")

    async def persist(item, gate, extracted) -> str:
        return "event-1"

    async def unknown(content_hash: str) -> bool:
        return False

    monkeypatch.setattr(youtube_runtime, "BriefingItem", BrokenBriefingItem)
    result = await YouTubeRuntimeJob(
        catalog(),
        FakeFlow(),
        persist,
        unknown,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=UTC),
    ).run()

    assert result.briefing_item_errors == 1
    assert result.errors == ["Fixture Channel: briefing_item_error"]


@pytest.mark.asyncio
async def test_explicit_retry_processes_a_blocked_video_once_and_creates_briefing_item() -> None:
    now = datetime(2026, 9, 6, 12, tzinfo=UTC)
    source = catalog().youtube[0]
    item = (await YouTubeDiscovery(FixtureFetcher()).collect(source, fetched_at=now))[0]
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nCaption"
    flow = FakeFlow()

    async def persist(item, gate, extracted) -> str:
        return "retried-event"

    async def unknown(content_hash: str) -> bool:
        return False

    async def blocked(content_hash: str) -> bool:
        return True

    job = YouTubeRuntimeJob(
        catalog(),
        flow,
        persist,
        unknown,
        is_post_llm_failed=blocked,
        discovery=YouTubeDiscovery(FixtureFetcher()),
        subtitles=FakeSubtitles([SubtitleTrack("en", False, vtt)]),
        clock=lambda: now,
    )

    normal = await job.run()
    retried = await job.run((source, item))

    assert normal.post_llm_blocked == 1
    assert normal.llm_calls == 0
    assert retried.processed == 1
    assert retried.llm_calls == 2
    assert retried.briefing_items[0].event_id == "retried-event"
