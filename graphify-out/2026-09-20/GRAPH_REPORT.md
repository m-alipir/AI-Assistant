# Graph Report - AI Personal Assistant  (2026-09-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1949 nodes · 4652 edges · 133 communities (80 shown, 28 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 828 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `51bad569`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- search.py
- SourceCatalog
- ProviderError
- test_llm.py
- test_telegram.py
- SourceItem
- create_app
- agent.py
- YouTubeRuntimeJob
- DailyScheduler
- Settings
- llm/core.py
- rsshub.py
- admin.py
- test_gmail_oauth.py
- ExtractionFlow
- contracts.py
- SubtitleTrack
- gmail_runtime.py
- TelegramDeliveryError
- MemoryEvent
- rss.py
- add_source
- SearchFilters
- service.py
- EmailMessage
- Router
- RetentionJob
- safe_links
- source_health.py
- BudgetTracker
- rss_runtime.py
- run_rss_now
- RssCollector
- TelegramBotClient
- TelegramWebhookHandler
- ValueError
- test_security_hardening.py
- database_persistence
- test_agent_api.py
- BriefingItem
- SqlAlchemyLlmRepository
- email/core.py
- logging.py
- load_model_settings
- test_notifications.py
- test_poller_reuses_handler_and_advances_cursor_after_safe_skips
- _load_yaml
- classify
- ReembeddingService
- YouTubeDiscovery
- youtube_runtime.py
- Base
- find_cluster
- NtfyNotifier
- .__init__
- health.py
- .__init__
- session.py
- GmailApiClient
- interests/core.py
- record_briefing_feedback
- main.py
- Notification
- database_dispatcher
- persist_event
- base.py
- protect_admin_and_add_security_headers
- env.py
- test_rss_post_llm_failure_blocks_a_repeat_before_another_provider_attempt
- test_durable_outbox_is_locked_and_deleted_only_with_briefing_persistence
- test_sqlalchemy_repository_aggregates_metadata_only_daily_spend
- _requested_subtitle_tracks
- .__init__
- BriefingFeedback
- .normalize_to_utc
- test_health.py
- SourceDefaults
- llm_models.py
- 20260906_0001_enable_pgvector.py
- test_search_sql_supports_current_metadata_and_legacy_rows
- _MappingResult
- .run
- .__init__
- .__init__
- backup-postgres.sh
- restore-postgres.sh
- briefing/__init__.py
- collectors/__init__.py
- config/__init__.py
- correlation/__init__.py
- db/__init__.py
- dedup/__init__.py
- email/__init__.py
- freshness/__init__.py
- ingestion/__init__.py
- app/__init__.py
- interests/__init__.py
- jobs/__init__.py
- knowledge/__init__.py
- llm/__init__.py
- normalize/__init__.py
- notifications/__init__.py
- observability/__init__.py
- pilot/__init__.py
- providers/__init__.py
- telegram/__init__.py
- personal-intelligence-system

## God Nodes (most connected - your core abstractions)
1. `create_app()` - 142 edges
2. `Settings` - 61 edges
3. `Router` - 51 edges
4. `SourceItem` - 50 edges
5. `database_persistence()` - 41 edges
6. `ProviderError` - 40 edges
7. `OpenRouterClient` - 40 edges
8. `SourceCatalog` - 38 edges
9. `BudgetTracker` - 38 edges
10. `ExtractionFlow` - 34 edges

## Surprising Connections (you probably didn't know these)
- `test_search_runtime_error_is_available_to_the_admin_as_a_safe_category()` --uses--> `KnowledgeSearchError`  [INFERRED]
  tests/test_search.py → app/knowledge/search.py
- `test_bounded_reasoner_context_returns_inferences_separate_from_verified_facts()` --uses--> `SafeEmailResult`  [INFERRED]
  tests/test_search.py → app/knowledge/search.py
- `test_gmail_action_item_is_returned_without_event_metadata()` --uses--> `SafeEmailResult`  [INFERRED]
  tests/test_search.py → app/knowledge/search.py
- `test_reasoner_context_respects_role_limit_with_large_retained_fields()` --uses--> `SafeEmailResult`  [INFERRED]
  tests/test_search.py → app/knowledge/search.py
- `test_reasoner_context_respects_role_limit_with_large_retained_fields()` --uses--> `SearchEvent`  [INFERRED]
  tests/test_search.py → app/knowledge/search.py

## Import Cycles
- None detected.

## Communities (133 total, 28 thin omitted)

### Community 0 - "search.py"
Cohesion: 0.06
Nodes (58): HybridRetriever, InMemoryKnowledgeRepository, _normal(), datetime, Small in-memory M3 repository and deterministic hybrid retrieval service., Offline repository fake used by M3 acceptance tests before job wiring is…, Apply raw-content retention without deleting distilled event/provenance records., Structured filtering then deterministic lexical/vector scoring over the… (+50 more)

### Community 1 - "SourceCatalog"
Cohesion: 0.07
Nodes (29): ArticleContent, The complete seedable RSS and YouTube source catalog., SourceCatalog, BriefingRenderError, Connect existing collector, deterministic gate, LLM flow, and persistence…, Safe category for an in-memory briefing composition/render failure., RssRuntimeJob, GatekeeperResult (+21 more)

### Community 2 - "ProviderError"
Cohesion: 0.06
Nodes (35): ArticleFetcher, _extract_html(), Safe, bounded public article fetch and offline HTML extraction boundary., Fetch public HTML with redirect-by-redirect validation and response bounds., Parse already-fetched HTML only; parsing never initiates another network…, _visible_html_text(), _VisibleText, ConditionalFeedResult (+27 more)

### Community 3 - "test_llm.py"
Cohesion: 0.10
Nodes (35): BudgetExceeded, InMemoryResultCache, ModelSettings, OpenRouterClient, AsyncBaseTransport, Validated model configuration loaded at the application edge., Return safe per-role request metadata, separating provider work from cache hits., Small direct HTTP client with bounded retries and no payload logging. (+27 more)

### Community 4 - "test_telegram.py"
Cohesion: 0.08
Nodes (25): _search_text(), _callback_handler(), _callback_payload(), _client(), _FeedbackStore, _handler(), _payload(), parametrize (+17 more)

### Community 5 - "SourceItem"
Cohesion: 0.09
Nodes (38): Expose configured defaults directly to the freshness-first pipeline., InMemoryDedupCache, Idempotent in-process identity cache for the deterministic ingestion stage., Return true once for a unique item and false for subsequent equivalent items., Reserve external-ID, canonical-URL, and content-hash identities in priority…, assess_freshness(), Freshness classification before article extraction or model work., Classify an item using published time, or discovered time only as a marked… (+30 more)

### Community 6 - "create_app"
Cohesion: 0.08
Nodes (33): create_app(), search_knowledge(), telegram_add_source(), telegram_disable_source(), telegram_set_interest(), telegram_sources(), telegram_status(), _telegram_subject() (+25 more)

### Community 7 - "agent.py"
Cohesion: 0.09
Nodes (40): AgentBriefingDetail, AgentBriefingItem, AgentBriefingPage, AgentBriefingSummary, AgentEmailAction, AgentKnowledgeResponse, AgentSearchEvent, _audit() (+32 more)

### Community 8 - "YouTubeRuntimeJob"
Cohesion: 0.12
Nodes (19): Apply freshness/dedup/captions before existing gatekeeper and extractor calls., YouTubeRuntimeJob, catalog(), FakeFlow, FakeSubtitles, FixtureFetcher, asyncio, test_event_persistence_failure_blocks_another_costly_attempt() (+11 more)

### Community 9 - "DailyScheduler"
Cohesion: 0.08
Nodes (24): DailyScheduler, datetime, Opt-in daily scheduler with durable per-day claims., Persist only aggregate operational counts, never source or provider payloads., Process-local non-blocking guard shared by manual and scheduled operations., Run once or return a safe skip rather than queueing concurrent expensive work., One daily opt-in job; durable claiming prevents restart double-runs., RuntimeRunCoordinator (+16 more)

### Community 10 - "Settings"
Cohesion: 0.07
Nodes (24): Path, Validated settings loaded from environment variables or a local ``.env`` file., Return the normalized SQLAlchemy connection URL without exposing it in logs., Return the OAuth secret from an environment value or mounted secret file., Return the Fernet key without ever rendering it in diagnostics., Return the OpenRouter credential from an environment value or secret file., Return the dedicated Agent API secret only for constant-time request…, Return the admin password only for constant-time request verification. (+16 more)

### Community 11 - "llm/core.py"
Cohesion: 0.06
Nodes (26): _bounded_metadata_prompt(), _bounded_untrusted_json(), EmbeddingResponse, _grounded_claims(), OpenRouterConfig, OpenRouterResponse, _provider_cost(), ProviderCallCoordinator (+18 more)

### Community 12 - "rsshub.py"
Cohesion: 0.10
Nodes (29): database_observation_writer(), _elapsed_ms(), load_observations(), main(), PilotRouteObservation, async_sessionmaker, AsyncSession, datetime (+21 more)

### Community 13 - "admin.py"
Cohesion: 0.12
Nodes (34): briefing_detail(), briefing_feedback(), briefings(), config(), gmail_callback(), gmail_connect(), interests(), _oauth_failure_response() (+26 more)

### Community 14 - "test_gmail_oauth.py"
Cohesion: 0.10
Nodes (22): classify_token_endpoint_error(), GmailOAuth, OAuthFlowError, Exception, OAuthErrorCategory, Bounded Google OAuth code flow; secrets are never logged or returned., A safe, user-actionable OAuth failure with no provider payload., Map only Google's non-secret ``error`` code to a safe diagnostic category. (+14 more)

### Community 15 - "ExtractionFlow"
Cohesion: 0.11
Nodes (20): ExtractedClaim, ExtractionFlow, ExtractorResult, BaseModel, model_validator, Accept harmless omissions/aliases without inventing source facts or retrying a…, Minimal gatekeeper/extractor flow that sends only compact delimited source…, Embed only compact event/claim text after extraction; never raw feeds or… (+12 more)

### Community 16 - "contracts.py"
Cohesion: 0.12
Nodes (23): CollectorProvider, ExternalItem, LlmProvider, LlmRequest, LlmResponse, BaseModel, Protocol, Narrow, testable contracts for network-backed providers. (+15 more)

### Community 17 - "SubtitleTrack"
Cohesion: 0.09
Nodes (22): _matches_language(), parse_webvtt(), yt-dlp wrapper that downloads selected VTT captions but never media or audio., Run blocking yt-dlp work off the event loop and enforce a total timeout., Prefer configured language, then Turkish/English, before another available…, Keep legacy requests unchanged, but request only the configured language family., Parse standard WebVTT cues while keeping their source timings intact., Convert ``HH:MM:SS.mmm`` or ``MM:SS.mmm`` VTT timestamps to seconds. (+14 more)

### Community 18 - "gmail_runtime.py"
Cohesion: 0.14
Nodes (23): GmailBatch, GmailAccountRecord, GmailRuntimeJob, Gmail job wiring that keeps credentials and message bodies outside…, Run bounded account syncs independently so a Gmail failure cannot stop RSS., message(), asyncio, datetime (+15 more)

### Community 19 - "TelegramDeliveryError"
Cohesion: 0.10
Nodes (21): get_settings(), Environment-backed runtime settings., Return the process-wide settings instance., main(), Explicit VDS-only webhook setup; it never runs during application startup., RuntimeError, Small direct Telegram Bot API client with safe plain-text rendering., Safe outbound error category; provider details must never leave the client. (+13 more)

### Community 20 - "MemoryEvent"
Cohesion: 0.17
Nodes (23): CorrelationPolicy, CorrelationResult, MemoryEvent, BaseModel, M4 deterministic escalation and compact, evidence-bound correlation records., Model boundary: relation remains an inference with explicit event/claim…, Use a strong reasoner only for meaningful, already-narrowed candidates., Keep only top relevant historical memories; never send the whole event store. (+15 more)

### Community 21 - "rss.py"
Cohesion: 0.13
Nodes (20): _author(), _entry_text(), _external_id(), Any, Bounded RSS/Atom collection and compact item normalization., Choose compact feed-provided summary text without fetching the linked article., Prefer feed-native identifiers before falling back to URL/hash identity., Extract an optional compact author value from common feedparser fields. (+12 more)

### Community 22 - "add_source"
Cohesion: 0.18
Nodes (25): add_source(), disable_source(), list_sources(), _load_catalog(), _load_data(), _looks_like_youtube(), Any, Path (+17 more)

### Community 23 - "SearchFilters"
Cohesion: 0.21
Nodes (22): answer_question(), KnowledgeSearchService, Answer only from bounded retained candidates; no candidates means no model…, Deterministic limits applied before candidate ranking or optional model use., Apply deterministic date/metadata narrowing then the existing hybrid ranker., SearchFilters, ask_knowledge(), event() (+14 more)

### Community 24 - "service.py"
Cohesion: 0.11
Nodes (21): feedback_keyboard(), Build fixed actions; server-side token lookup supplies the event and actor…, _actor_for(), _bounded_body(), _callback_answer_text(), _command(), _feedback_data(), _help_text() (+13 more)

### Community 25 - "EmailMessage"
Cohesion: 0.15
Nodes (16): EmailMessage, _deduplicated(), GmailApiError, _json_mapping(), _message_ids(), _metadata_message(), _optional_string(), Any (+8 more)

### Community 26 - "Router"
Cohesion: 0.12
Nodes (15): LlmError, ProviderBusy, RuntimeError, Non-sensitive usage/cost metadata retained for operational accounting., Configuration-driven fallback router with cache, strict validation, and…, Account for every provider/cache attempt without retaining request/response…, Return cached or provider-validated structured data with safe fallback behavior., Safe LLM boundary failure that never contains request content or credentials. (+7 more)

### Community 27 - "RetentionJob"
Cohesion: 0.11
Nodes (12): Any, datetime, Bounded, opt-in PostgreSQL retention maintenance., Expire raw public content and old operational metadata without deleting…, Run maintenance immediately and periodically without provider work., RetentionJob, RetentionScheduler, asyncio (+4 more)

### Community 28 - "safe_links"
Cohesion: 0.12
Nodes (23): _display_section(), _json_strings(), _load_briefing_sections(), Join only briefed event provenance and compact claims, never raw source/email…, _source_type(), BriefingViewItem, compact_sentences(), format_istanbul() (+15 more)

### Community 29 - "source_health.py"
Cohesion: 0.14
Nodes (18): classify_fetch_failure(), database_source_health(), failure(), FetchFailure, HealthDecision, next_retry_at(), async_sessionmaker, AsyncSession (+10 more)

### Community 30 - "BudgetTracker"
Cohesion: 0.15
Nodes (16): BudgetPolicy, BudgetTracker, datetime, Return configured primary then ordered configured fallbacks., Daily spending guardrails; email action work may use its reserved allowance., UTC-day budget state, hydrated from metadata-only persistence before preflight., Replace this process's daily view with durable aggregate spending., Report whether prior daily spending reached a total or role soft threshold. (+8 more)

### Community 31 - "rss_runtime.py"
Cohesion: 0.11
Nodes (18): BriefingPersistenceError, _ignore_correlation(), _ignore_post_llm_failure(), _ignore_refresh_blocked_item(), BaseException, datetime, RuntimeError, The small RSS-only runtime path used by the local admin manual trigger. (+10 more)

### Community 32 - "run_rss_now"
Cohesion: 0.13
Nodes (23): claim_blocked_item(), has_pending_briefing(), is_post_llm_failed(), known_item(), mark_post_llm_failure(), refresh_blocked_item(), resolve_blocked_item(), fetch_gmail_account() (+15 more)

### Community 33 - "RssCollector"
Cohesion: 0.13
Nodes (15): datetime, Collect RSS/Atom metadata only; article-body fetching is deliberately out of…, Fetch and normalize source entries into compact candidate items., RssCollector, load_source_catalog(), Path, One RSS or Atom source configured for collection., Load a YAML source catalog without accepting executable YAML constructs. (+7 more)

### Community 34 - "TelegramBotClient"
Cohesion: 0.12
Nodes (10): Disable a prior webhook without discarding queued Telegram updates., Receive one bounded long-poll batch without retaining provider response bodies., Send only bounded plain-text Bot API messages through a direct HTTP boundary., Send one message with no parse mode, previews, or unbounded provider error…, Map the existing minimized notification contract into one protected Telegram…, Dismiss Telegram's callback spinner with a fixed, non-sensitive status message., Set approved update types through an explicit operator action, never at startup., TelegramBotClient (+2 more)

### Community 35 - "TelegramWebhookHandler"
Cohesion: 0.24
Nodes (8): Split at a readable boundary while preserving literal, non-formatted text., split_plain_text(), TelegramMessage, Actor, _hash(), Keep Telegram untrusted until secret verification and actor-pair authorization…, TelegramWebhookHandler, test_plain_text_split_preserves_literal_content_without_format_mode()

### Community 36 - "ValueError"
Cohesion: 0.12
Nodes (10): field_validator, model_validator, Fail closed when a production process would expose its admin surface., Parse explicit user/chat pairs, avoiding an accidental cross-product allow-list., model_validator, Permit disabled placeholders while keeping source configuration non-secret., Reject example placeholders only when the source is switched on., _missing_gmail_cipher() (+2 more)

### Community 37 - "test_security_hardening.py"
Cohesion: 0.15
Nodes (16): create_engine(), Create the application's asynchronous PostgreSQL engine., _basic_header(), _production_settings(), asyncio, Path, Offline regressions for production access and outbound-content hardening., test_admin_failed_authentication_is_process_limited() (+8 more)

### Community 38 - "database_persistence"
Cohesion: 0.14
Nodes (19): database_persistence(), async_sessionmaker, AsyncSession, IsPostLlmFailed, KnownItem, PersistEvent, PostLlmFailure, RefreshBlockedItem (+11 more)

### Community 39 - "test_agent_api.py"
Cohesion: 0.21
Nodes (15): _app(), _briefing(), _headers(), Offline contract and privacy regressions for the separate read-only Agent API., test_agent_api_briefing_pagination_is_bounded(), test_agent_api_enforces_request_size_and_rate_limit(), test_agent_api_limits_failed_auth_before_unbounded_audit_writes(), test_agent_api_rejects_missing_or_invalid_token_without_echoing_it() (+7 more)

### Community 40 - "BriefingItem"
Cohesion: 0.22
Nodes (17): BriefingItem, build_sections(), edit_compact(), EditedBriefing, BaseModel, Deterministic M6 briefing queues and local preview., Edit only a bounded, distilled briefing; empty briefings never reach this…, _render_item() (+9 more)

### Community 41 - "SqlAlchemyLlmRepository"
Cohesion: 0.16
Nodes (10): LlmCall, Metadata-only LLM call record; prompts and raw responses are never columns., DailySpend, LlmRepository, datetime, Protocol, Async repository boundary for non-sensitive LLM cache and accounting data., Return metadata-only total and per-role costs since the UTC-day boundary. (+2 more)

### Community 42 - "email/core.py"
Cohesion: 0.18
Nodes (12): InMemoryGmailSync, datetime, Bounded, read-only email classification without live Gmail access in tests., Independent account checkpoints and bounded initial/recovery sync for fixture…, Encrypt OAuth refresh tokens with authenticated Fernet encryption., TokenCipher, message(), datetime (+4 more)

### Community 43 - "logging.py"
Cohesion: 0.13
Nodes (16): bind_request_id(), configure_logging(), JsonFormatter, Minimal structured logging with no request/body capture., Associate a server-generated correlation ID with logs for one request., Clear request context so background work never inherits a prior request ID., Render log records as JSON suitable for container log collection., Configure root logging once, emitting structured records to standard output. (+8 more)

### Community 44 - "load_model_settings"
Cohesion: 0.13
Nodes (14): load_model_settings(), Path, Configuration loader for model-role mappings; business services never select…, Load role mappings, fallbacks, and budget limits from safe YAML., main(), Advisory OpenRouter catalog command; it never rewrites configuration., Print eligible model IDs from the provider catalog using an explicit…, advisory_candidates() (+6 more)

### Community 45 - "test_notifications.py"
Cohesion: 0.19
Nodes (12): deliver_run_notifications(), notification_key(), NotificationKind, StrEnum, Create an opaque deterministic key without retaining a Gmail/event identifier…, _notification(), asyncio, test_dispatcher_deduplicates_and_isolates_delivery_failure() (+4 more)

### Community 46 - "test_poller_reuses_handler_and_advances_cursor_after_safe_skips"
Cohesion: 0.15
Nodes (9): asyncio, test_callback_answer_retries_transient_failure_and_bounds_timeout(), test_poller_reuses_handler_and_advances_cursor_after_safe_skips(), poll_transport(), test_polling_client_deletes_webhook_and_requests_bounded_updates(), poll_transport(), test_telegram_client_rejects_provider_error_without_exposing_body(), test_telegram_client_retries_only_safe_transient_failures_and_never_uses_markup() (+1 more)

### Community 47 - "_load_yaml"
Cohesion: 0.27
Nodes (16): add_source(), _configured_sources(), _dashboard_context(), _database_details(), delete_source(), _interest_profiles(), _load_yaml(), Any (+8 more)

### Community 48 - "classify"
Cohesion: 0.19
Nodes (12): classify(), classify_unknown(), EmailClassification, GmailAccount, BaseModel, Use the configured cheap role only after deterministic rules leave a message…, Deterministic sender/subject rules run before any optional cheap-model fallback., _briefing_item() (+4 more)

### Community 49 - "ReembeddingService"
Cohesion: 0.21
Nodes (11): Explicit, bounded re-embedding orchestration; never runs automatically at…, Re-embed only missing or incompatible compact retained records in small batches., ReembeddingRecord, ReembeddingService, EmbeddingResult, Cached, model-bound embedding result; vectors never come from a chat model., fetch(), asyncio (+3 more)

### Community 50 - "YouTubeDiscovery"
Cohesion: 0.16
Nodes (9): FeedFetcher, Protocol, Fetch a feed payload with an explicit response-size bound., Return one RSS or Atom XML payload., Discover recent public channel uploads through YouTube's Atom channel feed., YouTubeDiscovery, FixtureFeedFetcher, asyncio (+1 more)

### Community 51 - "youtube_runtime.py"
Cohesion: 0.16
Nodes (9): One public YouTube channel discovered through its Atom feed., Return YouTube's public channel-feed endpoint without any API credential., YouTubeSourceConfig, _ignore_post_llm_failure(), _ignore_refresh_blocked_item(), _language_matches(), Caption-first YouTube runtime built from the existing public Atom and yt-dlp…, Keep standalone/offline jobs side-effect free when no durable guard is supplied. (+1 more)

### Community 52 - "Base"
Cohesion: 0.24
Nodes (13): Base, Base class for persisted models introduced in later milestones., CategoryRow, ClaimRow, EntityAliasRow, EntityRow, EventRow, EventSearchMetadataRow (+5 more)

### Community 53 - "find_cluster"
Cohesion: 0.27
Nodes (12): ClusterCandidate, ClusterMatch, find_cluster(), _normal(), _overlap(), datetime, timedelta, Conservative deterministic clustering for distinct sources covering one public… (+4 more)

### Community 54 - "NtfyNotifier"
Cohesion: 0.18
Nodes (9): NotificationError, RuntimeError, Safe notification failure category; never carries provider response data., NtfyNotifier, Small ntfy HTTP adapter with bounded retries and deterministic sequence IDs., Publish a privacy-minimized notification to one configured ntfy topic., Publish or update the deterministic ntfy sequence for this logical notification., HttpPublish (+1 more)

### Community 55 - ".__init__"
Cohesion: 0.17
Nodes (11): AddSourceCallback, async_sessionmaker, AsyncSession, BriefingCallback, DisableSourceCallback, HistoryCallback, InterestsCallback, SearchCallback (+3 more)

### Community 56 - "health.py"
Cohesion: 0.21
Nodes (11): health(), HealthResponse, BaseModel, get, Request, Response, Liveness and dependency-readiness endpoints., Small health payload with no configuration or secret information. (+3 more)

### Community 57 - ".__init__"
Cohesion: 0.17
Nodes (10): Protocol, Return available manually authored and automatic VTT caption tracks., Download subtitle files only, with video/audio downloads disabled., SubtitleFetcher, datetime, IsPostLlmFailed, KnownItem, PersistEvent (+2 more)

### Community 58 - "session.py"
Cohesion: 0.21
Nodes (11): check_database_ready(), create_session_factory(), get_session(), async_sessionmaker, AsyncEngine, AsyncSession, Async SQLAlchemy engine lifecycle and readiness checks., Create sessions that do not implicitly commit transactions. (+3 more)

### Community 59 - "GmailApiClient"
Cohesion: 0.36
Nodes (10): GmailApiClient, Bounded Gmail metadata collector with retry and history-based incremental sync., asyncio, response(), test_expired_history_uses_bounded_recovery_sync(), handler(), test_incremental_history_sync_avoids_initial_mailbox_query(), handler() (+2 more)

### Community 60 - "interests/core.py"
Cohesion: 0.40
Nodes (8): explicit_intent(), Feedback, Interest, nightly(), BaseModel, datetime, Deterministic M7 interest layers; world ranking intentionally ignores these…, test_m7_stable_learning()

### Community 61 - "record_briefing_feedback"
Cohesion: 0.27
Nodes (9): _display_section(), FeedbackConnection, FeedbackResult, _json_strings(), datetime, Protocol, Shared, transaction-safe briefing feedback boundary for every user interface., Record one allowed signal without allowing a UI to alter ranking rules directly. (+1 more)

### Community 62 - "main.py"
Cohesion: 0.22
Nodes (9): _find_blocked_youtube_item(), datetime, FastAPI application factory and production ASGI entrypoint., Recover metadata for a legacy block only during the user's explicit retry…, Request, Response, Minimal webhook route; all authorization and parsing remain inside the Telegram…, webhook() (+1 more)

### Community 63 - "Notification"
Cohesion: 0.25
Nodes (8): DeliveryResult, Notification, NotificationDispatcher, BaseModel, Provider-neutral notification delivery with durable idempotency boundaries., A compact message that must never contain raw email or provider error text., Ensure a notification cannot undo or duplicate completed ingestion work., Send one claimed notification; failures are isolated from the caller's…

### Community 64 - "database_dispatcher"
Cohesion: 0.18
Nodes (7): database_dispatcher(), async_sessionmaker, AsyncSession, Persist per-channel delivery state and permit safe retries of failed logical…, ClaimDelivery, RecordDelivery, SendNotification

### Community 65 - "persist_event"
Cohesion: 0.20
Nodes (10): correlation_content_hash(), Produce a deterministic cache key without including raw source content., correlate_event(), reasoner(), persist_event(), _json_strings(), _merged_strings(), Serialize finite provider vectors for PostgreSQL without retaining source text. (+2 more)

### Community 66 - "base.py"
Cohesion: 0.20
Nodes (7): AgentApiAuditRow, Metadata-only audit records for the separate read-only Agent API., Never stores caller identity, token, question, source content, or response…, Shared SQLAlchemy declarative metadata., EmailClassificationRow, GmailAccountRow, Minimal persistent Gmail account/checkpoint and classification records.

### Community 67 - "protect_admin_and_add_security_headers"
Cohesion: 0.28
Nodes (8): _admin_credentials_valid(), protect_admin_and_add_security_headers(), Request, Verify Basic credentials without retaining or logging either supplied value., Require the configured browser origin for authenticated state-changing admin…, _request_is_https(), _same_admin_origin(), RedirectResponse

### Community 68 - "env.py"
Cohesion: 0.25
Nodes (8): Connection, do_run_migrations(), Alembic environment for asynchronous PostgreSQL migrations., Generate SQL without opening a database connection., Run migrations against an existing synchronous connection., Create a temporary async engine, migrate, then release all resources., run_migrations_offline(), run_migrations_online()

### Community 73 - "_requested_subtitle_tracks"
Cohesion: 0.33
Nodes (6): Path, Use yt-dlp's library API in a temporary directory to retain captions only., Canonicalize only known public YouTube video URLs before invoking yt-dlp., Read only yt-dlp-created VTT subtitle files from the private temporary…, _requested_subtitle_tracks(), _validated_youtube_video_url()

### Community 74 - ".__init__"
Cohesion: 0.29
Nodes (6): datetime, DecryptToken, FetchAccount, KnownMessage, PersistClassification, UpdateCheckpoint

### Community 75 - "BriefingFeedback"
Cohesion: 0.33
Nodes (6): BriefingFeedback, ModelUpdate, BaseModel, One intentionally small, safe preference signal from a rendered briefing item., SourceCreate, YouTubeLanguageUpdate

### Community 76 - ".normalize_to_utc"
Cohesion: 0.33
Nodes (4): datetime, field_validator, Normalize source dates at the model boundary and reject naïve timestamps., Use publication time when available; discovery time is an explicit fallback.

### Community 77 - "test_health.py"
Cohesion: 0.53
Nodes (5): not_ready(), ready(), test_health_does_not_need_database(), test_ready_reports_available_database(), test_ready_returns_service_unavailable_for_unreachable_database()

### Community 78 - "SourceDefaults"
Cohesion: 0.40
Nodes (4): BaseModel, Global freshness values loaded from the source seed file., Convert YAML defaults into the policy consumed by the ingestion pipeline., SourceDefaults

### Community 79 - "llm_models.py"
Cohesion: 0.40
Nodes (3): LlmResultCache, Nonsensitive operational LLM persistence models., Validated structured result keyed by opaque digest, without input or raw…

### Community 80 - "20260906_0001_enable_pgvector.py"
Cohesion: 0.40
Nodes (4): downgrade(), Enable pgvector in the development PostgreSQL image., Remove pgvector only when explicitly downgrading an otherwise empty foundation., upgrade()

### Community 81 - "test_search_sql_supports_current_metadata_and_legacy_rows"
Cohesion: 0.40
Nodes (5): asyncio, Validate the M22.1 schema against a real dedicated PostgreSQL database., Validate the real PostgreSQL aggregate query and safe Gmail aliasing after…, test_search_sql_supports_current_metadata_and_legacy_rows(), test_telegram_migration_creates_replay_tables_and_channel_key()

### Community 83 - ".run"
Cohesion: 0.50
Nodes (3): _article_extraction_content(), Keep untrusted article text clearly delimited and under the existing extractor…, process()

### Community 84 - ".__init__"
Cohesion: 0.50
Nodes (3): Embed, FetchRecords, PersistVectors

## Knowledge Gaps
- **3 isolated node(s):** `backup-postgres.sh script`, `restore-postgres.sh script`, `personal-intelligence-system`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 799 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_app()` connect `create_app` to `search.py`, `SourceCatalog`, `ProviderError`, `test_llm.py`, `SourceItem`, `agent.py`, `YouTubeRuntimeJob`, `DailyScheduler`, `Settings`, `llm/core.py`, `admin.py`, `test_gmail_oauth.py`, `ExtractionFlow`, `gmail_runtime.py`, `TelegramDeliveryError`, `add_source`, `SearchFilters`, `Router`, `RetentionJob`, `safe_links`, `source_health.py`, `BudgetTracker`, `run_rss_now`, `RssCollector`, `TelegramBotClient`, `TelegramWebhookHandler`, `test_security_hardening.py`, `database_persistence`, `test_agent_api.py`, `BriefingItem`, `SqlAlchemyLlmRepository`, `email/core.py`, `logging.py`, `load_model_settings`, `test_notifications.py`, `ReembeddingService`, `YouTubeDiscovery`, `NtfyNotifier`, `session.py`, `GmailApiClient`, `main.py`, `Notification`, `database_dispatcher`, `protect_admin_and_add_security_headers`, `test_health.py`?**
  _High betweenness centrality (0.171) - this node is a cross-community bridge._
- **Why does `Settings` connect `Settings` to `protect_admin_and_add_security_headers`, `ValueError`, `test_security_hardening.py`, `create_app`, `agent.py`, `TelegramWebhookHandler`, `test_agent_api.py`, `test_telegram.py`, `TelegramDeliveryError`, `.__init__`, `service.py`, `session.py`, `main.py`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `TelegramWebhookHandler` connect `TelegramWebhookHandler` to `TelegramBotClient`, `test_telegram.py`, `create_app`, `agent.py`, `Settings`, `TelegramDeliveryError`, `.__init__`, `SearchFilters`, `service.py`, `main.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `create_app()` (e.g. with `BriefingItem` and `SourceControlError`) actually correct?**
  _`create_app()` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Settings` (e.g. with `_guard()` and `knowledge_search()`) actually correct?**
  _`Settings` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `Router` (e.g. with `edit_compact()` and `classify_unknown()`) actually correct?**
  _`Router` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SourceItem` (e.g. with `ConditionalFeedResult` and `RssCollector`) actually correct?**
  _`SourceItem` has 19 INFERRED edges - model-reasoned connections that need verification._