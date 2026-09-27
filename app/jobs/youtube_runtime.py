"""Caption-first YouTube runtime built from the existing public Atom and yt-dlp tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.briefing.core import BriefingItem
from app.collectors.rss import HttpFeedFetcher
from app.collectors.youtube import (
    SubtitleFetcher,
    SubtitleFetchError,
    YouTubeDiscovery,
    YtDlpSubtitleFetcher,
    parse_webvtt,
    select_preferred_track,
)
from app.config.source_repository import SourceRepository
from app.config.sources import SourceCatalog, YouTubeSourceConfig
from app.dedup.cache import InMemoryDedupCache
from app.ingestion.pipeline import DeterministicIngestionPipeline
from app.ingestion.schemas import SourceItem
from app.llm.core import BudgetExceeded, ExtractionFlow, ProviderBusy

PersistEvent = Callable[[SourceItem, object, object], Awaitable[str]]
KnownItem = Callable[[str], Awaitable[bool]]
PostLlmFailure = Callable[[SourceItem, str, str | None], Awaitable[None]]
IsPostLlmFailed = Callable[[str], Awaitable[bool]]
RefreshBlockedItem = Callable[[SourceItem, str | None], Awaitable[None]]


@dataclass
class YouTubeRun:
    fetched: int = 0
    stale: int = 0
    duplicates: int = 0
    relevant: int = 0
    processed: int = 0
    events_committed: int = 0
    captions_available: int = 0
    preferred_language_captions: int = 0
    skipped_no_captions: int = 0
    skipped_no_preferred_language_caption: int = 0
    metadata_fallbacks: int = 0
    failed: int = 0
    post_llm_blocked: int = 0
    youtube_feed_access_errors: int = 0
    caption_access_errors: int = 0
    caption_diagnostics: dict[str, int] = field(
        default_factory=lambda: {
            "caption_missing": 0,
            "preferred_language_missing": 0,
            "access_denied": 0,
            "rate_limited": 0,
            "timeout": 0,
            "download_error": 0,
            "empty_or_parse_failure": 0,
            "unknown": 0,
        }
    )
    gatekeeper_errors: int = 0
    extractor_errors: int = 0
    event_persistence_errors: int = 0
    briefing_item_errors: int = 0
    processing_errors: int = 0
    source_health_persistence_errors: int = 0
    provider_busy: int = 0
    budget_exhausted: int = 0
    budget_dimensions: dict[str, int] = field(
        default_factory=lambda: {
            "usd": 0,
            "calls": 0,
            "role": 0,
            "unknown_cost": 0,
            "soft": 0,
            "unknown": 0,
        }
    )
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)
    briefing_items: list[BriefingItem] = field(default_factory=list)
    source_outcomes: dict[str, dict[str, int]] = field(default_factory=dict)

    def response(self) -> dict[str, object]:
        return {
            "status": "completed" if not self.errors else "completed_with_errors",
            "fetched": self.fetched,
            "stale": self.stale,
            "duplicates": self.duplicates,
            "relevant": self.relevant,
            "processed": self.processed,
            "events_committed": self.events_committed,
            "captions_available": self.captions_available,
            "preferred_language_captions": self.preferred_language_captions,
            "skipped_no_captions": self.skipped_no_captions,
            "skipped_no_preferred_language_caption": self.skipped_no_preferred_language_caption,
            "caption_diagnostics": dict(self.caption_diagnostics),
            "metadata_fallbacks": self.metadata_fallbacks,
            "failed": self.failed,
            "budget_exhausted": self.budget_exhausted,
            "budget_dimensions": dict(self.budget_dimensions),
            "post_llm_blocked": self.post_llm_blocked,
            "failure_categories": {
                "youtube_feed_access_error": self.youtube_feed_access_errors,
                "yt_dlp_caption_access_error": self.caption_access_errors,
                **{
                    f"yt_dlp_caption_{category}": self.caption_diagnostics[category]
                    for category in (
                        "access_denied", "rate_limited", "timeout", "download_error", "unknown"
                    )
                },
                "captions_missing": self.caption_diagnostics["caption_missing"],
                "preferred_language_caption_missing": self.caption_diagnostics[
                    "preferred_language_missing"
                ],
                "caption_empty_or_parse_failure": self.caption_diagnostics[
                    "empty_or_parse_failure"
                ],
                "gatekeeper_error": self.gatekeeper_errors,
                "extractor_error": self.extractor_errors,
                "event_persistence_error": self.event_persistence_errors,
                "briefing_item_error": self.briefing_item_errors,
                "processing_error": self.processing_errors,
                "source_health_persistence_error": self.source_health_persistence_errors,
                "provider_busy": self.provider_busy,
            },
            "llm_calls": self.llm_calls,
            "source_outcomes": [
                {"source": name[:128], **counts}
                for name, counts in list(self.source_outcomes.items())[:32]
            ],
        }


class YouTubeRuntimeJob:
    """Apply freshness/dedup/captions before existing gatekeeper and extractor calls."""

    def __init__(
        self,
        catalog: SourceCatalog,
        flow: ExtractionFlow,
        persist_event: PersistEvent,
        known_item: KnownItem,
        post_llm_failure: PostLlmFailure | None = None,
        is_post_llm_failed: IsPostLlmFailed | None = None,
        refresh_blocked_item: RefreshBlockedItem | None = None,
        *,
        discovery: YouTubeDiscovery | None = None,
        subtitles: SubtitleFetcher | None = None,
        clock: Callable[[], datetime] | None = None,
        source_repository: SourceRepository | None = None,
    ) -> None:
        self._catalog = catalog
        self._flow = flow
        self._persist_event = persist_event
        self._known_item = known_item
        self._post_llm_failure = post_llm_failure or _ignore_post_llm_failure
        self._is_post_llm_failed = is_post_llm_failed or _not_post_llm_failed
        self._refresh_blocked_item = refresh_blocked_item or _ignore_refresh_blocked_item
        self._discovery = discovery or YouTubeDiscovery(HttpFeedFetcher())
        self._subtitles = subtitles or YtDlpSubtitleFetcher()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._source_repository = source_repository

    async def run(
        self, retry_item: tuple[YouTubeSourceConfig, SourceItem] | None = None
    ) -> YouTubeRun:
        run = YouTubeRun()
        pipeline = DeterministicIngestionPipeline(
            self._catalog.freshness_policy, InMemoryDedupCache()
        )

        async def process(
            source: YouTubeSourceConfig, item: SourceItem, *, is_retry: bool = False
        ) -> None:
            source_counts = run.source_outcomes.setdefault(
                source.name,
                {"discovered": 0, "items_seen": 0, "relevant": 0, "events_committed": 0,
                "processed": 0, "failed": 0, "captions_available": 0,
                "caption_access_errors": 0, "extractor_errors": 0,
                 "event_persistence_errors": 0},
            )
            source_counts["items_seen"] += 1
            before = {
                key: getattr(run, key)
                for key in (
                    "relevant", "events_committed", "processed", "failed", "captions_available"
                    , "caption_access_errors", "extractor_errors", "event_persistence_errors"
                )
            }
            calls_before = len(self._flow._router.calls)
            try:
                if not is_retry and await self._known_item(item.content_hash):
                    run.duplicates += 1
                    return
                if not is_retry and await self._is_post_llm_failed(item.content_hash):
                    run.post_llm_blocked += 1
                    await self._refresh_blocked_item(item, source.language)
                    return
                if not item.canonical_url:
                    run.failed += 1
                    run.processing_errors += 1
                    run.errors.append(f"{item.source_name}: processing_error")
                    return
                try:
                    tracks = await self._subtitles.fetch_subtitles(
                        item.canonical_url, preferred_language=source.language
                    )
                except Exception as error:
                    run.failed += 1
                    run.caption_access_errors += 1
                    run.errors.append(f"{item.source_name}: yt_dlp_caption_access_error")
                    category = (
                        error.category
                        if isinstance(error, SubtitleFetchError)
                        and error.category in run.caption_diagnostics
                        else "unknown"
                    )
                    run.caption_diagnostics[category] += 1
                    return
                transcript = ""
                provenance = "description_only"
                track = select_preferred_track(tracks, source.language)
                if track is not None:
                    segments = parse_webvtt(track.vtt)
                    transcript = "\n".join(segment.text for segment in segments)[:12_000]
                    if transcript:
                        provenance = "auto_caption" if track.is_automatic else "manual_caption"
                        run.captions_available += 1
                        if source.language and _language_matches(track.language, source.language):
                            run.preferred_language_captions += 1
                    else:
                        run.caption_diagnostics["empty_or_parse_failure"] += 1
                if not transcript:
                    if source.language:
                        if track is None:
                            run.skipped_no_preferred_language_caption += 1
                            run.caption_diagnostics["preferred_language_missing"] += 1
                        return
                    if not tracks:
                        run.caption_diagnostics["caption_missing"] += 1
                    if item.snippet and len(item.snippet.strip()) >= 80:
                        transcript = item.snippet.strip()
                        run.metadata_fallbacks += 1
                    else:
                        if not tracks:
                            run.skipped_no_captions += 1
                        return
                try:
                    gate = await self._flow.gate(item.title, item.snippet or "", item.content_hash)
                except ProviderBusy:
                    run.failed += 1
                    run.provider_busy += 1
                    run.errors.append(f"{item.source_name}: provider_busy")
                    return
                except BudgetExceeded as error:
                    run.budget_exhausted += 1
                    dimension = (
                        error.dimension
                        if error.dimension in run.budget_dimensions
                        else "unknown"
                    )
                    run.budget_dimensions[dimension] += 1
                    return
                except Exception:
                    run.failed += 1
                    run.gatekeeper_errors += 1
                    run.errors.append(f"{item.source_name}: gatekeeper_error")
                    return
                if not gate.relevant and gate.global_importance < 7:
                    return
                run.relevant += 1
                try:
                    extracted = await self._flow.extract(
                        f"VIDEO TITLE: {item.title}\nSOURCE: {provenance}\nCONTENT:\n{transcript}",
                        item.content_hash,
                    )
                except ProviderBusy:
                    run.failed += 1
                    run.provider_busy += 1
                    run.errors.append(f"{item.source_name}: provider_busy")
                    return
                except BudgetExceeded as error:
                    run.budget_exhausted += 1
                    dimension = (
                        error.dimension
                        if error.dimension in run.budget_dimensions
                        else "unknown"
                    )
                    run.budget_dimensions[dimension] += 1
                    return
                except Exception:
                    run.failed += 1
                    run.extractor_errors += 1
                    run.errors.append(f"{item.source_name}: extractor_error")
                    try:
                        await self._post_llm_failure(item, "extractor_error", source.language)
                    except Exception:
                        run.processing_errors += 1
                    return
                try:
                    await self._flow.embed_extraction(item.title, extracted, item.content_hash)
                except (BudgetExceeded, ProviderBusy):
                    # Keep the event when optional retrieval enrichment is unavailable.
                    pass
                except Exception:
                    # The router records safe provider metadata; captions are not logged here.
                    pass
                try:
                    event_id = await self._persist_event(item, gate, extracted)
                    run.events_committed += 1
                except Exception:
                    run.failed += 1
                    run.event_persistence_errors += 1
                    run.errors.append(f"{item.source_name}: event_persistence_error")
                    try:
                        await self._post_llm_failure(
                            item, "event_persistence_error", source.language
                        )
                    except Exception:
                        run.processing_errors += 1
                    return
                try:
                    run.briefing_items.append(
                        BriefingItem(
                            event_id=event_id,
                            title=item.title,
                            source_urls=[item.canonical_url],
                            importance=gate.importance,
                            interest=gate.personal_relevance,
                            global_importance=gate.global_importance,
                            video=True,
                            source_type="youtube",
                            published_at=item.freshness_reference_at,
                            why_watch=extracted.what_changed or extracted.compact_summary,
                            summary_tr=extracted.compact_summary,
                            what_changed_tr=extracted.what_changed,
                        )
                    )
                except Exception:
                    run.failed += 1
                    run.briefing_item_errors += 1
                    run.errors.append(f"{item.source_name}: briefing_item_error")
                    return
                run.processed += 1
            except Exception:
                run.failed += 1
                run.processing_errors += 1
                run.errors.append(f"{item.source_name}: processing_error")
            finally:
                run.llm_calls += len(self._flow._router.calls) - calls_before
                for key, value in before.items():
                    source_counts[key] += getattr(run, key) - value

        if retry_item:
            source, item = retry_item
            await process(source, item, is_retry=True)
            return run

        for source in self._catalog.youtube:
            if not source.enabled:
                continue
            source_counts = run.source_outcomes.setdefault(
                source.name,
                {"discovered": 0, "items_seen": 0, "relevant": 0, "events_committed": 0,
                 "processed": 0, "failed": 0, "captions_available": 0,
                 "caption_access_errors": 0, "extractor_errors": 0,
                 "event_persistence_errors": 0},
            )
            try:
                items = await self._discovery.collect(source, fetched_at=self._clock())
                source_counts["discovered"] += len(items)
                run.fetched += len(items)
                deterministic = await pipeline.process(
                    items, lambda item, current_source=source: process(current_source, item)
                )
                run.stale += len(deterministic.stale)
                run.duplicates += len(deterministic.duplicates)
                source_counts["stale"] = len(deterministic.stale)
                source_counts["duplicates"] = len(deterministic.duplicates)
            except Exception:
                run.failed += 1
                run.youtube_feed_access_errors += 1
                source_counts["failed"] += 1
                run.errors.append(f"{source.name}: youtube_feed_access_error")
                if self._source_repository is not None and source.managed_source_id:
                    try:
                        await self._source_repository.record_failure(
                            source.managed_source_id,
                            error_category="youtube_feed_access_error",
                        )
                    except Exception:
                        run.source_health_persistence_errors += 1
                        run.errors.append(f"{source.name}: source_health_persistence_error")
            else:
                if self._source_repository is not None and source.managed_source_id:
                    try:
                        await self._source_repository.record_success(
                            source.managed_source_id, strategy="youtube_atom"
                        )
                    except Exception:
                        run.source_health_persistence_errors += 1
                        run.errors.append(f"{source.name}: source_health_persistence_error")
        return run


async def _ignore_post_llm_failure(item: SourceItem, category: str, language: str | None) -> None:
    """Keep standalone/offline jobs side-effect free when no durable guard is supplied."""


async def _not_post_llm_failed(content_hash: str) -> bool:
    return False


async def _ignore_refresh_blocked_item(item: SourceItem, language: str | None) -> None:
    """Keep standalone/offline jobs side-effect free when no durable guard is supplied."""


def _language_matches(value: str, preference: str) -> bool:
    return value.casefold().replace("_", "-").startswith(preference.casefold())
