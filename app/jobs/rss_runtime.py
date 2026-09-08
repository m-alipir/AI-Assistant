"""The small RSS-only runtime path used by the local admin manual trigger."""

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.briefing.core import BriefingItem, build_sections, render_preview
from app.collectors.rss import HttpFeedFetcher, RssCollector
from app.config.sources import SourceCatalog
from app.dedup.cache import InMemoryDedupCache
from app.ingestion.pipeline import DeterministicIngestionPipeline
from app.ingestion.schemas import SourceItem
from app.llm.core import BudgetExceeded, ExtractionFlow, ProviderBusy


@dataclass
class RunCounts:
    fetched: int = 0
    stale: int = 0
    future_filtered: int = 0
    duplicates: int = 0
    relevant: int = 0
    processed: int = 0
    failed: int = 0
    briefing_render_errors: int = 0
    briefing_persistence_errors: int = 0
    post_llm_blocked: int = 0
    extractor_errors: int = 0
    event_persistence_errors: int = 0
    provider_busy: int = 0
    budget_exhausted: int = 0
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)

    def response(self) -> dict[str, object]:
        return {
            "status": "completed" if not self.errors else "completed_with_errors",
            "counts": {
                "fetched": self.fetched,
                "stale": self.stale,
                "future_filtered": self.future_filtered,
                "duplicates": self.duplicates,
                "relevant": self.relevant,
                "processed": self.processed,
                "failed": self.failed,
                "failure_categories": {
                    "briefing_render_error": self.briefing_render_errors,
                    "briefing_persistence_error": self.briefing_persistence_errors,
                    "extractor_error": self.extractor_errors,
                    "event_persistence_error": self.event_persistence_errors,
                    "provider_busy": self.provider_busy,
                    "budget_exhausted": self.budget_exhausted,
                },
                "post_llm_blocked": self.post_llm_blocked,
                "llm_calls": self.llm_calls,
            },
            "message": "; ".join(self.errors) if self.errors else "RSS run completed.",
        }


PersistEvent = Callable[[SourceItem, object, object], Awaitable[str]]
PersistBriefing = Callable[[list[BriefingItem]], Awaitable[None]]
KnownItem = Callable[[str], Awaitable[bool]]
PostLlmFailure = Callable[[SourceItem, str, str | None], Awaitable[None]]
IsPostLlmFailed = Callable[[str], Awaitable[bool]]
RefreshBlockedItem = Callable[[SourceItem, str | None], Awaitable[None]]
ClaimBlockedItem = Callable[[str, str], Awaitable[dict[str, object] | None]]
ResolveBlockedItem = Callable[[str], Awaitable[None]]
HasPendingBriefing = Callable[[], Awaitable[bool]]


class BriefingRenderError(RuntimeError):
    """Safe category for an in-memory briefing composition/render failure."""


class BriefingPersistenceError(RuntimeError):
    """Safe category for a database write failure after rendering succeeds."""


class RssRuntimeJob:
    """Connect existing collector, deterministic gate, LLM flow, and persistence boundaries."""

    def __init__(
        self,
        catalog: SourceCatalog,
        flow: ExtractionFlow,
        persist_event: PersistEvent,
        persist_briefing: PersistBriefing,
        known_item: KnownItem | None = None,
        collector: RssCollector | None = None,
        clock: Callable[[], datetime] | None = None,
        *,
        post_llm_failure: PostLlmFailure | None = None,
        is_post_llm_failed: IsPostLlmFailed | None = None,
        refresh_blocked_item: RefreshBlockedItem | None = None,
        has_pending_briefing: HasPendingBriefing | None = None,
    ) -> None:
        self._catalog = catalog
        self._flow = flow
        self._persist_event = persist_event
        self._persist_briefing = persist_briefing
        self._known_item = known_item or _unknown_item
        self._collector = collector or RssCollector(HttpFeedFetcher())
        self._clock = clock or (lambda: datetime.now(UTC))
        self._post_llm_failure = post_llm_failure or _ignore_post_llm_failure
        self._is_post_llm_failed = is_post_llm_failed or _not_post_llm_failed
        self._refresh_blocked_item = refresh_blocked_item or _ignore_refresh_blocked_item
        self._has_pending_briefing = has_pending_briefing or _no_pending_briefing

    async def run(
        self,
        additional_briefing_items: list[BriefingItem] | None = None,
        *,
        retry_item: SourceItem | None = None,
    ) -> dict[str, object]:
        counts = RunCounts()
        pipeline = DeterministicIngestionPipeline(
            self._catalog.freshness_policy, InMemoryDedupCache()
        )
        briefing_items = list(additional_briefing_items or [])

        async def process(item: SourceItem, *, is_retry: bool = False) -> None:
            calls_before = len(
                self._flow._router.calls
            )  # Runtime metrics only; no request content.
            try:
                if await self._known_item(item.content_hash):
                    counts.duplicates += 1
                    return
                if not is_retry and await self._is_post_llm_failed(item.content_hash):
                    counts.post_llm_blocked += 1
                    await self._refresh_blocked_item(item, None)
                    return
                try:
                    gate = await self._flow.gate(item.title, item.snippet or "", item.content_hash)
                except ProviderBusy:
                    counts.failed += 1
                    counts.provider_busy += 1
                    counts.errors.append(f"{item.source_name}: provider_busy")
                    return
                except BudgetExceeded:
                    counts.failed += 1
                    counts.budget_exhausted += 1
                    counts.errors.append(f"{item.source_name}: budget_exhausted")
                    return
                except Exception:
                    counts.failed += 1
                    counts.errors.append(f"{item.source_name}: gatekeeper_error")
                    return
                if not gate.relevant and gate.global_importance < 7:
                    return
                counts.relevant += 1
                try:
                    extracted = await self._flow.extract(
                        f"TITLE: {item.title}\nSNIPPET: {item.snippet or ''}", item.content_hash
                    )
                except ProviderBusy:
                    counts.failed += 1
                    counts.provider_busy += 1
                    counts.errors.append(f"{item.source_name}: provider_busy")
                    return
                except BudgetExceeded:
                    counts.failed += 1
                    counts.budget_exhausted += 1
                    counts.errors.append(f"{item.source_name}: budget_exhausted")
                    return
                except Exception:
                    counts.failed += 1
                    counts.extractor_errors += 1
                    counts.errors.append(f"{item.source_name}: extractor_error")
                    try:
                        await self._post_llm_failure(item, "extractor_error", None)
                    except Exception:
                        pass
                    return
                try:
                    event_id = await self._persist_event(item, gate, extracted)
                except Exception:
                    counts.failed += 1
                    counts.event_persistence_errors += 1
                    counts.errors.append(f"{item.source_name}: event_persistence_error")
                    try:
                        await self._post_llm_failure(item, "event_persistence_error", None)
                    except Exception:
                        pass
                    return
                briefing_items.append(
                    BriefingItem(
                        event_id=event_id,
                        title=item.title,
                        source_urls=[item.canonical_url] if item.canonical_url else [],
                        importance=gate.importance,
                        interest=gate.personal_relevance,
                        global_importance=gate.global_importance,
                        summary_tr=extracted.compact_summary,
                        what_changed_tr=extracted.what_changed,
                    )
                )
                counts.processed += 1
            except Exception as error:  # Individual item failure must not abort other feeds/items.
                counts.failed += 1
                counts.errors.append(f"{item.source_name}: {type(error).__name__}")
            finally:
                counts.llm_calls += len(self._flow._router.calls) - calls_before

        if retry_item is not None:
            await process(retry_item, is_retry=True)
        else:
            for source in self._catalog.rss:
                if not source.enabled:
                    continue
                try:
                    items = await self._collector.collect(source, fetched_at=self._clock())
                    counts.fetched += len(items)
                    deterministic = await pipeline.process(items, process)
                    counts.stale += len(deterministic.stale)
                    counts.future_filtered += len(deterministic.future_quarantined)
                    counts.duplicates += len(deterministic.duplicates)
                except Exception as error:
                    counts.failed += 1
                    counts.errors.append(f"{source.name}: {type(error).__name__}")

        if briefing_items or await self._has_pending_briefing():
            try:
                await self._persist_briefing(briefing_items)
            except BriefingRenderError:
                counts.failed += 1
                counts.briefing_render_errors += 1
                counts.errors.append("briefing_render_error")
            except Exception:
                counts.failed += 1
                counts.briefing_persistence_errors += 1
                counts.errors.append("briefing_persistence_error")
        return counts.response()


async def _unknown_item(content_hash: str) -> bool:
    return False


async def _ignore_post_llm_failure(
    item: SourceItem, category: str, language: str | None
) -> None:
    """Keep standalone/offline jobs side-effect free without a durable guard."""


async def _not_post_llm_failed(content_hash: str) -> bool:
    return False


async def _ignore_refresh_blocked_item(item: SourceItem, language: str | None) -> None:
    """Keep standalone/offline jobs side-effect free without a durable guard."""


async def _no_pending_briefing() -> bool:
    return False


def database_persistence(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[
    PersistEvent,
    PersistBriefing,
    KnownItem,
    PostLlmFailure,
    IsPostLlmFailed,
    RefreshBlockedItem,
    ClaimBlockedItem,
    ResolveBlockedItem,
    HasPendingBriefing,
]:
    """Return durable provenance/briefing writers without retaining raw provider payloads."""

    async def persist_event(item: SourceItem, gate: object, extracted: object) -> str:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item.content_hash))
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO events (id, canonical_title, occurred_at, embedding_dimensions, "
                    "raw_content, status) "
                    "VALUES (:id, :title, :occurred_at, 0, :raw_content, 'active') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": event_id,
                    "title": item.title,
                    "occurred_at": item.freshness_reference_at,
                    "raw_content": item.snippet,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO event_sources "
                    "(event_id, source_item_id, relation, canonical_url, source_kind) "
                    "VALUES (:event_id, :source_item_id, 'primary', :canonical_url, :source_kind) "
                    "ON CONFLICT (event_id, source_item_id) DO UPDATE SET "
                    "canonical_url = EXCLUDED.canonical_url, source_kind = EXCLUDED.source_kind"
                ),
                {
                    "event_id": event_id,
                    "source_item_id": item.content_hash,
                    "canonical_url": item.canonical_url,
                    "source_kind": item.source_kind.value,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO event_search_metadata "
                    "(event_id, category_paths_json, entities_json, topics_json) "
                    "VALUES (:event_id, :category_paths, :entities, :topics) "
                    "ON CONFLICT (event_id) DO UPDATE SET "
                    "category_paths_json = EXCLUDED.category_paths_json, "
                    "entities_json = EXCLUDED.entities_json, topics_json = EXCLUDED.topics_json"
                ),
                {
                    "event_id": event_id,
                    "category_paths": json.dumps(gate.category_paths),
                    "entities": json.dumps(gate.entities),
                    "topics": json.dumps(gate.topics),
                },
            )
            for claim in extracted.claims:
                claim_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{event_id}:{claim.statement}"))
                await session.execute(
                    text(
                        "INSERT INTO claims (id, event_id, source_item_id, statement, "
                        "source_locator) "
                        "VALUES (:id, :event_id, :source_item_id, :statement, :source_locator) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": claim_id,
                        "event_id": event_id,
                        "source_item_id": item.content_hash,
                        "statement": claim.statement,
                        "source_locator": claim.source_locator,
                    },
                )
            await session.execute(
                text(
                    "INSERT INTO briefing_outbox "
                    "(event_id, title, source_urls_json, importance, interest, global_importance, "
                    "actionable, video, source_type, published_at, why_watch, summary_tr, "
                    "what_changed_tr, why_important_tr) "
                    "VALUES (:event_id, :title, :source_urls_json, :importance, :interest, "
                    ":global_importance, false, :video, :source_type, :published_at, :why_watch, "
                    ":summary_tr, :what_changed_tr, :why_important_tr) "
                    "ON CONFLICT (event_id) DO UPDATE SET title = EXCLUDED.title, "
                    "source_urls_json = EXCLUDED.source_urls_json, "
                    "importance = EXCLUDED.importance, "
                    "interest = EXCLUDED.interest, global_importance = EXCLUDED.global_importance, "
                    "video = EXCLUDED.video, source_type = EXCLUDED.source_type, "
                    "published_at = EXCLUDED.published_at, why_watch = EXCLUDED.why_watch, "
                    "summary_tr = EXCLUDED.summary_tr, what_changed_tr = EXCLUDED.what_changed_tr, "
                    "why_important_tr = EXCLUDED.why_important_tr"
                ),
                {
                    "event_id": event_id,
                    "title": extracted.briefing_title or item.title,
                    "source_urls_json": json.dumps(
                        [item.canonical_url] if item.canonical_url else []
                    ),
                    "importance": gate.importance,
                    "interest": gate.personal_relevance,
                    "global_importance": gate.global_importance,
                    "video": item.source_kind.value == "youtube",
                    "source_type": item.source_kind.value,
                    "published_at": item.source_published_at,
                    "why_watch": (
                        extracted.what_changed or extracted.compact_summary
                        if item.source_kind.value == "youtube"
                        else None
                    ),
                    "summary_tr": extracted.compact_summary,
                    "what_changed_tr": extracted.what_changed,
                    "why_important_tr": None,
                },
            )
        return event_id

    async def persist_briefing(items: list[BriefingItem]) -> None:
        """Atomically drain safe pending candidates so a retry cannot duplicate a briefing."""
        try:
            async with sessions.begin() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT event_id, title, source_urls_json, importance, interest, "
                            "global_importance, actionable, video, source_type, published_at, "
                            "why_watch, summary_tr, what_changed_tr, why_important_tr "
                            "FROM briefing_outbox ORDER BY created_at ASC "
                            "FOR UPDATE SKIP LOCKED LIMIT 100"
                        )
                    )
                ).mappings().all()
                if not rows:
                    return
                try:
                    sections = build_sections([_outbox_item(dict(row)) for row in rows])
                    rendered = render_preview(sections)
                except Exception as error:
                    raise BriefingRenderError from error
                briefing_id = str(uuid.uuid4())
                await session.execute(
                    text("INSERT INTO briefings (id, rendered) VALUES (:id, :rendered)"),
                    {"id": briefing_id, "rendered": rendered},
                )
                for section, section_items in sections.items():
                    for item in section_items:
                        if item.source_type == "gmail":
                            continue
                        await session.execute(
                            text(
                                "INSERT INTO briefing_items (briefing_id, event_id, section) "
                                "VALUES (:briefing_id, :event_id, :section) ON CONFLICT DO NOTHING"
                            ),
                            {
                                "briefing_id": briefing_id,
                                "event_id": item.event_id,
                                "section": section,
                            },
                        )
                        await session.execute(
                            text(
                                "INSERT INTO briefing_item_content "
                                "(briefing_id, event_id, title, summary_tr, what_changed_tr, "
                                "why_important_tr) VALUES (:briefing_id, :event_id, :title, "
                                ":summary_tr, :what_changed_tr, :why_important_tr) "
                                "ON CONFLICT (briefing_id, event_id) DO NOTHING"
                            ),
                            {
                                "briefing_id": briefing_id,
                                "event_id": item.event_id,
                                "title": item.title,
                                "summary_tr": item.summary_tr,
                                "what_changed_tr": item.what_changed_tr,
                                "why_important_tr": item.why_important_tr,
                            },
                        )
                for row in rows:
                    await session.execute(
                        text("DELETE FROM briefing_outbox WHERE event_id = :event_id"),
                        {"event_id": row["event_id"]},
                    )
        except BriefingRenderError:
            raise
        except Exception as error:
            raise BriefingPersistenceError from error

    async def known_item(content_hash: str) -> bool:
        async with sessions() as session:
            return bool(
                await session.scalar(
                    text("SELECT 1 FROM event_sources WHERE source_item_id = :source_item_id"),
                    {"source_item_id": content_hash},
                )
            )

    async def mark_post_llm_failure(item: SourceItem, category: str, language: str | None) -> None:
        """Block automatic reprocessing after LLM work but before event persistence succeeds."""
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO post_llm_failures "
                    "(content_hash, failure_category, source_name, title, canonical_url, "
                    "published_at, language, retry_state, source_kind) "
                    "VALUES (:content_hash, :failure_category, :source_name, :title, "
                    ":canonical_url, :published_at, :language, 'blocked', :source_kind) "
                    "ON CONFLICT (content_hash) DO UPDATE SET "
                    "failure_category = EXCLUDED.failure_category, "
                    "source_name = EXCLUDED.source_name, "
                    "title = EXCLUDED.title, canonical_url = EXCLUDED.canonical_url, "
                    "published_at = EXCLUDED.published_at, language = EXCLUDED.language, "
                    "retry_state = 'blocked', updated_at = now()"
                ),
                {
                    "content_hash": item.content_hash,
                    "failure_category": category,
                    "source_name": item.source_name,
                    "title": item.title,
                    "canonical_url": item.canonical_url,
                    "published_at": item.source_published_at,
                    "language": language,
                    "source_kind": item.source_kind.value,
                },
            )

    async def is_post_llm_failed(content_hash: str) -> bool:
        async with sessions() as session:
            return bool(
                await session.scalar(
                    text("SELECT 1 FROM post_llm_failures WHERE content_hash = :content_hash"),
                    {"content_hash": content_hash},
                )
            )

    async def has_pending_briefing() -> bool:
        async with sessions() as session:
            return bool(await session.scalar(text("SELECT 1 FROM briefing_outbox LIMIT 1")))

    async def refresh_blocked_item(item: SourceItem, language: str | None) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "UPDATE post_llm_failures SET source_name = :source_name, title = :title, "
                    "canonical_url = :canonical_url, published_at = :published_at, "
                    "language = :language, updated_at = now() WHERE content_hash = :content_hash"
                ),
                {
                    "content_hash": item.content_hash,
                    "source_name": item.source_name,
                    "title": item.title,
                    "canonical_url": item.canonical_url,
                    "published_at": item.source_published_at,
                    "language": language,
                },
            )

    async def claim_blocked_item(
        content_hash: str, source_kind: str
    ) -> dict[str, object] | None:
        async with sessions.begin() as session:
            result = await session.execute(
                text(
                    "UPDATE post_llm_failures SET retry_state = 'retrying', "
                    "retry_attempts = retry_attempts + 1, updated_at = now() "
                    "WHERE content_hash = :content_hash AND retry_state = 'blocked' "
                    "AND source_kind = :source_kind "
                    "RETURNING source_name, title, canonical_url, published_at, language"
                ),
                {"content_hash": content_hash, "source_kind": source_kind},
            )
            row = result.mappings().one_or_none()
            return dict(row) if row else None

    async def resolve_blocked_item(content_hash: str) -> None:
        async with sessions.begin() as session:
            await session.execute(
                text("DELETE FROM post_llm_failures WHERE content_hash = :content_hash"),
                {"content_hash": content_hash},
            )

    return (
        persist_event,
        persist_briefing,
        known_item,
        mark_post_llm_failure,
        is_post_llm_failed,
        refresh_blocked_item,
        claim_blocked_item,
        resolve_blocked_item,
        has_pending_briefing,
    )


def _outbox_item(row: dict[str, object]) -> BriefingItem:
    """Rebuild a briefing item from safe, durable outbox metadata only."""
    try:
        source_urls = json.loads(str(row["source_urls_json"]))
    except (TypeError, ValueError):
        source_urls = []
    return BriefingItem(
        event_id=str(row["event_id"]),
        title=str(row["title"]),
        source_urls=[str(url) for url in source_urls if isinstance(url, str)],
        importance=int(row["importance"]),
        interest=int(row["interest"]),
        global_importance=int(row["global_importance"]),
        actionable=bool(row["actionable"]),
        video=bool(row["video"]),
        source_type=str(row["source_type"]),
        published_at=row["published_at"] if isinstance(row["published_at"], datetime) else None,
        why_watch=str(row["why_watch"]) if row["why_watch"] is not None else None,
        summary_tr=str(row["summary_tr"]) if row.get("summary_tr") is not None else None,
        what_changed_tr=(
            str(row["what_changed_tr"]) if row.get("what_changed_tr") is not None else None
        ),
        why_important_tr=(
            str(row["why_important_tr"]) if row.get("why_important_tr") is not None else None
        ),
    )
