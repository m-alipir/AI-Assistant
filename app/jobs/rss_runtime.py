"""The small RSS-only runtime path used by the local admin manual trigger."""

import json
import math
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.briefing.core import BriefingItem, build_sections, render_preview
from app.collectors.article import ArticleContent, ArticleFetcher
from app.collectors.rss import HttpFeedFetcher, RssCollector
from app.config.sources import SourceCatalog
from app.correlation.core import CorrelationResult, MemoryEvent
from app.correlation.runtime import CorrelationRuntime, correlation_content_hash
from app.dedup.cache import InMemoryDedupCache
from app.ingestion.pipeline import DeterministicIngestionPipeline
from app.ingestion.schemas import SourceItem
from app.knowledge.clustering import ClusterCandidate, find_cluster
from app.llm.core import BudgetExceeded, ExtractionFlow, ProviderBusy, Router


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
    article_fetch_errors: int = 0
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
                    "article_fetch_error": self.article_fetch_errors,
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
CorrelateEvent = Callable[[str, object, object, Router], Awaitable[None]]


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
        correlate_event: CorrelateEvent | None = None,
        article_fetcher: ArticleFetcher | None = None,
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
        self._correlate_event = correlate_event or _ignore_correlation
        self._article_fetcher = article_fetcher or ArticleFetcher()

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
                extraction_content = f"TITLE: {item.title}\nSNIPPET: {item.snippet or ''}"
                if gate.needs_full_extraction and item.canonical_url:
                    try:
                        article = await self._article_fetcher.fetch(item.canonical_url)
                        extraction_content = _article_extraction_content(item.title, article)
                    except Exception:
                        # A public-page failure safely falls back to metadata, without an LLM retry.
                        counts.article_fetch_errors += 1
                        counts.errors.append(f"{item.source_name}: article_fetch_error")
                try:
                    extracted = await self._flow.extract(extraction_content, item.content_hash)
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
                    await self._flow.embed_extraction(item.title, extracted, item.content_hash)
                except (BudgetExceeded, ProviderBusy):
                    # Embeddings improve retrieval but must not discard a validated event.
                    pass
                except Exception:
                    # Provider failures are accounted by the router; no source payload is logged.
                    pass
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
                try:
                    await self._correlate_event(event_id, gate, extracted, self._flow._router)
                except Exception:
                    pass
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


async def _ignore_post_llm_failure(item: SourceItem, category: str, language: str | None) -> None:
    """Keep standalone/offline jobs side-effect free without a durable guard."""


async def _not_post_llm_failed(content_hash: str) -> bool:
    return False


async def _ignore_refresh_blocked_item(item: SourceItem, language: str | None) -> None:
    """Keep standalone/offline jobs side-effect free without a durable guard."""


async def _no_pending_briefing() -> bool:
    return False


async def _ignore_correlation(
    event_id: str, gate: object, extracted: object, router: Router
) -> None:
    """Keep isolated runtime tests and deployments without persistence wiring operational."""
    return None


def _article_extraction_content(title: str, article: ArticleContent) -> str:
    """Keep untrusted article text clearly delimited and under the existing extractor limit."""
    return f"TITLE: {title}\nARTICLE:\n{article.text[:24_000]}"


def _vector_literal(values: list[float] | None) -> str | None:
    """Serialize finite provider vectors for PostgreSQL without retaining source text."""
    if values is None:
        return None
    if not values or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) for value in values
    ):
        raise ValueError("embedding vector must contain finite numeric values")
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _json_strings(value: object) -> list[str]:
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return [str(item) for item in decoded if item] if isinstance(decoded, list) else []


def _merged_strings(existing: list[str], incoming: list[str]) -> list[str]:
    """Keep current metadata plus new-source values without case-only duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *incoming]:
        normalized = " ".join(value.casefold().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(value)
    return merged


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
    CorrelateEvent,
]:
    """Return durable provenance/briefing writers without retaining raw provider payloads."""

    async def persist_event(item: SourceItem, gate: object, extracted: object) -> str:
        new_event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item.content_hash))
        event_embedding = getattr(extracted, "_event_embedding", None)
        embedding_dimensions = int(getattr(extracted, "_embedding_dimensions", 0) or 0)
        embedding_model_id = getattr(extracted, "_embedding_model_id", None)
        if not isinstance(event_embedding, list) or len(event_embedding) != embedding_dimensions:
            event_embedding, embedding_dimensions, embedding_model_id = None, 0, None
        async with sessions.begin() as session:
            candidate_rows = (
                (
                    await session.execute(
                        text(
                            "SELECT e.id, e.canonical_title, e.occurred_at, "
                            "coalesce(m.entities_json, '[]') AS entities_json, "
                            "coalesce(m.category_paths_json, '[]') AS category_paths_json, "
                            "coalesce(m.topics_json, '[]') AS topics_json, "
                            "ARRAY(SELECT c.statement FROM claims c WHERE c.event_id = e.id "
                            "ORDER BY c.id LIMIT 8) AS claims "
                            "FROM events e LEFT JOIN event_search_metadata m ON m.event_id = e.id "
                            "WHERE e.occurred_at >= :since AND e.occurred_at <= :until "
                            "ORDER BY e.occurred_at DESC LIMIT 50"
                        ),
                        {
                            "since": item.freshness_reference_at - timedelta(hours=72),
                            "until": item.freshness_reference_at + timedelta(hours=72),
                        },
                    )
                )
                .mappings()
                .all()
            )
            candidates = [
                ClusterCandidate(
                    event_id=str(row["id"]),
                    title=str(row["canonical_title"]),
                    occurred_at=row["occurred_at"],
                    entities=_json_strings(row["entities_json"]),
                    claims=[str(value) for value in (row["claims"] or []) if value],
                )
                for row in candidate_rows
            ]
            match = find_cluster(
                title=item.title,
                occurred_at=item.freshness_reference_at,
                entities=list(gate.entities),
                claims=[claim.statement for claim in extracted.claims],
                candidates=candidates,
            )
            event_id = match.event_id if match else new_event_id
            metadata_row = next((row for row in candidate_rows if str(row["id"]) == event_id), None)
            category_paths = _merged_strings(
                _json_strings(metadata_row["category_paths_json"]) if metadata_row else [],
                list(gate.category_paths),
            )
            entities = _merged_strings(
                _json_strings(metadata_row["entities_json"]) if metadata_row else [],
                list(gate.entities),
            )
            topics = _merged_strings(
                _json_strings(metadata_row["topics_json"]) if metadata_row else [],
                list(gate.topics),
            )
            await session.execute(
                text(
                    "INSERT INTO events (id, canonical_title, occurred_at, embedding_dimensions, "
                    "embedding_model_id, embedding, raw_content, status) "
                    "VALUES (:id, :title, :occurred_at, :embedding_dimensions, "
                    ":embedding_model_id, CAST(:embedding AS vector), :raw_content, 'active') "
                    "ON CONFLICT (id) DO UPDATE SET embedding = CASE "
                    "WHEN events.embedding IS NULL THEN EXCLUDED.embedding "
                    "ELSE events.embedding END, "
                    "embedding_dimensions = CASE WHEN events.embedding IS NULL "
                    "THEN EXCLUDED.embedding_dimensions ELSE events.embedding_dimensions END, "
                    "embedding_model_id = CASE WHEN events.embedding IS NULL "
                    "THEN EXCLUDED.embedding_model_id ELSE events.embedding_model_id END"
                ),
                {
                    "id": event_id,
                    "title": item.title,
                    "occurred_at": item.freshness_reference_at,
                    "embedding_dimensions": embedding_dimensions,
                    "embedding_model_id": embedding_model_id,
                    "embedding": _vector_literal(event_embedding),
                    "raw_content": item.snippet,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO event_sources "
                    "(event_id, source_item_id, relation, canonical_url, source_kind) "
                    "VALUES (:event_id, :source_item_id, :relation, :canonical_url, :source_kind) "
                    "ON CONFLICT (event_id, source_item_id) DO UPDATE SET "
                    "canonical_url = EXCLUDED.canonical_url, source_kind = EXCLUDED.source_kind"
                ),
                {
                    "event_id": event_id,
                    "source_item_id": item.content_hash,
                    "relation": "corroborating" if match else "primary",
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
                    "category_paths": json.dumps(category_paths),
                    "entities": json.dumps(entities),
                    "topics": json.dumps(topics),
                },
            )
            claim_embeddings = getattr(extracted, "_claim_embeddings", [])
            for index, claim in enumerate(extracted.claims):
                claim_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL, f"{event_id}:{item.content_hash}:{claim.statement}"
                    )
                )
                claim_embedding = (
                    claim_embeddings[index]
                    if index < len(claim_embeddings) and isinstance(claim_embeddings[index], list)
                    else None
                )
                if (
                    not isinstance(claim_embedding, list)
                    or len(claim_embedding) != embedding_dimensions
                ):
                    claim_embedding = None
                await session.execute(
                    text(
                        "INSERT INTO claims (id, event_id, source_item_id, statement, "
                        "source_locator, embedding_model_id, embedding_dimensions, embedding) "
                        "VALUES (:id, :event_id, :source_item_id, :statement, :source_locator, "
                        ":embedding_model_id, :embedding_dimensions, CAST(:embedding AS vector)) "
                        "ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": claim_id,
                        "event_id": event_id,
                        "source_item_id": item.content_hash,
                        "statement": claim.statement,
                        "source_locator": claim.source_locator,
                        "embedding_model_id": embedding_model_id if claim_embedding else None,
                        "embedding_dimensions": embedding_dimensions if claim_embedding else None,
                        "embedding": _vector_literal(claim_embedding),
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

    async def correlate_event(
        event_id: str, gate: object, extracted: object, router: Router
    ) -> None:
        """Use the reasoner only after a bounded same-entity SQL retrieval."""
        async with sessions() as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "SELECT e.id, e.occurred_at, e.canonical_title, "
                            "coalesce(m.entities_json, '[]') AS entities_json, "
                        "ARRAY(SELECT c.id FROM claims c WHERE c.event_id = e.id "
                        "ORDER BY c.id LIMIT 12) AS claim_ids "
                            "FROM events e LEFT JOIN event_search_metadata m ON m.event_id = e.id "
                            "WHERE e.occurred_at >= :since ORDER BY e.occurred_at DESC LIMIT 51"
                        ),
                        {"since": datetime.now(UTC) - timedelta(days=180)},
                    )
                )
                .mappings()
                .all()
            )
        current_row = next((row for row in rows if str(row["id"]) == event_id), None)
        if current_row is None:
            return
        current = MemoryEvent(
            event_id=event_id,
            occurred_at=current_row["occurred_at"],
            compact_summary=str(getattr(extracted, "compact_summary", ""))[:1200],
            importance=int(getattr(gate, "importance", 0)),
            global_importance=int(getattr(gate, "global_importance", 0)),
            entities=_json_strings(current_row["entities_json"]),
            claim_ids=[str(value) for value in (current_row["claim_ids"] or [])],
        )
        entities = {value.casefold() for value in current.entities}
        candidates = [
            (
                MemoryEvent(
                    event_id=str(row["id"]),
                    occurred_at=row["occurred_at"],
                    compact_summary=str(row["canonical_title"])[:1200],
                    importance=0,
                    global_importance=0,
                    entities=_json_strings(row["entities_json"]),
                    claim_ids=[str(value) for value in (row["claim_ids"] or [])],
                ),
                0.8,
            )
            for row in rows
            if str(row["id"]) != event_id
            and entities & {value.casefold() for value in _json_strings(row["entities_json"])}
        ]
        if not candidates:
            return

        async def reasoner(
            version: str, payload: str, result_type: type[CorrelationResult]
        ) -> CorrelationResult:
            return await router.structured(
                "reasoner",
                "Correlate only the supplied compact records; never invent facts.\n" + payload,
                correlation_content_hash(current, [candidate for candidate, _ in candidates[:5]]),
                result_type,
                version,
                "v1",
                optional=True,
            )

        result = await CorrelationRuntime().correlate(current, candidates, reasoner)
        if result is None:
            return
        inference_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{event_id}:{result.relation_type}:{','.join(result.linked_event_ids)}",
            )
        )
        async with sessions.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO inferences (id, event_id, inference_text, inference_type) VALUES "
                    "(:id, :event_id, :inference_text, :inference_type) ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": inference_id,
                    "event_id": event_id,
                    "inference_text": result.explanation,
                    "inference_type": result.relation_type,
                },
            )
            for target_event_id in result.linked_event_ids:
                relation_id = str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"{inference_id}:{target_event_id}")
                )
                await session.execute(
                    text(
                        "INSERT INTO event_relations (id, source_event_id, target_event_id, "
                        "relation_type, inference_id, confidence, status) VALUES "
                        "(:id, :source, :target, :relation, "
                        ":inference, :confidence, :status) ON CONFLICT (id) DO NOTHING"
                    ),
                    {
                        "id": relation_id,
                        "source": event_id,
                        "target": target_event_id,
                        "relation": result.relation_type,
                        "inference": inference_id,
                        "confidence": result.confidence,
                        "status": result.status,
                    },
                )

    async def persist_briefing(items: list[BriefingItem]) -> None:
        """Atomically drain safe pending candidates so a retry cannot duplicate a briefing."""
        try:
            async with sessions.begin() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT event_id, title, source_urls_json, importance, interest, "
                                "global_importance, actionable, video, source_type, published_at, "
                                "why_watch, summary_tr, what_changed_tr, why_important_tr "
                                "FROM briefing_outbox ORDER BY created_at ASC "
                                "FOR UPDATE SKIP LOCKED LIMIT 100"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
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

    async def claim_blocked_item(content_hash: str, source_kind: str) -> dict[str, object] | None:
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
        correlate_event,
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
