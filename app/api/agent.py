"""Read-only, bounded integration API for external orchestration agents."""

import asyncio
import json
import secrets
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.briefing.presentation import safe_links
from app.config.settings import Settings
from app.knowledge.search import SafeEmailResult, SearchFilters, SearchResponse

router = APIRouter(prefix="/api/v1", tags=["agent-api"])

MAX_LIST_PAGE_SIZE = 20
MAX_ITEM_TEXT_CHARS = 600
MAX_FACTS_PER_ITEM = 5
MAX_INFERENCES_PER_ITEM = 3
MAX_LINKS_PER_ITEM = 3

AuditWriter = Callable[[str, str, int], Awaitable[None]]


class AgentApiRateLimiter:
    """Small process-local request limiter; it intentionally stores no caller or token value."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        now = time.monotonic()
        async with self._lock:
            cutoff = now - self._window_seconds
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max_requests:
                return False
            self._timestamps.append(now)
            return True


class AgentEmailAction(BaseModel):
    """Only existing safe Gmail classification metadata, never mailbox identity or body data."""

    model_config = ConfigDict(extra="forbid")
    classification: str
    action_summary: str | None = None
    deadline: datetime | None = None
    application_company: str | None = None
    recorded_at: datetime | None = None


class AgentBriefingItem(BaseModel):
    """Projection of a persisted briefing item with bounded facts and labelled inferences."""

    model_config = ConfigDict(extra="forbid")
    section: str
    title: str
    summary: str
    what_changed: str | None = None
    why_important: str | None = None
    published_at: datetime | None = None
    source_links: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    stored_inferences: list[str] = Field(default_factory=list)
    email_action: AgentEmailAction | None = None
    original_text: bool = False


class AgentBriefingDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    created_at: datetime
    items: list[AgentBriefingItem] = Field(default_factory=list)


class AgentBriefingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    created_at: datetime
    item_count: int = Field(ge=0)


class AgentBriefingPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AgentBriefingSummary] = Field(default_factory=list)
    next_before: datetime | None = None


class AgentSearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    occurred_at: datetime
    source_links: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    stored_inferences: list[str] = Field(default_factory=list)
    category_paths: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class AgentKnowledgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    answer_tr: str
    events: list[AgentSearchEvent] = Field(default_factory=list)
    email_actions: list[AgentEmailAction] = Field(default_factory=list)
    model_inferences: list[str] = Field(default_factory=list)


async def _audit(request: Request, endpoint: str, outcome: str, response_bytes: int) -> None:
    writer = getattr(request.app.state, "agent_api_audit_writer", None)
    if callable(writer):
        try:
            await writer(endpoint, outcome, response_bytes)
        except Exception:
            # Audit trouble must not disclose database detail or make retrieval unavailable.
            return


async def _guard(request: Request, endpoint: str) -> None:
    settings: Settings = request.app.state.agent_api_settings
    if not settings.agent_api_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    authorization = request.headers.get("authorization", "")
    expected = settings.agent_api_token_value
    if not authorization.startswith("Bearer ") or not secrets.compare_digest(
        authorization[7:], expected
    ):
        await _audit(request, endpoint, "unauthorized", 0)
        raise HTTPException(
            status_code=401,
            detail="Agent API authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    limiter: AgentApiRateLimiter = request.app.state.agent_api_rate_limiter
    if not await limiter.allow():
        await _audit(request, endpoint, "rate_limited", 0)
        raise HTTPException(status_code=429, detail="Agent API rate limit exceeded.")


async def _response(
    request: Request, endpoint: str, payload: BaseModel, *, status_code: int = 200
) -> JSONResponse:
    content = jsonable_encoder(payload)
    encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    settings: Settings = request.app.state.agent_api_settings
    if len(encoded) > settings.agent_api_max_response_bytes:
        await _audit(request, endpoint, "response_too_large", 0)
        raise HTTPException(status_code=413, detail="Agent API response exceeds configured limit.")
    await _audit(request, endpoint, "ok", len(encoded))
    return JSONResponse(content=content, status_code=status_code)


def _compact(value: str | None, limit: int = MAX_ITEM_TEXT_CHARS) -> str | None:
    if value is None:
        return None
    return " ".join(value.split())[:limit]


def _project_email(value: SafeEmailResult) -> AgentEmailAction:
    return AgentEmailAction(
        classification=value.classification[:64],
        action_summary=_compact(value.action_summary, 400),
        deadline=value.deadline,
        application_company=_compact(value.application_company, 160),
        recorded_at=value.recorded_at,
    )


def project_search_response(value: dict[str, object]) -> AgentKnowledgeResponse:
    """Drop provider/account metadata and bound every retained field before agent delivery."""
    result = SearchResponse.model_validate(value)
    events = [
        AgentSearchEvent(
            title=_compact(event.title, 320) or "Kaydedilmiş olay",
            occurred_at=event.occurred_at,
            source_links=safe_links(event.source_links)[:MAX_LINKS_PER_ITEM],
            verified_facts=[
                _compact(fact, 400) or "" for fact in event.verified_facts[:MAX_FACTS_PER_ITEM]
            ],
            stored_inferences=[
                _compact(item, 400) or ""
                for item in event.stored_inferences[:MAX_INFERENCES_PER_ITEM]
            ],
            category_paths=[_compact(item, 256) or "" for item in event.category_paths[:5]],
            entities=[_compact(item, 256) or "" for item in event.entities[:5]],
            topics=[_compact(item, 256) or "" for item in event.topics[:5]],
        )
        for event in result.events[:5]
    ]
    return AgentKnowledgeResponse(
        status=result.status,
        answer_tr=_compact(result.answer_tr, MAX_ITEM_TEXT_CHARS) or "",
        events=events,
        email_actions=[_project_email(item) for item in result.emails[:5]],
        model_inferences=[
            _compact(item, 400) or "" for item in result.model_inferences[:MAX_INFERENCES_PER_ITEM]
        ],
    )


@router.get("/briefings/latest", response_model=None)
async def latest_briefing(request: Request) -> JSONResponse:
    endpoint = "briefings.latest"
    await _guard(request, endpoint)
    callback = getattr(request.app.state, "agent_api_latest_briefing", None)
    if not callable(callback):
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(status_code=503, detail="Agent API is temporarily unavailable.")
    try:
        result = await callback()
    except LookupError:
        await _audit(request, endpoint, "not_found", 0)
        raise HTTPException(status_code=404, detail="No saved briefing found.") from None
    except Exception:
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(
            status_code=503, detail="Agent API is temporarily unavailable."
        ) from None
    return await _response(request, endpoint, AgentBriefingDetail.model_validate(result))


@router.get("/briefings", response_model=None)
async def list_briefings(
    request: Request,
    limit: int = 10,
    before: datetime | None = None,
) -> JSONResponse:
    endpoint = "briefings.list"
    await _guard(request, endpoint)
    if not 1 <= limit <= MAX_LIST_PAGE_SIZE:
        await _audit(request, endpoint, "invalid_request", 0)
        raise HTTPException(status_code=422, detail="Invalid briefing page limit.")
    callback = getattr(request.app.state, "agent_api_list_briefings", None)
    if not callable(callback):
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(status_code=503, detail="Agent API is temporarily unavailable.")
    try:
        result = await callback(limit, before)
        page = AgentBriefingPage.model_validate(result)
    except Exception:
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(
            status_code=503, detail="Agent API is temporarily unavailable."
        ) from None
    return await _response(request, endpoint, page)


@router.get("/briefings/{briefing_id}", response_model=None)
async def briefing_detail(briefing_id: str, request: Request) -> JSONResponse:
    endpoint = "briefings.detail"
    await _guard(request, endpoint)
    if len(briefing_id) > 64:
        await _audit(request, endpoint, "invalid_request", 0)
        raise HTTPException(status_code=422, detail="Invalid briefing identifier.")
    callback = getattr(request.app.state, "agent_api_briefing_detail", None)
    if not callable(callback):
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(status_code=503, detail="Agent API is temporarily unavailable.")
    try:
        result = await callback(briefing_id)
    except LookupError:
        await _audit(request, endpoint, "not_found", 0)
        raise HTTPException(status_code=404, detail="Saved briefing not found.") from None
    except Exception:
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(
            status_code=503, detail="Agent API is temporarily unavailable."
        ) from None
    return await _response(request, endpoint, AgentBriefingDetail.model_validate(result))


@router.post("/knowledge/search", response_model=None)
async def knowledge_search(request: Request) -> JSONResponse:
    endpoint = "knowledge.search"
    await _guard(request, endpoint)
    settings: Settings = request.app.state.agent_api_settings
    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > settings.agent_api_max_request_bytes
    ):
        await _audit(request, endpoint, "request_too_large", 0)
        raise HTTPException(status_code=413, detail="Agent API request exceeds configured limit.")
    body = await request.body()
    if len(body) > settings.agent_api_max_request_bytes:
        await _audit(request, endpoint, "request_too_large", 0)
        raise HTTPException(status_code=413, detail="Agent API request exceeds configured limit.")
    try:
        filters = SearchFilters.model_validate_json(body)
    except ValidationError:
        await _audit(request, endpoint, "invalid_request", 0)
        raise HTTPException(status_code=422, detail="Invalid knowledge search request.") from None
    callback = getattr(request.app.state, "ask_callback", None)
    if not callable(callback):
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(status_code=503, detail="Agent API is temporarily unavailable.")
    try:
        result = await callback(filters)
        response = project_search_response(result)
    except Exception:
        await _audit(request, endpoint, "unavailable", 0)
        raise HTTPException(
            status_code=503, detail="Agent API is temporarily unavailable."
        ) from None
    return await _response(request, endpoint, response)
