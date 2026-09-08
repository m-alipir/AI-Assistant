"""Bounded, provenance-first user search over retained event and email metadata."""

import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.knowledge.repository import HybridRetriever, InMemoryKnowledgeRepository
from app.knowledge.schemas import EventDraft, Inference, RetrievalQuery, SourceBackedClaim
from app.llm.core import Router, usage_breakdown

SourceType = Literal["rss", "youtube", "gmail"]
SEARCH_CANDIDATE_LIMIT = 100
logger = logging.getLogger(__name__)


class KnowledgeSearchError(RuntimeError):
    """Safe operational category for retrieval failures; never carries database/provider text."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class SearchFilters(BaseModel):
    """Deterministic limits applied before candidate ranking or optional model use."""

    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    since: datetime | None = None
    until: datetime | None = None
    entity: str | None = Field(default=None, max_length=256)
    category: str | None = Field(default=None, max_length=256)
    topic: str | None = Field(default=None, max_length=256)
    source_type: SourceType | None = None
    limit: int = Field(default=5, ge=1, le=10)


class SearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    title: str
    occurred_at: datetime
    source_links: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    stored_inferences: list[str] = Field(default_factory=list)
    category_paths: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class SafeEmailResult(BaseModel):
    """Searchable Gmail record: no subject, sender, body, or token is retained here."""

    model_config = ConfigDict(extra="forbid")
    classification: str
    action_summary: str | None = None
    deadline: datetime | None = None
    application_company: str | None = None
    recorded_at: datetime | None = None


class AskSynthesis(BaseModel):
    """Optional reasoner result, visibly separate from source-backed claims."""

    model_config = ConfigDict(extra="forbid")
    answer_tr: str
    model_inferences: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "insufficient_sources"]
    answer_tr: str
    events: list[SearchEvent] = Field(default_factory=list)
    emails: list[SafeEmailResult] = Field(default_factory=list)
    model_inferences: list[str] = Field(default_factory=list)
    llm: dict[str, object]


FetchRows = Callable[[SearchFilters], Awaitable[tuple[list[SearchEvent], list[SafeEmailResult]]]]


class KnowledgeSearchService:
    """Apply deterministic date/metadata narrowing then the existing hybrid ranker."""

    def __init__(self, fetch_rows: FetchRows, clock: Callable[[], datetime] | None = None) -> None:
        self._fetch_rows = fetch_rows
        self._clock = clock or (lambda: datetime.now(UTC))

    async def search(
        self, filters: SearchFilters
    ) -> tuple[list[SearchEvent], list[SafeEmailResult]]:
        effective = _with_inferred_time(filters, self._clock())
        events, emails = await self._fetch_rows(effective)
        narrowed = [event for event in events if _matches_metadata(event, effective)]
        repository = InMemoryKnowledgeRepository()
        for event in narrowed:
            repository.add_event(_to_event_draft(event))
        ranked = HybridRetriever(repository).search(
            RetrievalQuery(
                text=effective.question,
                since=effective.since,
                until=effective.until,
                limit=effective.limit,
            )
        )
        return [
            next(event for event in narrowed if event.event_id == result.event.event_id)
            for result in ranked
        ], emails[: effective.limit]


async def answer_question(
    filters: SearchFilters, service: KnowledgeSearchService, router: Router | None
) -> SearchResponse:
    """Answer only from bounded retained candidates; no candidates means no model request."""
    events, emails = await service.search(filters)
    if not events and not emails:
        return SearchResponse(
            status="insufficient_sources",
            answer_tr="Yeterli kaynak bulunamadı.",
            llm=usage_breakdown([]),
        )
    answer = (
        "İlgili kaynaklar aşağıda listelenmiştir. Kaynakla doğrulanmış bilgiler ve çıkarımlar "
        "ayrı gösterilir."
    )
    model_inferences: list[str] = []
    llm = usage_breakdown([])
    if router is not None:
        try:
            prefix = (
                "Türkçe cevap ver. Yalnızca aşağıdaki sınırlı, kaynak-provenanslı adaylara "
                "dayan. Kaynakta olmayan gerçekleri uydurma. Çıkarımları ayrı "
                "model_inferences listesine koy.\n"
            )
            question_limit = max(router.input_char_limit("reasoner") - len(prefix) - 24, 0)
            question = filters.question[:question_limit]
            context_budget = max(
                router.input_char_limit("reasoner") - len(prefix) - len(question) - 24, 0
            )
            context = _bounded_context(events, emails, context_budget)
            content_hash = hashlib.sha256(f"{question}|{context}".encode()).hexdigest()
            synthesis = await router.structured(
                "reasoner",
                f"{prefix}SORU: {question}\nADAYLAR:\n{context}",
                content_hash,
                AskSynthesis,
                "ask-v2",
                "v1",
                optional=True,
            )
            answer, model_inferences = synthesis.answer_tr, synthesis.model_inferences
        except Exception:  # The optional summary must never hide already-retrieved sources.
            logger.warning(
                "knowledge_search_model_unavailable",
                extra={"search_error_category": "model_schema_or_provider_error"},
            )
            answer = "İlgili kaynaklar bulundu; model özeti şu anda kullanılamıyor."
        llm = usage_breakdown(router.calls)
    return SearchResponse(
        status="ok",
        answer_tr=answer,
        events=events,
        emails=emails,
        model_inferences=model_inferences,
        llm=llm,
    )


async def fetch_sql_candidates(
    engine: AsyncEngine, filters: SearchFilters
) -> tuple[list[SearchEvent], list[SafeEmailResult]]:
    """Read only compact facts, metadata and URLs; email bodies are never selected."""
    try:
        since = (filters.since or datetime.now(UTC) - timedelta(days=180)).astimezone(UTC)
        until = (filters.until or datetime.now(UTC)).astimezone(UTC)
        source_filter = ""
        query_parameters: dict[str, object] = {
            "since": since,
            "until": until,
            "candidate_limit": SEARCH_CANDIDATE_LIMIT,
        }
        if filters.source_type in {"rss", "youtube"}:
            source_filter = (
                "AND EXISTS (SELECT 1 FROM event_sources filter_es "
                "WHERE filter_es.event_id = e.id AND filter_es.source_kind = :source_kind) "
            )
            query_parameters["source_kind"] = filters.source_type
        event_query = text(
            "SELECT e.id, e.canonical_title, e.occurred_at, "
            "coalesce(m.category_paths_json, '[]') AS category_paths_json, "
            "coalesce(m.entities_json, '[]') AS entities_json, "
            "coalesce(m.topics_json, '[]') AS topics_json, "
            "ARRAY(SELECT c.statement FROM claims c WHERE c.event_id = e.id "
            "ORDER BY c.id LIMIT 8) AS facts, "
            "ARRAY(SELECT i.inference_text FROM inferences i WHERE i.event_id = e.id "
            "ORDER BY i.id LIMIT 5) AS inferences, "
            "ARRAY(SELECT es.canonical_url FROM event_sources es "
            "WHERE es.event_id = e.id AND es.canonical_url IS NOT NULL "
            "ORDER BY es.canonical_url LIMIT 3) AS source_links, "
            "ARRAY(SELECT DISTINCT es.source_kind FROM event_sources es "
            "WHERE es.event_id = e.id AND es.source_kind IS NOT NULL) AS source_kinds "
            "FROM events e "
            "LEFT JOIN event_search_metadata m ON m.event_id = e.id "
            "WHERE e.occurred_at >= :since AND e.occurred_at <= :until "
            f"{source_filter}"
            "GROUP BY e.id, e.canonical_title, e.occurred_at, m.category_paths_json, "
            "m.entities_json, m.topics_json ORDER BY e.occurred_at DESC "
            "LIMIT :candidate_limit"
        )
        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(event_query, query_parameters)
                )
                .mappings()
                .all()
            )
            emails: list[SafeEmailResult] = []
            if filters.source_type == "gmail" or _asks_for_email(filters.question):
                email_rows = (
                    (
                        await connection.execute(
                        text(
                            "SELECT classification, action_summary, deadline, application_company, "
                            "created_at AS recorded_at "
                            "FROM email_classifications "
                            "WHERE created_at >= :since AND created_at <= :until "
                            "AND classification IN "
                            "('action_required', 'application_update', 'recruiter', "
                            "'security', 'transactional') "
                            "ORDER BY created_at DESC NULLS LAST LIMIT :email_limit"
                        ),
                        {
                            "since": since,
                            "until": until,
                            "email_limit": min(max(filters.limit * 5, filters.limit), 50),
                        },
                        )
                    )
                    .mappings()
                    .all()
                )
                emails = [_safe_email_from_row(row) for row in email_rows]
        events = [
            event
            for row in rows
            if filters.source_type is None or filters.source_type in set(row["source_kinds"] or [])
            if (event := _safe_event_from_row(row)) is not None
        ]
        return events, emails
    except (ProgrammingError, DBAPIError) as error:
        raise KnowledgeSearchError(_database_error_category(error)) from error
    except SQLAlchemyError as error:
        raise KnowledgeSearchError("search_sql_error") from error
    except (KeyError, TypeError, ValidationError, ValueError) as error:
        raise KnowledgeSearchError("search_result_shape_error") from error


def _safe_event_from_row(row: object) -> SearchEvent | None:
    """Skip one malformed legacy row rather than making the whole user search unavailable."""
    try:
        mapping = dict(row)
        return SearchEvent(
            event_id=str(mapping["id"]),
            title=str(mapping["canonical_title"]),
            occurred_at=mapping["occurred_at"],
            source_links=[str(url) for url in (mapping["source_links"] or []) if url],
            verified_facts=[str(fact) for fact in (mapping["facts"] or []) if fact],
            stored_inferences=[
                str(inference) for inference in (mapping["inferences"] or []) if inference
            ],
            category_paths=_json_list(mapping["category_paths_json"]),
            entities=_json_list(mapping["entities_json"]),
            topics=_json_list(mapping["topics_json"]),
        )
    except (KeyError, TypeError, ValidationError, ValueError):
        logger.warning(
            "knowledge_search_legacy_event_skipped",
            extra={"search_error_category": "legacy_event_shape_error"},
        )
        return None


def _safe_email_from_row(row: object) -> SafeEmailResult:
    """Map legacy classification rows using only their safe retained fields."""
    mapping = dict(row)
    return SafeEmailResult(
        classification=str(mapping.get("classification") or "other"),
        action_summary=(
            str(mapping["action_summary"]) if mapping.get("action_summary") is not None else None
        ),
        deadline=mapping.get("deadline"),
        application_company=(
            str(mapping["application_company"])
            if mapping.get("application_company") is not None
            else None
        ),
        recorded_at=mapping.get("recorded_at"),
    )


def _database_error_category(error: Exception) -> str:
    """Classify only the operational class, never a SQL string or driver message."""
    text_value = str(getattr(error, "orig", "")).casefold()
    if "does not exist" in text_value or "undefined" in text_value:
        return "search_migration_or_schema_error"
    return "search_sql_error"


def _with_inferred_time(filters: SearchFilters, now: datetime) -> SearchFilters:
    if filters.since is not None:
        return filters
    question = filters.question.casefold()
    now = now.astimezone(UTC)
    if "bu hafta" in question:
        week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=now.weekday()
        )
        return filters.model_copy(update={"since": week_start})
    match = re.search(r"son\s+(\d{1,3})\s+g[üu]n", question)
    if match:
        return filters.model_copy(update={"since": now - timedelta(days=int(match.group(1)))})
    return filters


def _matches_metadata(event: SearchEvent, filters: SearchFilters) -> bool:
    def matches(values: list[str], value: str | None, prefix: bool = False) -> bool:
        if value is None:
            return True
        candidate = value.casefold()
        return any(
            item.casefold().startswith(candidate) if prefix else item.casefold() == candidate
            for item in values
        )

    return (
        matches(event.entities, filters.entity)
        and matches(event.category_paths, filters.category, prefix=True)
        and matches(event.topics, filters.topic)
    )


def _to_event_draft(event: SearchEvent) -> EventDraft:
    return EventDraft(
        event_id=event.event_id,
        title=event.title,
        occurred_at=event.occurred_at,
        category_paths=event.category_paths,
        entities=event.entities,
        topics=event.topics,
        source_item_ids=[event.event_id],
        claims=[
            SourceBackedClaim(statement=fact, source_item_id=event.event_id)
            for fact in event.verified_facts
        ],
        inferences=[
            Inference(statement=item, inference_type="stored") for item in event.stored_inferences
        ],
        embedding=[1.0],
    )


def _bounded_context(
    events: list[SearchEvent], emails: list[SafeEmailResult], max_chars: int
) -> str:
    """Serialize only compact source-backed fields under the role-configured ceiling."""
    event_context = [
        {
            "id": event.event_id,
            "date": event.occurred_at.isoformat(),
            "title": event.title[:320],
            "facts": [fact[:500] for fact in event.verified_facts[:3]],
            "sources": [url[:300] for url in event.source_links[:2]],
        }
        for event in events[:5]
    ]
    email_context = [
        {
            "classification": email.classification,
            "action_summary": email.action_summary[:400] if email.action_summary else None,
            "deadline": email.deadline.isoformat() if email.deadline else None,
            "application_company": email.application_company[:160]
            if email.application_company
            else None,
        }
        for email in emails[:5]
    ]
    serialized = json.dumps(
        {"events": event_context, "safe_emails": email_context}, ensure_ascii=False
    )
    if max_chars <= 0:
        return ""
    return serialized if len(serialized) <= max_chars else serialized[:max_chars]


def _json_list(value: object) -> list[str]:
    try:
        loaded = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _asks_for_email(question: str) -> bool:
    return bool(re.search(r"e-?posta|email|mail", question.casefold()))
