"""FastAPI application factory and production ASGI entrypoint."""

import asyncio
import logging
import secrets
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
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
from app.briefing.presentation import compact_sentences, legacy_sections, safe_links
from app.collectors.article import ArticleFetcher
from app.collectors.rss import HttpFeedFetcher, RssCollector
from app.collectors.youtube import YouTubeDiscovery
from app.config.models import load_model_settings
from app.config.settings import Settings, get_settings
from app.config.sources import SourceCatalog, YouTubeSourceConfig, load_source_catalog
from app.db.session import check_database_ready, create_engine, create_session_factory
from app.email.core import TokenCipher
from app.email.gmail_api import GmailApiClient
from app.email.oauth import GmailOAuth
from app.ingestion.schemas import SourceItem, SourceKind, TimestampConfidence
from app.jobs.gmail_runtime import GmailAccountRecord, GmailRuntimeJob
from app.jobs.rss_runtime import RssRuntimeJob, database_persistence
from app.jobs.scheduler import DailyScheduler, RuntimeRunCoordinator
from app.jobs.youtube_runtime import YouTubeRuntimeJob
from app.knowledge.reembedding import ReembeddingRecord, ReembeddingService
from app.knowledge.search import (
    KnowledgeSearchService,
    SearchFilters,
    answer_question,
    fetch_sql_candidates,
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
    notification_key,
)
from app.notifications.ntfy import NtfyNotifier
from app.observability.logging import configure_logging

ReadinessCheck = Callable[[], Awaitable[bool]]


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
        scheduler = getattr(lifespan_app.state, "scheduler", None)
        if scheduler:
            scheduler.start()
        yield
        if scheduler:
            await scheduler.stop()
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
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=active_settings.allowed_host_list)

    @app.middleware("http")
    async def protect_admin_and_add_security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Apply production-only access control, CSRF origin checks, and browser hardening."""
        is_admin = request.url.path == "/admin" or request.url.path.startswith("/admin/")
        is_agent_api = request.url.path.startswith("/api/v1/")
        if is_admin and active_settings.admin_auth_enabled:
            if not _admin_credentials_valid(request, active_settings):
                return PlainTextResponse(
                    "Admin authentication required.",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Personal Intelligence Admin"'},
                )
            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _same_admin_origin(
                request, active_settings
            ):
                return PlainTextResponse("Invalid admin request origin.", status_code=403)
        if active_settings.force_https and request.url.path not in {"/health", "/ready"}:
            forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            proto = forwarded_proto.split(",")[0].strip()
            if proto != "https":
                secure_url = request.url.replace(scheme="https")
                return RedirectResponse(str(secure_url), status_code=307)
        response: Response = await call_next(request)
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
            "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
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

    app.state.readiness_check = readiness_check
    app.state.engine = engine
    app.state.agent_api_settings = active_settings
    app.state.agent_api_rate_limiter = AgentApiRateLimiter(
        active_settings.agent_api_rate_limit_per_minute
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
        provider_coordinator = ProviderCallCoordinator()
        app.state.provider_coordinator = provider_coordinator
        notification_dispatcher = None
        if active_settings.ntfy_enabled:
            ntfy_notifier = NtfyNotifier(
                active_settings.ntfy_base_url,
                active_settings.ntfy_topic,
                active_settings.ntfy_token_value,
                active_settings.ntfy_request_timeout_seconds,
                active_settings.ntfy_max_retries,
            )
            notification_dispatcher = database_dispatcher(sessions, ntfy_notifier.send)
        app.state.notifications_enabled = notification_dispatcher is not None

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
                                    "SELECT id, canonical_title, raw_content, embedding_model_id, embedding_dimensions "
                                    "FROM events WHERE embedding IS NULL OR embedding_model_id != :model "
                                    "OR (:dimensions IS NOT NULL AND embedding_dimensions != :dimensions) "
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
                                "embedding_model_id = :model, embedding_dimensions = :dimensions WHERE id = :id"
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

        async def deliver_run_notifications(
            result: dict[str, object], gmail_items: list[BriefingItem]
        ) -> list[str]:
            """Deliver minimal post-persistence notices without changing a completed run result."""
            if notification_dispatcher is None:
                return ["disabled"]
            local_day = datetime.now(UTC).astimezone(
                ZoneInfo(active_settings.app_timezone)
            ).date().isoformat()
            admin_link = (
                f"{active_settings.admin_public_origin}/admin"
                if active_settings.admin_public_origin
                else None
            )
            notifications: list[Notification] = []
            counts = result.get("counts")
            processed = int(counts.get("processed", 0)) if isinstance(counts, dict) else 0
            if processed:
                notifications.append(
                    Notification(
                        idempotency_key=notification_key(
                            NotificationKind.BRIEFING_READY, local_day
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
                notifications.append(
                    Notification(
                        idempotency_key=notification_key(
                            NotificationKind.OPERATIONAL_FAILURE, local_day
                        ),
                        kind=NotificationKind.OPERATIONAL_FAILURE,
                        title="İşlem uyarısı",
                        body=(
                            "Günlük işlem güvenli hata durumu ile tamamlandı. "
                            "Ayrıntılar yönetim panelinde."
                        ),
                        link=admin_link,
                    )
                )
            results = await asyncio.gather(
                *(notification_dispatcher.deliver(notification) for notification in notifications)
            )
            return [delivery.status for delivery in results] or ["no_notification"]

        async def run_rss_now() -> dict[str, object]:
            """Run independently bounded Gmail, YouTube, and RSS paths in one briefing cycle."""
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
            catalog = load_source_catalog(active_settings.admin_sources_path)
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
                    )
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
            )
            gmail_job = GmailRuntimeJob(
                gmail_accounts,
                cipher.reveal if cipher else _missing_gmail_cipher,
                fetch_gmail_account,
                known_gmail_message,
                persist_gmail_classification,
                update_gmail_checkpoint,
            )
            gmail_run = await gmail_job.run()
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
            ).run()
            youtube_llm = usage_breakdown(router.calls[youtube_call_start:])
            rss_call_start = len(router.calls)
            result = await job.run([*gmail_run.action_items, *youtube_run.briefing_items])
            rss_llm = usage_breakdown(router.calls[rss_call_start:])
            gmail_counts = gmail_run.response(active_settings.gmail_enabled)["gmail"]
            gmail_llm = usage_breakdown([])
            briefing_editor_llm = usage_breakdown([])
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
            if gmail_run.failed:
                result["message"] += f" Gmail sync had {gmail_run.failed} safe failure(s)."
            if youtube_run.failed:
                result["message"] += f" YouTube sync had {youtube_run.failed} safe failure(s)."
            result["notifications"] = await deliver_run_notifications(
                result, gmail_run.action_items
            )
            return result

        run_coordinator = RuntimeRunCoordinator()

        async def run_manual_now() -> dict[str, object]:
            return await run_coordinator.run("manual", run_rss_now)

        async def run_scheduled_now() -> dict[str, object]:
            return await run_coordinator.run("scheduled", run_rss_now)

        app.state.run_coordinator = run_coordinator
        app.state.run_callback = run_manual_now

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

        async def agent_briefing_items(briefing_id: str, rendered: str) -> list[AgentBriefingItem]:
            """Select only safe persisted briefing/event/action fields for Agent API reads."""
            async with sessions() as session:
                rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT bi.section, bc.title AS briefing_title, bc.summary_tr, "
                                "bc.what_changed_tr, bc.why_important_tr, e.canonical_title, "
                                "e.occurred_at, ec.classification, ec.action_summary, ec.deadline, "
                                "ec.application_company, ec.created_at AS email_recorded_at, "
                                "ARRAY(SELECT c.statement FROM claims c WHERE c.event_id = bi.event_id "
                                "ORDER BY c.id LIMIT 5) AS facts, "
                                "ARRAY(SELECT i.inference_text FROM inferences i "
                                "WHERE i.event_id = bi.event_id ORDER BY i.id LIMIT 3) AS inferences, "
                                "ARRAY(SELECT es.canonical_url FROM event_sources es "
                                "WHERE es.event_id = bi.event_id AND es.canonical_url IS NOT NULL "
                                "ORDER BY es.canonical_url LIMIT 3) AS source_links "
                                "FROM briefing_items bi "
                                "LEFT JOIN briefing_item_content bc ON bc.briefing_id = bi.briefing_id "
                                "AND bc.event_id = bi.event_id "
                                "LEFT JOIN events e ON e.id = bi.event_id "
                                "LEFT JOIN email_classifications ec ON ec.source_item_id = bi.event_id "
                                "WHERE bi.briefing_id = :briefing_id "
                                "ORDER BY bi.section, e.occurred_at DESC NULLS LAST"
                            ),
                            {"briefing_id": briefing_id},
                        )
                    )
                    .mappings()
                    .all()
                )
            if not rows:
                return [
                    AgentBriefingItem(
                        section=item.section,
                        title=item.title[:320],
                        summary=compact_sentences(item.summary, max_chars=600),
                        source_links=safe_links(item.source_links),
                        original_text=True,
                    )
                    for items in legacy_sections(rendered).values()
                    for item in items
                ]
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
            return result

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
                                "FROM briefings b LEFT JOIN briefing_items bi ON bi.briefing_id = b.id "
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

        async def retry_blocked_youtube(content_hash: str) -> dict[str, object]:
            """Run exactly one explicitly claimed retry; scheduler/manual runs remain blocked."""
            record = await claim_blocked_item(content_hash, "youtube")
            if record is None:
                return {"status": "retry_not_available"}
            source_name = record.get("source_name")
            video_url = record.get("canonical_url")
            catalog = load_source_catalog(active_settings.admin_sources_path)
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
            catalog = load_source_catalog(active_settings.admin_sources_path)
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

        async def claim_scheduled_day(run_date: date) -> bool:
            async with sessions.begin() as session:
                result = await session.execute(
                    text(
                        "INSERT INTO scheduled_runs (run_date, status) "
                        "VALUES (:run_date, 'started') "
                        "ON CONFLICT DO NOTHING RETURNING run_date"
                    ),
                    {"run_date": run_date},
                )
            return result.scalar_one_or_none() is not None

        async def record_scheduled_result(run_date: date, status: str, summary: str | None) -> None:
            async with sessions.begin() as session:
                await session.execute(
                    text(
                        "UPDATE scheduled_runs SET status = :status, message = :message, "
                        "completed_at = now() WHERE run_date = :run_date"
                    ),
                    {"run_date": run_date, "status": status, "message": summary},
                )

        app.state.scheduler = DailyScheduler(
            active_settings.scheduler_enabled,
            active_settings.scheduler_daily_time,
            active_settings.app_timezone,
            run_scheduled_now,
            claim_scheduled_day,
            record_scheduled_result,
        )
    app.include_router(health_router)
    app.include_router(admin_router)
    app.include_router(agent_router)

    logging.getLogger(__name__).info(
        "application_configured",
        extra={"environment": active_settings.app_env},
    )
    return app


app = create_app()


def _missing_gmail_cipher(value: str) -> str:
    raise ValueError("Gmail token cipher is unavailable")


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
    """Require the configured browser origin for authenticated state-changing admin requests."""
    origin = request.headers.get("origin", "").rstrip("/")
    expected = settings.admin_public_origin.rstrip("/")
    return bool(origin and expected and secrets.compare_digest(origin, expected))
