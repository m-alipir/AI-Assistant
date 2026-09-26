"""FastAPI application factory and production ASGI entrypoint."""

import asyncio
import json
import logging
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.admin import router as admin_router
from app.api.agent import (
    AgentApiRateLimiter,
    AgentBriefingDetail,
    AgentBriefingItem,
    AgentBriefingPage,
    AgentBriefingSummary,
    AgentEmailAction,
)
from app.api.agent import router as agent_router
from app.api.health import router as health_router
from app.briefing.core import BriefingItem
from app.briefing.presentation import (
    compact_sentences,
    legacy_sections,
    order_briefing_items,
    safe_links,
)
from app.collectors.article import ArticleFetcher
from app.collectors.rss import HttpFeedFetcher, RssCollector
from app.collectors.youtube import YouTubeDiscovery
from app.config.models import load_model_settings
from app.config.onboarding import GmailPollingPreference, OnboardingRepository
from app.config.settings import Settings, get_settings
from app.config.source_repository import ManagedSourceCreate, SourceRepository
from app.config.sources import SourceCatalog, YouTubeSourceConfig, load_source_catalog
from app.db.session import check_database_ready, create_engine, create_session_factory
from app.email.core import TokenCipher
from app.email.gmail_api import GmailApiClient
from app.email.oauth import GmailOAuth
from app.ingestion.schemas import SourceItem, SourceKind, TimestampConfidence
from app.ingestion.source_health import database_source_health
from app.jobs.gmail_runtime import GmailAccountRecord, GmailRun, GmailRuntimeJob
from app.jobs.retention import RetentionJob, RetentionScheduler
from app.jobs.rss_runtime import RssRuntimeJob, database_persistence
from app.jobs.scheduler import (
    DailyScheduler,
    GmailPollingScheduler,
    RuntimeRunCoordinator,
    format_failure_summary,
    wait_until,
)
from app.jobs.youtube_runtime import YouTubeRuntimeJob
from app.knowledge.reembedding import ReembeddingRecord, ReembeddingService
from app.knowledge.search import (
    KnowledgeSearchService,
    SearchFilters,
    SearchResponse,
    answer_question,
    fetch_sql_candidates,
    fetch_sql_event,
)
from app.llm.core import (
    BudgetTracker,
    ExtractionFlow,
    InMemoryResultCache,
    OpenRouterClient,
    ProviderCallCoordinator,
    Router,
    usage_breakdown,
)
from app.llm.repository import SqlAlchemyLlmRepository
from app.notifications.core import (
    Notification,
    NotificationKind,
    database_dispatcher,
    deliver_ordered,
    notification_key,
)
from app.notifications.ntfy import NtfyNotifier
from app.observability.logging import bind_request_id, configure_logging, reset_request_id
from app.security import ProcessRateLimiter, opaque_client_key
from app.telegram.api import router as telegram_router
from app.telegram.core import TelegramBotClient
from app.telegram.service import TelegramWebhookHandler
from app.telegram.source_categories import (
    run_source_category_question_worker,
    send_source_category_question,
    source_category_question_was_delivered,
    telegram_delivery_channel,
)

ReadinessCheck = Callable[[], Awaitable[bool]]
logger = logging.getLogger(__name__)


def _delivery_delay_note(target_at: datetime, delivered_at: datetime) -> str | None:
    """Return a short local-time note only when delivery missed its configured target."""
    seconds_late = (delivered_at.astimezone(UTC) - target_at.astimezone(UTC)).total_seconds()
    total_seconds = int(seconds_late)
    if total_seconds <= 0:
        return None
    minutes, seconds = divmod(total_seconds, 60)
    delay = f"{minutes} dk {seconds} sn" if minutes else f"{seconds} sn"
    return f"Hedef {target_at.strftime('%H:%M')} idi; {delay} gecikme."


def create_app(
    settings: Settings | None = None,
    readiness_check: ReadinessCheck | None = None,
) -> FastAPI:
    """Build the API with injectable readiness behavior for isolated unit tests."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level, secrets=active_settings.logging_secret_values())
    engine: AsyncEngine | None = None

    if readiness_check is None:
        engine = create_engine(active_settings)

        async def database_readiness() -> bool:
            assert engine is not None
            return await check_database_ready(engine)

        readiness_check = database_readiness

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> AsyncIterator[None]:
        source_category_worker_task: asyncio.Task[None] | None = None
        source_category_worker_stop: asyncio.Event | None = None
        if active_settings.managed_sources_bootstrap:
            repository = getattr(lifespan_app.state, "source_repository", None)
            if repository is None:
                raise RuntimeError("managed source bootstrap requires a database")
            if await repository.needs_yaml_bootstrap():
                seed = load_source_catalog(active_settings.admin_sources_path)
                await repository.bootstrap_yaml(seed)
        scheduler = getattr(lifespan_app.state, "scheduler", None)
        preferences = getattr(lifespan_app.state, "onboarding_repository", None)
        gmail_scheduler = getattr(lifespan_app.state, "gmail_polling_scheduler", None)
        if scheduler and preferences:
            preference = await preferences.scheduler_preference()
            if preference is not None:
                await scheduler.configure(preference.enabled, preference.daily_time)
        if gmail_scheduler and preferences:
            preference = await preferences.gmail_polling_preference()
            await gmail_scheduler.configure(preference.interval_minutes)
        retention_scheduler = getattr(lifespan_app.state, "retention_scheduler", None)
        if scheduler:
            scheduler.start()
        if gmail_scheduler:
            gmail_scheduler.start()
        if retention_scheduler:
            retention_scheduler.start()
        if active_settings.telegram_enabled and active_settings.telegram_mode == "webhook":
            source_category_worker = getattr(
                lifespan_app.state, "run_source_category_question_worker", None
            )
            if callable(source_category_worker):
                source_category_worker_stop = asyncio.Event()
                source_category_worker_task = asyncio.create_task(
                    source_category_worker(source_category_worker_stop),
                    name="telegram-source-category-questions",
                )
        yield
        if source_category_worker_stop is not None:
            source_category_worker_stop.set()
        if source_category_worker_task is not None:
            source_category_worker_task.cancel()
            await asyncio.gather(source_category_worker_task, return_exceptions=True)
        if retention_scheduler:
            await retention_scheduler.stop()
        if scheduler:
            await scheduler.stop()
        if gmail_scheduler:
            await gmail_scheduler.stop()
        if lifespan_app.state.engine is not None:
            await lifespan_app.state.engine.dispose()

    app = FastAPI(
        title="Personal Intelligence System",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if active_settings.app_env.casefold() == "production" else "/docs",
        redoc_url=None if active_settings.app_env.casefold() == "production" else "/redoc",
        openapi_url=None if active_settings.app_env.casefold() == "production" else "/openapi.json",
    )
    @app.middleware("http")
    async def protect_admin_and_add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Apply production-only access control, CSRF origin checks, and browser hardening."""
        request.state.csp_nonce = secrets.token_urlsafe(18)
        request_id = secrets.token_urlsafe(12)
        request.state.request_id = request_id
        request_context = bind_request_id(request_id)
        is_admin = request.url.path == "/admin" or request.url.path.startswith("/admin/")
        is_agent_api = request.url.path.startswith("/api/v1/")
        def finalize(response: Response) -> Response:
            response.headers.setdefault("X-Request-ID", request_id)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy", "camera=(), geolocation=(), microphone=()"
            )
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
                "img-src 'self' data: https:; connect-src 'self'; "
                f"script-src 'self' 'nonce-{request.state.csp_nonce}'; "
                f"style-src 'self' 'nonce-{request.state.csp_nonce}'",
            )
            if is_admin or is_agent_api:
                response.headers.setdefault("Cache-Control", "no-store")
            if is_agent_api:
                response.headers.setdefault("Vary", "Authorization")
            if active_settings.force_https:
                response.headers.setdefault(
                    "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                )
            return response

        try:
            if is_admin and active_settings.admin_auth_enabled:
                if not _admin_credentials_valid(request, active_settings):
                    client_key = opaque_client_key(request.client.host if request.client else None)
                    if not await app.state.admin_auth_rate_limiter.allow(client_key):
                        return finalize(
                            PlainTextResponse("Too many authentication attempts.", status_code=429)
                        )
                    return finalize(
                        PlainTextResponse(
                            "Admin authentication required.",
                            status_code=401,
                            headers={
                                "WWW-Authenticate": 'Basic realm="Personal Intelligence Admin"'
                            },
                        )
                    )
                if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _same_admin_origin(
                    request, active_settings
                ):
                    return finalize(
                        PlainTextResponse("Invalid admin request origin.", status_code=403)
                    )
            if active_settings.force_https and request.url.path not in {"/health", "/ready"}:
                if not _request_is_https(request, active_settings):
                    origin = urlsplit(active_settings.admin_public_origin)
                    secure_url = urlunsplit(
                        (origin.scheme, origin.netloc, request.url.path, request.url.query, "")
                    )
                    return finalize(RedirectResponse(secure_url, status_code=307))
            return finalize(await call_next(request))
        finally:
            reset_request_id(request_context)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=active_settings.allowed_host_list)

    app.state.readiness_check = readiness_check
    app.state.engine = engine
    app.state.agent_api_settings = active_settings
    app.state.agent_api_rate_limiter = AgentApiRateLimiter(
        active_settings.agent_api_rate_limit_per_minute
    )
    app.state.agent_api_auth_rate_limiter = ProcessRateLimiter(
        active_settings.agent_api_auth_rate_limit_per_minute
    )
    app.state.admin_auth_rate_limiter = ProcessRateLimiter(
        active_settings.admin_auth_rate_limit_per_minute
    )

    async def metrics() -> dict[str, object]:
        if engine is None:
            return {"llm_calls": 0, "llm_cost_usd": 0, "recent_briefings": []}
        async with engine.connect() as connection:
            count, cost = (
                await connection.execute(
                    text("SELECT count(*), coalesce(sum(estimated_cost_usd),0) FROM llm_calls")
                )
            ).one()
            rows = (
                await connection.execute(
                    text("SELECT id, rendered FROM briefings ORDER BY created_at DESC LIMIT 10")
                )
            ).all()
        return {
            "llm_calls": count,
            "llm_cost_usd": float(cost),
            "recent_briefings": [dict(row._mapping) for row in rows],
        }

    app.state.metrics_provider = metrics
    app.state.sources_path = active_settings.admin_sources_path
    app.state.models_path = active_settings.admin_models_path
    app.state.interests_path = active_settings.admin_interests_path
    app.state.gmail_enabled = active_settings.gmail_enabled
    # The polling worker is a separate container, so dashboard status must not
    # depend on a webhook/poller object living in this process.
    app.state.telegram_enabled = active_settings.telegram_enabled
    app.state.telegram_mode = active_settings.telegram_mode
    app.state.openrouter_configured = bool(active_settings.openrouter_api_key_value)
    app.state.gmail_configured = bool(
        active_settings.gmail_enabled
        and active_settings.gmail_client_id.strip()
        and active_settings.gmail_client_secret_value
    )
    app.state.gmail_encryption_ready = False
    app.state.gmail_encryption_configuration_error = False
    if engine is not None:
        sessions = create_session_factory(engine)
        source_repository = SourceRepository(sessions)
        app.state.source_repository = source_repository
        app.state.onboarding_repository = OnboardingRepository(sessions)
        app.state.sessions = sessions

        async def write_agent_api_audit(endpoint: str, outcome: str, response_bytes: int) -> None:
            """Persist metadata only; no token, caller, question, source, or payload is stored."""
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "INSERT INTO agent_api_audit_log "
                        "(endpoint, outcome, response_bytes) "
                        "VALUES (:endpoint, :outcome, :response_bytes)"
                    ),
                    {
                        "endpoint": endpoint,
                        "outcome": outcome,
                        "response_bytes": response_bytes,
                    },
                )

        app.state.agent_api_audit_writer = write_agent_api_audit
        app.state.gmail_oauth = GmailOAuth(
            active_settings.gmail_client_id,
            active_settings.gmail_client_secret_value,
            active_settings.gmail_oauth_redirect_uri,
        )
        cipher: TokenCipher | None = None
        encryption_configuration_error = False
        if active_settings.app_encryption_key_value:
            try:
                cipher = TokenCipher(active_settings.app_encryption_key_value)
            except ValueError:
                encryption_configuration_error = True
        app.state.gmail_encryption_ready = cipher is not None
        app.state.gmail_encryption_configuration_error = encryption_configuration_error

        async def store_gmail_token(refresh_token: str) -> None:
            if cipher is None:
                raise ValueError("OAuth token storage is unavailable: configure APP_ENCRYPTION_KEY")
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "INSERT INTO gmail_accounts (id, encrypted_refresh_token, token_scheme) "
                        "VALUES (:id, :token, 'fernet-v1')"
                    ),
                    {"id": str(uuid.uuid4()), "token": cipher.protect(refresh_token)},
                )

        app.state.store_gmail_token = store_gmail_token
        (
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
        ) = database_persistence(sessions)
        (
            source_ready,
            source_succeeded,
            source_failed,
            source_validators,
            save_source_validators,
        ) = database_source_health(sessions)
        provider_coordinator = ProviderCallCoordinator()
        app.state.provider_coordinator = provider_coordinator
        notification_dispatchers = []
        if active_settings.ntfy_enabled:
            ntfy_notifier = NtfyNotifier(
                active_settings.ntfy_base_url,
                active_settings.ntfy_topic,
                active_settings.ntfy_token_value,
                active_settings.ntfy_request_timeout_seconds,
                active_settings.ntfy_max_retries,
            )
            notification_dispatchers.append(
                database_dispatcher(sessions, ntfy_notifier.send, channel="ntfy")
            )
        telegram_bot = None
        if active_settings.telegram_enabled:
            telegram_bot = TelegramBotClient(
                active_settings.telegram_bot_token_value,
                timeout_seconds=active_settings.telegram_request_timeout_seconds,
                retries=active_settings.telegram_max_retries,
            )

        async def queue_source_category_question(source_id: str) -> str:
            result = await send_source_category_question(
                sessions, active_settings, telegram_bot, source_id
            )
            return result.status

        async def source_category_question_delivered(source_id: str, chat_id: int) -> bool:
            return await source_category_question_was_delivered(sessions, source_id, chat_id)

        app.state.queue_source_category_question = queue_source_category_question
        app.state.run_source_category_question_worker = lambda stop_event: (
            run_source_category_question_worker(
                source_repository, sessions, active_settings, telegram_bot, stop_event
            )
        )
        app.state.notifications_enabled = bool(
            notification_dispatchers
            or (telegram_bot is not None and active_settings.telegram_notification_chat_id_list)
        )

        async def reembed_knowledge(limit: int = 50) -> int:
            """Explicit operator action; startup and scheduled jobs never call this routine."""
            model_settings = load_model_settings(active_settings.admin_models_path)
            embedding_config = model_settings.roles["embedding"]
            target_model = embedding_config.candidates[0]
            target_dimensions = embedding_config.dimensions

            async def fetch(limit_value: int) -> list[ReembeddingRecord]:
                async with sessions() as session:
                    rows = (
                        (
                            await session.execute(
                                text(
                                    "SELECT id, canonical_title, raw_content, embedding_model_id, "
                                    "embedding_dimensions FROM events WHERE embedding IS NULL "
                                    "OR embedding_model_id != :model OR (:dimensions IS NOT NULL "
                                    "AND embedding_dimensions != :dimensions) "
                                    "ORDER BY occurred_at DESC LIMIT :limit"
                                ),
                                {
                                    "model": target_model,
                                    "dimensions": target_dimensions,
                                    "limit": limit_value,
                                },
                            )
                        )
                        .mappings()
                        .all()
                    )
                return [
                    ReembeddingRecord(
                        str(row["id"]),
                        "\n".join(
                            value
                            for value in [
                                str(row["canonical_title"]),
                                str(row["raw_content"] or ""),
                            ]
                            if value
                        ),
                        str(row["embedding_model_id"]) if row["embedding_model_id"] else None,
                        int(row["embedding_dimensions"]) if row["embedding_dimensions"] else None,
                    )
                    for row in rows
                ]

            async def persist(values: list[tuple[str, object, int]]) -> None:
                async with sessions.begin() as session:
                    for event_id, result, index in values:
                        await session.execute(
                            text(
                                "UPDATE events SET embedding = CAST(:embedding AS vector), "
                                "embedding_model_id = :model, embedding_dimensions = :dimensions "
                                "WHERE id = :id"
                            ),
                            {
                                "id": event_id,
                                "embedding": "["
                                + ",".join(str(value) for value in result.vectors[index])
                                + "]",
                                "model": result.model_id,
                                "dimensions": result.dimensions,
                            },
                        )

            router = Router(
                OpenRouterClient(
                    active_settings.openrouter_api_key_value, model_settings.openrouter.base_url
                ),
                model_settings,
                InMemoryResultCache(),
                BudgetTracker(),
                SqlAlchemyLlmRepository(sessions),
                provider_coordinator=provider_coordinator,
            )
            return await ReembeddingService(fetch, persist, router.embed).run(limit=limit)

        app.state.reembed_knowledge_callback = reembed_knowledge
        gmail_client = GmailApiClient(
            active_settings.gmail_client_id,
            active_settings.gmail_client_secret_value,
            initial_lookback_hours=active_settings.gmail_initial_lookback_hours,
            initial_max_messages=active_settings.gmail_initial_max_messages,
            timeout_seconds=active_settings.gmail_request_timeout_seconds,
            max_retries=active_settings.gmail_max_retries,
        )

        async def gmail_accounts() -> list[GmailAccountRecord]:
            if not active_settings.gmail_enabled or cipher is None:
                return []
            async with sessions() as session:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, encrypted_refresh_token, history_id FROM gmail_accounts "
                            "WHERE token_scheme = 'fernet-v1'"
                        )
                    )
                ).mappings()
                return [
                    GmailAccountRecord(
                        account_id=str(row["id"]),
                        encrypted_refresh_token=str(row["encrypted_refresh_token"]),
                        history_id=str(row["history_id"]) if row["history_id"] else None,
                    )
                    for row in rows
                ]

        async def known_gmail_message(source_item_id: str) -> bool:
            async with sessions() as session:
                return bool(
                    await session.scalar(
                        text(
                            "SELECT 1 FROM email_classifications "
                            "WHERE source_item_id = :source_item_id"
                        ),
                        {"source_item_id": source_item_id},
                    )
                )

        async def persist_gmail_classification(source_item_id: str, classification: object) -> None:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "INSERT INTO email_classifications "
                        "(source_item_id, classification, action_summary, deadline, "
                        "application_company) "
                        "VALUES (:source_item_id, :classification, :action_summary, :deadline, "
                        ":application_company) ON CONFLICT (source_item_id) DO NOTHING"
                    ),
                    {
                        "source_item_id": source_item_id,
                        "classification": classification.classification,
                        "action_summary": classification.action_summary,
                        "deadline": classification.deadline,
                        "application_company": classification.application_company,
                    },
                )
                if classification.classification in {
                    "action_required",
                    "application_update",
                    "recruiter",
                    "security",
                    "transactional",
                }:
                    await session.execute(
                        text(
                            "INSERT INTO briefing_outbox "
                            "(event_id, title, source_urls_json, importance, interest, "
                            "global_importance, actionable, video, source_type) "
                            "VALUES (:event_id, :title, '[]', :importance, 0, 0, true, false, "
                            "'gmail') ON CONFLICT (event_id) DO NOTHING"
                        ),
                        {
                            "event_id": source_item_id,
                            "title": classification.action_summary or "Gmail action item",
                            "importance": (
                                8
                                if classification.classification in {"security", "action_required"}
                                else 6
                            ),
                        },
                    )

        async def update_gmail_checkpoint(
            account_id: str, history_id: str | None, synced_at: datetime
        ) -> None:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "UPDATE gmail_accounts SET history_id = :history_id, "
                        "last_sync_at = :last_sync_at WHERE id = :id"
                    ),
                    {"id": account_id, "history_id": history_id, "last_sync_at": synced_at},
                )

        async def fetch_gmail_account(account: GmailAccountRecord, refresh_token: str) -> object:
            return await gmail_client.sync(refresh_token, account.history_id)

        def create_gmail_job() -> GmailRuntimeJob:
            return GmailRuntimeJob(
                gmail_accounts,
                cipher.reveal if cipher else _missing_gmail_cipher,
                fetch_gmail_account,
                known_gmail_message,
                persist_gmail_classification,
                update_gmail_checkpoint,
            )

        async def latest_briefing_id() -> str | None:
            async with sessions() as session:
                value = await session.scalar(
                    text("SELECT id FROM briefings ORDER BY created_at DESC LIMIT 1")
                )
            return str(value) if value is not None else None

        async def telegram_calibration_candidates(briefing_id: str) -> list[dict[str, str]]:
            async with sessions() as session:
                days = await session.scalar(
                    text("SELECT telegram_calibration_days FROM control_center_settings WHERE id")
                )
                if int(days or 0) >= 14:
                    return []
                rows = (
                    await session.execute(
                        text(
                            "SELECT bi.event_id, bi.section, "
                            "coalesce(m.entities_json, '[]') AS entities_json, "
                            "coalesce(m.topics_json, '[]') AS topics_json, "
                            "ARRAY(SELECT es.canonical_url FROM event_sources es "
                            "WHERE es.event_id = bi.event_id AND es.canonical_url IS NOT NULL "
                            "ORDER BY es.canonical_url LIMIT 5) AS source_urls "
                            "FROM briefing_items bi "
                            "LEFT JOIN event_search_metadata m ON m.event_id = bi.event_id "
                            "WHERE bi.briefing_id = :briefing_id ORDER BY bi.section, bi.event_id"
                        ),
                        {"briefing_id": briefing_id},
                    )
                ).mappings().all()
            return select_telegram_calibration_candidates(rows)

        async def record_telegram_calibration_day(local_day: date) -> None:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "UPDATE control_center_settings SET "
                        "telegram_calibration_days = least(14, telegram_calibration_days + 1), "
                        "telegram_calibration_last_day = :local_day "
                        "WHERE id AND telegram_calibration_days < 14 "
                        "AND (telegram_calibration_last_day IS NULL "
                        "OR telegram_calibration_last_day <> :local_day)"
                    ),
                    {"local_day": local_day},
                )

        async def deliver_run_notifications(
            result: dict[str, object],
            gmail_items: list[BriefingItem],
            briefing_id: str | None = None,
            delivery_target_at: datetime | None = None,
        ) -> list[str]:
            """Deliver post-persistence notifications without changing a completed run result."""
            dispatchers = list(notification_dispatchers)
            local_now = datetime.now(UTC).astimezone(ZoneInfo(active_settings.app_timezone))
            local_day = (
                delivery_target_at.astimezone(ZoneInfo(active_settings.app_timezone)).date()
                if delivery_target_at is not None
                else local_now.date()
            )
            delivery_note = None
            if delivery_target_at is not None:
                delivered_at = await wait_until(
                    delivery_target_at,
                    now=lambda: datetime.now(UTC),
                )
                if briefing_id:
                    delivery_note = _delivery_delay_note(delivery_target_at, delivered_at)
            if telegram_bot is not None:
                for chat_id in active_settings.telegram_notification_chat_id_list:
                    async def send_telegram_notification(
                        notification: Notification,
                        *,
                        destination: int = chat_id,
                        current_briefing_id: str | None = briefing_id,
                    ) -> None:
                        assert telegram_bot is not None
                        if notification.kind == NotificationKind.BRIEFING_READY:
                            handler = getattr(app.state, "telegram_command_handler", None)
                            if handler is None or current_briefing_id is None:
                                raise RuntimeError("telegram_briefing_handler_unavailable")
                            await handler.send_briefing(
                                destination,
                                await agent_briefing_detail(current_briefing_id),
                                await telegram_calibration_candidates(current_briefing_id),
                                delivery_note=delivery_note,
                            )
                            try:
                                await record_telegram_calibration_day(local_day)
                            except Exception:
                                logger.warning(
                                    "telegram_calibration_progress_unavailable",
                                    extra={"diagnostic_category": "telegram_calibration_state"},
                                )
                            return
                        await telegram_bot.send_notification(destination, notification)

                    channel = telegram_delivery_channel(chat_id)
                    dispatchers.append(
                        database_dispatcher(
                            sessions, send_telegram_notification, channel=channel
                        )
                    )
            if not dispatchers:
                return ["disabled"]
            admin_link = (
                f"{active_settings.admin_public_origin}/admin"
                if active_settings.admin_public_origin
                else None
            )
            notifications: list[Notification] = []
            if briefing_id:
                notifications.append(
                    Notification(
                        idempotency_key=notification_key(
                            NotificationKind.BRIEFING_READY, briefing_id
                        ),
                        kind=NotificationKind.BRIEFING_READY,
                        title="Günlük özet hazır",
                        body="Yeni özet güvenli yönetim panelinde hazır.",
                        link=admin_link,
                    )
                )
            for item in gmail_items:
                notifications.append(
                    Notification(
                        idempotency_key=notification_key(
                            NotificationKind.ACTIONABLE_MAIL, item.event_id
                        ),
                        kind=NotificationKind.ACTIONABLE_MAIL,
                        title="Eylem gerektiren e-posta",
                        body="Yeni bir eylem gerektiren e-posta tespit edildi.",
                        link=admin_link,
                    )
                )
            if result.get("status") in {"failed", "completed_with_errors"}:
                failure_summary = format_failure_summary(result)
                notifications.append(
                    Notification(
                        idempotency_key=notification_key(
                            NotificationKind.OPERATIONAL_FAILURE, local_day
                        ),
                        kind=NotificationKind.OPERATIONAL_FAILURE,
                        title="İşlem uyarısı",
                        body=(
                            "Günlük işlem güvenli hata durumu ile tamamlandı. "
                            f"{failure_summary}. Ayrıntılar yönetim panelinde."
                            if failure_summary
                            else "Günlük işlem güvenli hata durumu ile tamamlandı. "
                            "Hata türü sayımı yok. Ayrıntılar yönetim panelinde."
                        ),
                        link=admin_link,
                    )
                )
            results = await deliver_ordered(dispatchers, notifications)
            return [delivery.status for delivery in results] or ["no_notification"]

        async def run_rss_now(
            delivery_target_at: datetime | None = None,
            *,
            deliver_notifications: bool = True,
        ) -> dict[str, object]:
            """Build a briefing from persisted Gmail items, YouTube, and RSS."""
            previous_briefing_id = await latest_briefing_id()
            model_settings = load_model_settings(active_settings.admin_models_path)
            router = Router(
                OpenRouterClient(
                    active_settings.openrouter_api_key_value, model_settings.openrouter.base_url
                ),
                model_settings,
                InMemoryResultCache(),
                BudgetTracker(),
                SqlAlchemyLlmRepository(sessions),
                provider_coordinator=provider_coordinator,
            )
            catalog = await source_repository.load_catalog()
            job = RssRuntimeJob(
                catalog,
                ExtractionFlow(router),
                persist_event,
                persist_briefing,
                known_item,
                collector=RssCollector(
                    HttpFeedFetcher(
                        allow_private_hosts=active_settings.allow_private_source_urls,
                        allow_insecure_http=active_settings.allow_insecure_source_urls,
                    ),
                    max_items=active_settings.rss_max_items_per_feed,
                ),
                post_llm_failure=mark_post_llm_failure,
                is_post_llm_failed=is_post_llm_failed,
                refresh_blocked_item=refresh_blocked_item,
                has_pending_briefing=has_pending_briefing,
                correlate_event=correlate_event,
                article_fetcher=ArticleFetcher(
                    active_settings.article_request_timeout_seconds,
                    active_settings.article_max_response_bytes,
                    active_settings.article_max_retries,
                    active_settings.allow_private_source_urls,
                    active_settings.allow_insecure_source_urls,
                ),
                source_ready=source_ready,
                source_succeeded=source_succeeded,
                source_failed=source_failed,
                source_validators=source_validators,
                save_source_validators=save_source_validators,
                max_concurrent_fetches=active_settings.rss_max_concurrent_fetches,
                source_repository=source_repository,
            )
            # Gmail has its own configured poll interval; briefing runs only consume its outbox.
            gmail_run = GmailRun()
            youtube_call_start = len(router.calls)
            youtube_run = await YouTubeRuntimeJob(
                catalog,
                ExtractionFlow(router),
                persist_event,
                known_item,
                mark_post_llm_failure,
                is_post_llm_failed,
                refresh_blocked_item,
                discovery=YouTubeDiscovery(
                    HttpFeedFetcher(
                        allow_private_hosts=active_settings.allow_private_source_urls,
                        allow_insecure_http=active_settings.allow_insecure_source_urls,
                    )
                ),
                source_repository=source_repository,
            ).run()
            youtube_llm = usage_breakdown(router.calls[youtube_call_start:])
            rss_call_start = len(router.calls)
            result = await job.run([*gmail_run.action_items, *youtube_run.briefing_items])
            rss_usages = router.calls[rss_call_start:]
            briefing_editor_llm = usage_breakdown(
                [usage for usage in rss_usages if usage.role == "editor"]
            )
            rss_llm = usage_breakdown(
                [usage for usage in rss_usages if usage.role != "editor"]
            )
            gmail_counts = gmail_run.response(active_settings.gmail_enabled)["gmail"]
            gmail_llm = usage_breakdown([])
            rss_counts = result["counts"]
            rss_counts["llm_calls"] = rss_llm["provider_calls"]
            rss_counts["llm_cache_hits"] = rss_llm["cache_hits"]
            rss_counts["llm_breakdown"] = rss_llm
            youtube_counts = youtube_run.response()
            youtube_counts["llm_calls"] = youtube_llm["provider_calls"]
            youtube_counts["llm_cache_hits"] = youtube_llm["cache_hits"]
            youtube_counts["llm_breakdown"] = youtube_llm
            gmail_counts["llm_breakdown"] = gmail_llm
            rss_counts["gmail"] = gmail_counts
            rss_counts["youtube"] = youtube_counts
            rss_counts["rss"] = {
                "provider_calls": rss_llm["provider_calls"],
                "cache_hits": rss_llm["cache_hits"],
                "by_role": rss_llm["by_role"],
            }
            rss_counts["llm_breakdown_by_flow"] = {
                "rss": rss_llm,
                "gmail": gmail_llm,
                "youtube": youtube_llm,
                "briefing_editor": briefing_editor_llm,
            }
            rss_counts["llm_calls"] = sum(
                int(flow["provider_calls"]) for flow in rss_counts["llm_breakdown_by_flow"].values()
            )
            rss_counts["llm_cache_hits"] = sum(
                int(flow["cache_hits"]) for flow in rss_counts["llm_breakdown_by_flow"].values()
            )
            if (
                result.get("status") == "completed"
                and (
                    gmail_run.failed
                    or youtube_counts.get("status") in {"failed", "completed_with_errors"}
                )
            ):
                result["status"] = "completed_with_errors"
            if gmail_run.failed:
                result["message"] += f" Gmail sync had {gmail_run.failed} safe failure(s)."
            if youtube_run.failed:
                result["message"] += f" YouTube sync had {youtube_run.failed} safe failure(s)."
            created_briefing_id = await latest_briefing_id()
            if created_briefing_id == previous_briefing_id:
                created_briefing_id = None
            result["briefing_id"] = created_briefing_id
            if deliver_notifications:
                result["notifications"] = await deliver_run_notifications(
                    result, gmail_run.action_items, created_briefing_id, delivery_target_at
                )
            else:
                result["notifications"] = []
            return result

        run_coordinator = RuntimeRunCoordinator()

        async def run_manual_now() -> dict[str, object]:
            return await run_coordinator.run("manual", run_rss_now)

        async def run_scheduled_now(delivery_target_at: datetime) -> dict[str, object]:
            return await run_coordinator.run(
                "scheduled", lambda: run_rss_now(delivery_target_at)
            )

        app.state.run_coordinator = run_coordinator
        app.state.run_callback = run_manual_now

        async def run_gmail_poll() -> None:
            async def poll() -> dict[str, object]:
                result = await create_gmail_job().run()
                return result.response(active_settings.gmail_enabled)

            await run_coordinator.run("gmail", poll)

        app.state.run_gmail_poll_callback = run_gmail_poll

        async def ask_knowledge(filters: SearchFilters) -> dict[str, object]:
            """Search compact persisted memory and optionally synthesize only its top candidates."""
            service = KnowledgeSearchService(
                lambda requested: fetch_sql_candidates(engine, requested)
            )
            model_settings = load_model_settings(active_settings.admin_models_path)
            router: Router | None = None
            if active_settings.openrouter_api_key_value and "reasoner" in model_settings.roles:
                router = Router(
                    OpenRouterClient(
                        active_settings.openrouter_api_key_value,
                        model_settings.openrouter.base_url,
                    ),
                    model_settings,
                    InMemoryResultCache(),
                    BudgetTracker(),
                    SqlAlchemyLlmRepository(sessions),
                    provider_coordinator=provider_coordinator,
                )
            return (await answer_question(filters, service, router)).model_dump(mode="json")

        app.state.ask_callback = ask_knowledge

        async def search_knowledge(filters: SearchFilters) -> dict[str, object]:
            """Return the existing deterministic bounded retrieval without a reasoner call."""
            service = KnowledgeSearchService(
                lambda requested: fetch_sql_candidates(engine, requested)
            )
            events, emails = await service.search(filters)
            if not events and not emails:
                return SearchResponse(
                    status="insufficient_sources",
                    answer_tr="Yeterli kaynak bulunamadı.",
                    llm={"provider_calls": 0, "cache_hits": 0, "by_role": {}},
                ).model_dump(mode="json")
            return SearchResponse(
                status="ok",
                answer_tr="Kaynaklar aşağıda listelenmiştir.",
                events=events,
                emails=emails,
                llm={"provider_calls": 0, "cache_hits": 0, "by_role": {}},
            ).model_dump(mode="json")

        app.state.search_callback = search_knowledge

        async def search_event_detail(event_id: str):
            """Read one persisted search result without invoking a provider."""
            return await fetch_sql_event(engine, event_id)

        app.state.search_event_detail_callback = search_event_detail

        async def agent_briefing_items(
            briefing_id: str, rendered: str
        ) -> list[AgentBriefingItem]:
            """Select only safe persisted briefing/event/action fields for Agent API reads."""
            async with sessions() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT bi.event_id, bi.section, bc.title AS briefing_title, "
                                "bc.summary_tr, "
                                "bc.what_changed_tr, bc.why_important_tr, e.canonical_title, "
                                "e.occurred_at, ec.classification, ec.action_summary, ec.deadline, "
                                "ec.application_company, ec.created_at AS email_recorded_at, "
                                "ARRAY(SELECT c.statement FROM claims c "
                                "WHERE c.event_id = bi.event_id "
                                "ORDER BY c.id LIMIT 5) AS facts, "
                                "ARRAY(SELECT i.inference_text FROM inferences i "
                                "WHERE i.event_id = bi.event_id "
                                "ORDER BY i.id LIMIT 3) AS inferences, "
                                "ARRAY(SELECT es.canonical_url FROM event_sources es "
                                "WHERE es.event_id = bi.event_id "
                                "AND es.canonical_url IS NOT NULL "
                                "ORDER BY es.canonical_url LIMIT 3) AS source_links "
                                "FROM briefing_items bi "
                                "LEFT JOIN briefing_item_content bc "
                                "ON bc.briefing_id = bi.briefing_id "
                                "AND bc.event_id = bi.event_id "
                                "LEFT JOIN events e ON e.id = bi.event_id "
                                "LEFT JOIN email_classifications ec "
                                "ON ec.source_item_id = bi.event_id "
                                "WHERE bi.briefing_id = :briefing_id "
                                "ORDER BY bi.section, e.occurred_at DESC NULLS LAST, bi.event_id"
                            ),
                            {"briefing_id": briefing_id},
                        )
                    )
                    .mappings()
                    .all()
                )
            if not rows:
                legacy_items = [
                    AgentBriefingItem(
                        section=item.section,
                        event_id=item.event_id,
                        title=item.title[:320],
                        summary=compact_sentences(item.summary, max_chars=600),
                        source_links=safe_links(item.source_links),
                        original_text=True,
                    )
                    for items in legacy_sections(rendered).values()
                    for item in items
                ]
                return order_briefing_items(
                    legacy_items,
                    section=lambda item: item.section,
                    published_at=lambda item: item.published_at,
                    event_id=lambda item: str(item.event_id or ""),
                )
            result: list[AgentBriefingItem] = []
            for row in rows:
                facts = [str(value)[:400] for value in (row["facts"] or []) if value][:5]
                action_summary = (
                    str(row["action_summary"])[:400] if row["action_summary"] is not None else None
                )
                title = (
                    row["briefing_title"]
                    or row["canonical_title"]
                    or action_summary
                    or "Kaydedilmiş briefing öğesi"
                )
                summary = row["summary_tr"] or action_summary or " ".join(facts) or title
                email_action = None
                if row["classification"] is not None:
                    email_action = AgentEmailAction(
                        classification=str(row["classification"])[:64],
                        action_summary=action_summary,
                        deadline=row["deadline"],
                        application_company=(
                            str(row["application_company"])[:160]
                            if row["application_company"] is not None
                            else None
                        ),
                        recorded_at=row["email_recorded_at"],
                    )
                result.append(
                    AgentBriefingItem(
                        section=str(row["section"])[:128],
                        event_id=str(row["event_id"])[:36],
                        title=str(title)[:320],
                        summary=compact_sentences(str(summary), max_chars=600),
                        what_changed=(
                            compact_sentences(str(row["what_changed_tr"]), limit=1, max_chars=400)
                            if row["what_changed_tr"] is not None
                            else None
                        ),
                        why_important=(
                            compact_sentences(str(row["why_important_tr"]), limit=1, max_chars=400)
                            if row["why_important_tr"] is not None
                            else None
                        ),
                        published_at=row["occurred_at"],
                        source_links=safe_links(row["source_links"] or []),
                        verified_facts=facts,
                        stored_inferences=[
                            str(value)[:400] for value in (row["inferences"] or []) if value
                        ][:3],
                        email_action=email_action,
                        original_text=row["summary_tr"] is None,
                    )
                )
            return order_briefing_items(
                result,
                section=lambda item: item.section,
                published_at=lambda item: item.published_at,
                event_id=lambda item: str(item.event_id or ""),
            )

        async def agent_briefing_detail(briefing_id: str) -> dict[str, object]:
            async with sessions() as session:
                row = (
                    (
                        await session.execute(
                            text(
                                "SELECT id, created_at, rendered FROM briefings "
                                "WHERE id = :briefing_id"
                            ),
                            {"briefing_id": briefing_id},
                        )
                    )
                    .mappings()
                    .first()
                )
            if row is None:
                raise LookupError("briefing not found")
            detail = AgentBriefingDetail(
                id=str(row["id"]),
                created_at=row["created_at"],
                items=await agent_briefing_items(str(row["id"]), str(row["rendered"])),
            )
            return detail.model_dump(mode="json")

        async def agent_latest_briefing() -> dict[str, object]:
            async with sessions() as session:
                row = (
                    (
                        await session.execute(
                            text("SELECT id FROM briefings ORDER BY created_at DESC LIMIT 1")
                        )
                    )
                    .mappings()
                    .first()
                )
            if row is None:
                raise LookupError("no briefing")
            return await agent_briefing_detail(str(row["id"]))

        async def agent_list_briefings(limit: int, before: datetime | None) -> dict[str, object]:
            clause = ""
            parameters: dict[str, object] = {"query_limit": limit + 1}
            if before is not None:
                clause = "WHERE b.created_at < :before"
                parameters["before"] = before
            async with sessions() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT b.id, b.created_at, count(bi.event_id) AS item_count "
                                "FROM briefings b LEFT JOIN briefing_items bi "
                                "ON bi.briefing_id = b.id "
                                f"{clause} GROUP BY b.id, b.created_at "
                                "ORDER BY b.created_at DESC LIMIT :query_limit"
                            ),
                            parameters,
                        )
                    )
                    .mappings()
                    .all()
                )
            has_more = len(rows) > limit
            page_rows = rows[:limit]
            page = AgentBriefingPage(
                items=[
                    AgentBriefingSummary(
                        id=str(row["id"]),
                        created_at=row["created_at"],
                        item_count=int(row["item_count"]),
                    )
                    for row in page_rows
                ],
                next_before=page_rows[-1]["created_at"] if has_more and page_rows else None,
            )
            return page.model_dump(mode="json")

        app.state.agent_api_latest_briefing = agent_latest_briefing
        app.state.agent_api_briefing_detail = agent_briefing_detail
        app.state.agent_api_list_briefings = agent_list_briefings

        async def telegram_status() -> dict[str, object]:
            ready = await readiness_check()
            last_run = str(getattr(app.state, "last_run", "idle"))[:64]
            scheduler = getattr(app.state, "scheduler", None)
            scheduler_state = scheduler.state if scheduler else None
            try:
                sources = await source_repository.list()
            except Exception:
                sources = []
            active_sources = sum(bool(source["enabled"]) for source in sources)
            async with sessions() as session:
                last_briefing = await session.scalar(
                    text("SELECT created_at FROM briefings ORDER BY created_at DESC LIMIT 1")
                )
                last_schedule = (
                    (
                        await session.execute(
                            text(
                                "SELECT completed_at, status FROM scheduled_runs "
                                "WHERE completed_at IS NOT NULL "
                                "ORDER BY run_date DESC LIMIT 1"
                            )
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            scheduled_at = "henüz yok"
            if last_schedule is not None:
                scheduled_at = f"{last_schedule['completed_at']} ({last_schedule['status']})"
            current_schedule_error = getattr(scheduler_state, "last_error", None)
            warning = current_schedule_error or (
                "son_zamanlanmış_çalışma_başarısız"
                if last_schedule is not None and last_schedule["status"] == "failed"
                else None
            )
            warning_line = f"\nUyarı: {warning}" if warning else ""
            return {
                "text": (
                    f"Sistem: {'hazır' if ready else 'geçici olarak hazır değil'}\n"
                    f"Son işlem: {last_run}\n"
                    f"Son zamanlanmış çalışma: {scheduled_at}\n"
                    f"Son özet: {last_briefing or 'henüz yok'}\n"
                    f"Aktif kaynak: {active_sources}/{len(sources)}{warning_line}"
                )
            }

        async def telegram_history(limit: int) -> list[dict[str, object]]:
            page = await agent_list_briefings(limit, None)
            rows = page.get("items")
            return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

        async def telegram_sources() -> str:
            rows = await source_repository.list()
            if not rows:
                return "Henüz takip edilen kaynak yok."
            lines = ["Takip edilen kaynaklar"]
            for row in rows[:30]:
                state = "aktif" if row["enabled"] else "pasif"
                lines.append(f"- {row['id']} · {row['kind']} · {row['name']} ({state})")
            return "\n".join(lines)

        async def telegram_add_source(
            kind: str, endpoint: str, name: str, _chat_id: int
        ) -> str:
            try:
                source = await source_repository.create(
                    ManagedSourceCreate(kind=kind, endpoint=endpoint, name=name, enabled=False)
                )
            except Exception:
                return "Kaynak yönetimi şu anda kullanılamıyor."
            if source.get("category") is None:
                try:
                    await queue_source_category_question(str(source["id"]))
                except Exception:
                    logger.warning(
                        "telegram_source_category_question_failed",
                        extra={"diagnostic_category": "category_question_queue_unavailable"},
                    )
            return f"{source['name']} eklendi ve pasif bırakıldı. Kimlik: {source['id']}"

        async def telegram_disable_source(source_id: str) -> str:
            try:
                row = await source_repository.get(source_id)
                if row is None or not await source_repository.set_enabled(source_id, False):
                    return "Kaynak bulunamadı."
            except Exception:
                return "Kaynak yönetimi şu anda kullanılamıyor."
            return (
                f"{row['name']} devre dışı bırakıldı. "
                "İsterseniz daha sonra tekrar ekleyebilirsiniz."
            )

        def _telegram_subject(value: str) -> str | None:
            subject = " ".join(value.split())
            if not subject or len(subject) > 128 or any(ord(char) < 32 for char in subject):
                return None
            return subject

        async def telegram_interests() -> str:
            async with sessions() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT subject, base, explicit, adaptive FROM interest_profile "
                                "WHERE base <> 0 OR explicit <> 0 OR adaptive <> 0 "
                                "ORDER BY (base + explicit + adaptive) DESC, subject LIMIT 20"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
            if not rows:
                return "Henüz kaydedilmiş ilgi alanı yok. /ilgi_ekle <konu> ile ekleyin."
            return "\n".join(
                ["İlgi alanları"]
                + [f"- {row['subject']}" for row in rows]
            )

        async def telegram_set_interest(value: str, enabled: bool) -> str:
            subject = _telegram_subject(value)
            if subject is None:
                return "İlgi alanı 1–128 görünür karakter olmalı."
            async with sessions.begin() as session:
                if enabled:
                    await session.execute(
                        text(
                            "INSERT INTO interest_profile (subject, base, explicit, adaptive) "
                            "VALUES (:subject, 0, 1, 0) ON CONFLICT (subject) DO UPDATE "
                            "SET explicit = greatest(1, interest_profile.explicit)"
                        ),
                        {"subject": subject},
                    )
                    await session.execute(
                        text(
                            "INSERT INTO feedback_events (subject, action, occurred_at) "
                            "VALUES (:subject, 'explicit_more', now())"
                        ),
                        {"subject": subject},
                    )
                else:
                    await session.execute(
                        text("UPDATE interest_profile SET explicit = 0 WHERE subject = :subject"),
                        {"subject": subject},
                    )
            return (
                f"{subject} ilgi alanlarına eklendi."
                if enabled
                else f"{subject} için açık tercih kaldırıldı."
            )

        if telegram_bot is not None:
            async def telegram_daily() -> tuple[str, dict[str, object] | None]:
                result = await run_coordinator.run(
                    "telegram_daily",
                    lambda: run_rss_now(deliver_notifications=False),
                )
                if result.get("skip_reason") == "another_run_active":
                    return "busy", None
                briefing_id = result.get("briefing_id")
                if not isinstance(briefing_id, str) or not briefing_id:
                    return "unavailable", None
                try:
                    return "ok", await agent_briefing_detail(briefing_id)
                except LookupError:
                    return "unavailable", None

            async def telegram_gmail_interval(interval: int | None) -> str:
                repository = app.state.onboarding_repository
                scheduler = app.state.gmail_polling_scheduler
                if interval is None:
                    preference = await repository.gmail_polling_preference()
                    if not active_settings.gmail_enabled:
                        return (
                            "Gmail eşitlemesi kapalı. Kayıtlı aralık: "
                            f"{preference.interval_minutes} dakika."
                        )
                    return (
                        f"Gmail, {preference.interval_minutes} dakikada bir kontrol ediliyor. "
                        "Anlık bildirim gönderilmez."
                    )
                preference = GmailPollingPreference(interval_minutes=interval)
                await repository.save_gmail_polling_preference(preference)
                await scheduler.configure(preference.interval_minutes)
                return (
                    f"Gmail kontrol aralığı {preference.interval_minutes} dakika "
                    "olarak kaydedildi. "
                    "Yeni aralık sonraki kontrolden itibaren uygulanır; anlık eşitleme yapılmaz."
                )

            app.state.telegram_command_handler = TelegramWebhookHandler(
                active_settings,
                sessions,
                telegram_bot,
                latest_briefing=agent_latest_briefing,
                search=search_knowledge,
                ask=ask_knowledge,
                status=telegram_status,
                history=telegram_history,
                sources=telegram_sources,
                add_source=telegram_add_source,
                disable_source=telegram_disable_source,
                interests=telegram_interests,
                set_interest=telegram_set_interest,
                source_repository=source_repository,
                queue_source_category_question=queue_source_category_question,
                source_category_question_delivered=source_category_question_delivered,
                daily=telegram_daily,
                gmail_interval=telegram_gmail_interval,
            )
            if active_settings.telegram_mode == "webhook":
                app.state.telegram_webhook_handler = app.state.telegram_command_handler

        async def retry_blocked_youtube(content_hash: str) -> dict[str, object]:
            """Run exactly one explicitly claimed retry; scheduler/manual runs remain blocked."""
            record = await claim_blocked_item(content_hash, "youtube")
            if record is None:
                return {"status": "retry_not_available"}
            source_name = record.get("source_name")
            video_url = record.get("canonical_url")
            catalog = await source_repository.load_catalog()
            source = next(
                (entry for entry in catalog.youtube if entry.name == source_name and entry.enabled),
                None,
            )
            now = datetime.now(UTC)
            if source and source_name and video_url:
                item = SourceItem(
                    source_name=source.name,
                    source_kind=SourceKind.YOUTUBE,
                    stream=source.stream,
                    canonical_url=str(video_url),
                    title=str(record.get("title") or "Blocked YouTube video"),
                    source_published_at=record.get("published_at"),
                    discovered_at=now,
                    fetched_at=now,
                    timestamp_confidence=(
                        TimestampConfidence.SOURCE
                        if record.get("published_at")
                        else TimestampConfidence.DISCOVERED_FALLBACK
                    ),
                    source_freshness_hours=source.freshness_hours,
                    content_hash=content_hash,
                )
            else:
                found = await _find_blocked_youtube_item(
                    catalog,
                    content_hash,
                    now,
                    allow_private_hosts=active_settings.allow_private_source_urls,
                    allow_insecure_http=active_settings.allow_insecure_source_urls,
                )
                if found is None:
                    await _reblock_retry(sessions, content_hash, "retry_source_unavailable")
                    return {"status": "retry_source_unavailable"}
                source, item = found
                await refresh_blocked_item(item, source.language)
            model_settings = load_model_settings(active_settings.admin_models_path)
            llm_router = Router(
                OpenRouterClient(
                    active_settings.openrouter_api_key_value, model_settings.openrouter.base_url
                ),
                model_settings,
                InMemoryResultCache(),
                BudgetTracker(),
                SqlAlchemyLlmRepository(sessions),
                provider_coordinator=provider_coordinator,
            )
            run = await YouTubeRuntimeJob(
                catalog,
                ExtractionFlow(llm_router),
                persist_event,
                known_item,
                mark_post_llm_failure,
                is_post_llm_failed,
                refresh_blocked_item,
            ).run((source, item))
            retry_llm = usage_breakdown(llm_router.calls)
            retry_counts = run.response()
            retry_counts["llm_calls"] = retry_llm["provider_calls"]
            retry_counts["llm_cache_hits"] = retry_llm["cache_hits"]
            retry_counts["llm_breakdown"] = retry_llm
            if run.processed != 1 or not run.briefing_items:
                if not run.event_persistence_errors and not run.extractor_errors:
                    await _reblock_retry(sessions, content_hash, _retry_failure_category(run))
                return {"status": "retry_failed", "youtube": retry_counts}
            try:
                await persist_briefing(run.briefing_items)
            except Exception:
                await _reblock_retry(sessions, content_hash, "briefing_persistence_error")
                return {"status": "retry_failed", "youtube": retry_counts}
            await resolve_blocked_item(content_hash)
            return {"status": "retry_completed", "youtube": retry_counts}

        app.state.retry_blocked_youtube_callback = retry_blocked_youtube

        async def retry_blocked_rss(content_hash: str) -> dict[str, object]:
            """Retry one RSS post-LLM block using durable cache before any new provider work."""
            record = await claim_blocked_item(content_hash, "rss")
            if record is None:
                return {"status": "retry_not_available"}
            catalog = await source_repository.load_catalog()
            source_name = record.get("source_name")
            source = next(
                (entry for entry in catalog.rss if entry.name == source_name and entry.enabled),
                None,
            )
            if source is None:
                await _reblock_retry(sessions, content_hash, "retry_source_unavailable")
                return {"status": "retry_source_unavailable"}
            now = datetime.now(UTC)
            item = SourceItem(
                source_name=source.name,
                source_kind=SourceKind.RSS,
                stream=source.stream,
                canonical_url=(
                    str(record["canonical_url"]) if record.get("canonical_url") else None
                ),
                title=str(record.get("title") or "Blocked RSS item"),
                source_published_at=record.get("published_at"),
                discovered_at=now,
                fetched_at=now,
                timestamp_confidence=(
                    TimestampConfidence.SOURCE
                    if record.get("published_at")
                    else TimestampConfidence.DISCOVERED_FALLBACK
                ),
                source_freshness_hours=source.freshness_hours,
                content_hash=content_hash,
            )
            model_settings = load_model_settings(active_settings.admin_models_path)
            retry_router = Router(
                OpenRouterClient(
                    active_settings.openrouter_api_key_value, model_settings.openrouter.base_url
                ),
                model_settings,
                InMemoryResultCache(),
                BudgetTracker(),
                SqlAlchemyLlmRepository(sessions),
                provider_coordinator=provider_coordinator,
            )
            result = await RssRuntimeJob(
                SourceCatalog(),
                ExtractionFlow(retry_router),
                persist_event,
                persist_briefing,
                known_item,
                post_llm_failure=mark_post_llm_failure,
                is_post_llm_failed=is_post_llm_failed,
                refresh_blocked_item=refresh_blocked_item,
                has_pending_briefing=has_pending_briefing,
                correlate_event=correlate_event,
                article_fetcher=ArticleFetcher(
                    active_settings.article_request_timeout_seconds,
                    active_settings.article_max_response_bytes,
                    active_settings.article_max_retries,
                    active_settings.allow_private_source_urls,
                    active_settings.allow_insecure_source_urls,
                ),
            ).run(retry_item=item)
            counts = result["counts"]
            retry_llm = usage_breakdown(retry_router.calls)
            counts["llm_calls"] = retry_llm["provider_calls"]
            counts["llm_cache_hits"] = retry_llm["cache_hits"]
            counts["llm_breakdown"] = retry_llm
            if counts["processed"] != 1:
                if (
                    not counts["failure_categories"]["extractor_error"]
                    and not counts["failure_categories"]["event_persistence_error"]
                ):
                    await _reblock_retry(sessions, content_hash, "retry_failed")
                return {"status": "retry_failed", "rss": result}
            await resolve_blocked_item(content_hash)
            return {"status": "retry_completed", "rss": result}

        app.state.retry_blocked_rss_callback = retry_blocked_rss

        async def claim_scheduled_slot(delivery_at: datetime) -> bool:
            run_date = delivery_at.astimezone(ZoneInfo(active_settings.app_timezone)).date()
            async with sessions.begin() as session:
                result = await session.execute(
                    text(
                        "INSERT INTO scheduled_run_slots (delivery_at, run_date, status) "
                        "VALUES (:delivery_at, :run_date, 'started') "
                        "ON CONFLICT DO NOTHING RETURNING delivery_at"
                    ),
                    {"delivery_at": delivery_at, "run_date": run_date},
                )
            return result.scalar_one_or_none() is not None

        async def record_scheduled_result(
            delivery_at: datetime, status: str, summary: str | None
        ) -> None:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "UPDATE scheduled_run_slots SET status = :status, message = :message, "
                        "completed_at = now() WHERE delivery_at = :delivery_at"
                    ),
                    {"delivery_at": delivery_at, "status": status, "message": summary},
                )

        app.state.scheduler = DailyScheduler(
            active_settings.scheduler_enabled,
            active_settings.scheduler_daily_time,
            active_settings.app_timezone,
            run_scheduled_now,
            claim_scheduled_slot,
            record_scheduled_result,
        )
        gmail_polling_scheduler = GmailPollingScheduler(
            active_settings.gmail_enabled,
            60,
            run_gmail_poll,
        )
        app.state.gmail_polling_scheduler = gmail_polling_scheduler
        if active_settings.retention_enabled:
            app.state.retention_scheduler = RetentionScheduler(
                RetentionJob(
                    sessions,
                    public_raw_days=active_settings.public_raw_content_retention_days,
                    operational_days=active_settings.operational_retention_days,
                ),
                active_settings.retention_interval_hours,
            )
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(agent_router)
    app.include_router(telegram_router)

    logging.getLogger(__name__).info(
        "application_configured",
        extra={"environment": active_settings.app_env},
    )
    return app


app = create_app()


def _missing_gmail_cipher(value: str) -> str:
    raise ValueError("Gmail token cipher is unavailable")


def _json_strings(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return (
        [str(item) for item in parsed if isinstance(item, str)]
        if isinstance(parsed, list)
        else []
    )


_CALIBRATION_EVENT_WORDS = frozenset(
    {"conference", "congress", "convention", "disrupt", "expo", "festival", "mwc", "summit", "wwdc"}
)
_CALIBRATION_SINGLE_WORD_PUBLISHERS = frozenset({"nytimes", "techcrunch"})
_CALIBRATION_GENERIC_SUBJECTS = frozenset(
    {"ai", "industry", "startup", "startups", "tech", "technology"}
)
_CALIBRATION_VARIANT_SUFFIXES = frozenset(
    {
        "development", "developments", "feature", "features", "gelişme", "gelişmeleri",
        "güncelleme", "güncellemeleri", "news", "update", "updates",
    }
)


def select_telegram_calibration_candidates(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, str]]:
    """Choose concrete subjects, skipping global news and obvious source/event labels."""
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if str(row.get("section", "")) == "World in Brief":
            continue
        source_urls = row.get("source_urls")
        publisher_keys = (
            {
                key
                for url in source_urls
                if isinstance(url, str) and (key := _source_site_key(url))
            }
            if isinstance(source_urls, list)
            else set()
        )
        subjects = _json_strings(row.get("entities_json")) + _json_strings(
            row.get("topics_json")
        )
        for subject in subjects:
            normalized = " ".join(subject.split())[:128]
            key = _calibration_subject_key(normalized)
            if not key or key in seen:
                continue
            words = re.findall(r"[^\W_]+", normalized.casefold())
            is_publisher = bool(_calibration_publisher_keys(normalized) & publisher_keys)
            if is_publisher and len(words) == 1:
                is_publisher = key in _CALIBRATION_SINGLE_WORD_PUBLISHERS
            if is_publisher:
                continue
            seen.add(key)
            candidates.append({"event_id": str(row.get("event_id", "")), "subject": normalized})
            break
        if len(candidates) == 3:
            break
    return candidates


def _calibration_subject_key(value: str) -> str:
    words = re.findall(r"[^\W_]+", value.casefold())
    compact = "".join(words)
    if (
        any(_is_calibration_year(word) for word in words)
        or any(word in _CALIBRATION_EVENT_WORDS for word in words)
        or "demoday" in compact
        or "googleio" in compact
    ):
        return ""
    while words and words[-1] in _CALIBRATION_VARIANT_SUFFIXES:
        words.pop()
    key = " ".join(words)
    return "" if key in _CALIBRATION_GENERIC_SUBJECTS else key


def _is_calibration_year(value: str) -> bool:
    return len(value) == 4 and value.isdigit() and value.startswith(("19", "20"))


def _calibration_publisher_keys(value: str) -> set[str]:
    words = re.findall(r"[^\W_]+", value.casefold())
    keys = {"".join(words)} if words else set()
    if words and words[0] == "the":
        words = words[1:]
    if words:
        keys.add("".join(words))
    if len(words) > 1:
        keys.add("".join(word[0] for word in words[:-1]) + words[-1])
    return keys


def _source_site_key(value: str) -> str:
    try:
        host = (urlsplit(value).hostname or "").casefold().removeprefix("www.")
    except ValueError:
        return ""
    if not host:
        return ""
    return "".join(re.findall(r"[^\W_]+", host.split(".", 1)[0]))


async def _reblock_retry(
    sessions: async_sessionmaker[AsyncSession], content_hash: str, category: str
) -> None:
    """Return an explicitly claimed retry to the safe blocked state without payload storage."""
    async with sessions.begin() as session:
        await session.execute(
            text(
                "UPDATE post_llm_failures SET failure_category = :category, "
                "retry_state = 'blocked', updated_at = now() WHERE content_hash = :content_hash"
            ),
            {"content_hash": content_hash, "category": category},
        )


def _retry_failure_category(run: object) -> str:
    """Map retry-only safe counters without rendering provider/source error text."""
    categories = (
        ("gatekeeper_errors", "gatekeeper_error"),
        ("caption_access_errors", "yt_dlp_caption_access_error"),
        ("youtube_feed_access_errors", "youtube_feed_access_error"),
        ("briefing_item_errors", "briefing_item_error"),
        ("provider_busy", "provider_busy"),
        ("budget_exhausted", "budget_exhausted"),
        ("skipped_no_captions", "skipped_no_captions"),
        ("skipped_no_preferred_language_caption", "skipped_no_preferred_language_caption"),
    )
    return next(
        (category for field, category in categories if getattr(run, field, 0)),
        "retry_failed",
    )


async def _find_blocked_youtube_item(
    catalog: SourceCatalog,
    content_hash: str,
    fetched_at: datetime,
    *,
    allow_private_hosts: bool = True,
    allow_insecure_http: bool = True,
) -> tuple[YouTubeSourceConfig, SourceItem] | None:
    """Recover metadata for a legacy block only during the user's explicit retry request."""
    discovery = YouTubeDiscovery(
        HttpFeedFetcher(
            allow_private_hosts=allow_private_hosts,
            allow_insecure_http=allow_insecure_http,
        )
    )
    for source in catalog.youtube:
        if not source.enabled:
            continue
        try:
            candidates = await discovery.collect(source, fetched_at=fetched_at)
        except Exception:
            continue
        if item := next(
            (candidate for candidate in candidates if candidate.content_hash == content_hash), None
        ):
            return source, item
    return None


def _admin_credentials_valid(request: Request, settings: Settings) -> bool:
    """Verify Basic credentials without retaining or logging either supplied value."""
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Basic "):
        return False
    try:
        import base64

        decoded = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (UnicodeDecodeError, ValueError):
        return False
    return secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(
        password, settings.admin_password_value
    )


def _same_admin_origin(request: Request, settings: Settings) -> bool:
    """Require the configured origin, plus the explicitly supported localhost SSH tunnel."""
    origin = request.headers.get("origin", "").rstrip("/")
    expected = settings.admin_public_origin.rstrip("/")
    if origin and expected and secrets.compare_digest(origin, expected):
        return True
    # Production may intentionally publish Admin as https://localhost while an operator
    # accesses it through the documented `ssh -L 8000:127.0.0.1:8000` tunnel.
    return (
        origin == "http://localhost:8000"
        and urlsplit(expected).scheme == "https"
        and urlsplit(expected).hostname == "localhost"
        and request.url.scheme == "http"
        and request.url.hostname == "localhost"
        and request.url.port == 8000
    )


def _request_is_https(request: Request, settings: Settings) -> bool:
    if request.url.scheme == "https":
        return True
    client_host = request.client.host if request.client else ""
    if client_host not in settings.trusted_proxy_ip_list:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return forwarded_proto.split(",", 1)[0].strip().casefold() == "https"
