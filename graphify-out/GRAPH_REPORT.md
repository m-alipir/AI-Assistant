# Graph Report - AI-Assistant  (2026-09-20)

## Corpus Check
- 204 files · ~127,337 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 4, .example 2, .xml 2)

## Summary
- 3015 nodes · 6746 edges · 194 communities (136 shown, 58 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 963 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6ed822a7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- InMemoryKnowledgeRepository
- test_rss_runtime.py
- ProviderError
- test_llm.py
- test_telegram.py
- SourceItem
- create_app
- agent.py
- YouTubeRuntimeJob
- DailyScheduler
- Settings
- .complete
- SourceCatalog
- get
- test_gmail_oauth.py
- ExtractionFlow
- contracts.py
- test_youtube.py
- gmail_runtime.py
- TelegramBotClient
- datetime
- rss.py
- runtime_sources.py
- test_search.py
- service.py
- gmail_api.py
- Router
- typing
- legacy_sections
- source_health.py
- BudgetTracker
- rss_runtime.py
- run_rss_now
- load_source_catalog
- Project Progress — Source of Truth
- TelegramWebhookHandler
- .enabled_source_requires_http_url
- test_secret_file_precedes_environment_value_without_rendering_it
- database_persistence
- test_agent_api.py
- admin.py
- Usage
- email/core.py
- test_security_hardening.py
- main.py
- notifications/core.py
- test_poller_reuses_handler_and_advances_cursor_after_safe_skips
- Request
- EmailMessage
- reembedding.py
- FeedFetcher
- .feed_url
- Base
- find_cluster
- test_csv_bulk_urls.py
- .__init__
- FastAPI
- .__init__
- opml.py
- GmailApiClient
- test_source_export.py
- record_briefing_feedback
- HttpFeedFetcher
- Architecture Decision Log
- database_dispatcher
- SourcePackService
- Data Model
- protect_admin_and_add_security_headers
- env.py
- test_admin.py
- test_durable_outbox_is_locked_and_deleted_only_with_briefing_persistence
- SourceRepository
- ai-personal-assistant-open-source-research.md
- ._normalize_entry
- .__init__
- post
- .normalize_to_utc
- 2. Data ingestion / web / news
- source_repository.py
- SchedulerPreference
- alembic
- search.py
- ManagedSourceCreate
- What You Must Do When Invoked
- Verification
- source_pack.py
- sqlalchemy
- 15. Full personal-assistant repos — dependency değil, architecture mine
- 4. Mobile app / sync / offline-first
- ._secret_or_file
- test_telegram_source_failures_have_concise_turkish_messages
- knowledge_search
- Open-Source Integration Plan
- ._normalize_entry
- SearchFilters
- 7. External apps / tools / actions
- backup-postgres.sh
- restore-postgres.sh
- Model Routing and Cost Policy
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
- 5. Task app / Calendar / interoperability
- Architecture
- Product Specification
- Security and Privacy
- 23. Kaynak repos
- 8. Notifications
- Interest Learning
- 12. Background jobs / queues / durable execution
- Pipelines
- AGENTS.md — Personal Intelligence System
- KnowledgeSearchError
- graphify reference: extra exports and benchmark
- Research Notes (checked 2026-09-06)
- Caveat olanlar
- Phase 1 — “Hazır değeri al”
- Read-only Agent API
- Agent Handoff — 2026-09-08
- Optimization Baseline and Acceptance Gates
- test_control_center_memory_detail_handles_result_missing_and_unavailable
- test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap
- 3.1 Docling
- Codex Master Prompt
- Gece Çalışma Planı — Production Öncesi Sertleştirme
- Telegram bot interface
- 10.1 Mem0
- 13.2 promptfoo
- graphify reference: query, path, explain
- Production VPS deployment
- 16. Automation platforms — dikkatli kullan
- update_source
- interests
- ProviderCallCoordinator
- .handle
- RSSHub credential-free pilot
- Q: Use the Graphify knowledge graph to explain the main architecture of this project. Do not inspect the whole codebase manually unless the graph is insufficient.
- test_control_center_memory_search_reuses_retrieval_and_ask_callbacks
- LangGraph
- Pipecat
- Phase 2 — Data quality
- briefing_feedback
- .__init__
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- Encrypted PostgreSQL backup and restore
- test_control_center_briefings_handle_empty_and_unavailable_history
- FakeSourceRepository
- .validate_production_security
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- .allowed_host_list
- BACKUP-RESTORE.md
- extraction-spec.md
- NTFY.md
- promptfoo/README.md
- evals/README.md
- START_HERE.md

## God Nodes (most connected - your core abstractions)
1. `create_app()` - 163 edges
2. `Settings` - 63 edges
3. `ManagedSourceCreate` - 60 edges
4. `SourceRepository` - 53 edges
5. `Router` - 51 edges
6. `SourceItem` - 48 edges
7. `SourceCatalog` - 47 edges
8. `database_persistence()` - 41 edges
9. `OpenRouterClient` - 40 edges
10. `ProviderError` - 40 edges

## Surprising Connections (you probably didn't know these)
- `Operational` --references--> `briefings()`  [INFERRED]
  docs/DATA_MODEL.md → app/api/admin.py
- `D016 — Separate agent orchestration and coding trust zones` --references--> `briefings()`  [INFERRED]
  docs/DECISIONS.md → app/api/admin.py
- `Operations and recovery` --references--> `config()`  [INFERRED]
  docs/VPS_DEPLOYMENT.md → app/api/admin.py
- `CSV` --references--> `ManagedSourceCreate`  [INFERRED]
  docs/CSV_AND_BULK_URLS.md → app/config/source_repository.py
- `Last work log` --references--> `HybridRetriever`  [INFERRED]
  docs/PROGRESS.md → app/knowledge/repository.py

## Import Cycles
- None detected.

## Communities (194 total, 58 thin omitted)

### Community 0 - "InMemoryKnowledgeRepository"
Cohesion: 0.13
Nodes (23): HybridRetriever, InMemoryKnowledgeRepository, _normal(), datetime, Small in-memory M3 repository and deterministic hybrid retrieval service., Offline repository fake used by M3 acceptance tests before job wiring is…, Apply raw-content retention without deleting distilled event/provenance records., Structured filtering then deterministic lexical/vector scoring over the… (+15 more)

### Community 1 - "test_rss_runtime.py"
Cohesion: 0.05
Nodes (26): ArticleContent, GatekeeperResult, FakeFlow, FakeSourceRepository, FixtureFetcher, asyncio, test_duplicate_rss_item_never_fetches_article_body(), test_explicit_rss_retry_bypasses_only_its_post_llm_block() (+18 more)

### Community 2 - "ProviderError"
Cohesion: 0.09
Nodes (20): ArticleFetcher, _extract_html(), Fetch public HTML with redirect-by-redirect validation and response bounds., Parse already-fetched HTML only; parsing never initiates another network…, _visible_html_text(), _VisibleText, ProviderError, RuntimeError (+12 more)

### Community 3 - "test_llm.py"
Cohesion: 0.13
Nodes (25): InMemoryResultCache, OpenRouterClient, AsyncBaseTransport, Small direct HTTP client with bounded retries and no payload logging., Validated-result cache keyed by all fields required by the cost policy., Create an opaque stable cache key from the mandatory components., LogCaptureFixture, priced_settings() (+17 more)

### Community 4 - "test_telegram.py"
Cohesion: 0.07
Nodes (27): TestClient, _callback_handler(), _callback_payload(), _client(), _FeedbackStore, _handler(), _MappingResult, _payload() (+19 more)

### Community 5 - "SourceItem"
Cohesion: 0.07
Nodes (45): InMemoryDedupCache, Idempotent in-process identity cache for the deterministic ingestion stage., Return true once for a unique item and false for subsequent equivalent items., Reserve external-ID, canonical-URL, and content-hash identities in priority…, assess_freshness(), Freshness classification before article extraction or model work., Classify an item using published time, or discovered time only as a marked…, DeterministicIngestionPipeline (+37 more)

### Community 6 - "create_app"
Cohesion: 0.07
Nodes (22): create_app(), agent_list_briefings(), gmail_accounts(), store_gmail_token(), telegram_history(), telegram_set_interest(), _telegram_subject(), Build the API with injectable readiness behavior for isolated unit tests. (+14 more)

### Community 7 - "agent.py"
Cohesion: 0.16
Nodes (20): AgentBriefingDetail, AgentBriefingItem, AgentBriefingPage, AgentBriefingSummary, AgentEmailAction, AgentKnowledgeResponse, AgentSearchEvent, _compact() (+12 more)

### Community 8 - "YouTubeRuntimeJob"
Cohesion: 0.10
Nodes (25): Discover recent public channel uploads through YouTube's Atom channel feed., YouTubeDiscovery, One public YouTube channel discovered through its Atom feed., YouTubeSourceConfig, Apply freshness/dedup/captions before existing gatekeeper and extractor calls., YouTubeRuntimeJob, catalog(), FakeFlow (+17 more)

### Community 9 - "DailyScheduler"
Cohesion: 0.08
Nodes (25): DailyScheduler, datetime, Persist only aggregate operational counts, never source or provider payloads., Process-local non-blocking guard shared by manual and scheduled operations., Run once or return a safe skip rather than queueing concurrent expensive work., One daily opt-in job; durable claiming prevents restart double-runs., Apply a persisted operator choice without interrupting an active run., RuntimeRunCoordinator (+17 more)

### Community 10 - "Settings"
Cohesion: 0.11
Nodes (16): field_validator, Validated settings loaded from environment variables or a local ``.env`` file., Parse explicit user/chat pairs, avoiding an accidental cross-product allow-list., Supply known secret values to log redaction without exposing them elsewhere., Settings, BaseSettings, pytest, test_agent_api_fails_closed_when_enabled_without_a_strong_dedicated_token() (+8 more)

### Community 11 - ".complete"
Cohesion: 0.08
Nodes (19): main(), Print eligible model IDs from the provider catalog using an explicit…, advisory_candidates(), EmbeddingResponse, OpenRouterResponse, _provider_cost(), Any, Response (+11 more)

### Community 12 - "SourceCatalog"
Cohesion: 0.06
Nodes (47): Collect RSS/Atom metadata only; article-body fetching is deliberately out of…, RssCollector, The complete seedable RSS and YouTube source catalog., Expose configured defaults directly to the freshness-first pipeline., SourceCatalog, check_database_ready(), create_engine(), create_session_factory() (+39 more)

### Community 13 - "get"
Cohesion: 0.13
Nodes (24): briefings(), control_center_briefing_detail_page(), control_center_briefings_page(), control_center_search_detail_page(), control_center_search_page(), _export(), export_csv(), export_opml() (+16 more)

### Community 14 - "test_gmail_oauth.py"
Cohesion: 0.10
Nodes (22): classify_token_endpoint_error(), GmailOAuth, OAuthFlowError, Exception, OAuthErrorCategory, Bounded Google OAuth code flow; secrets are never logged or returned., A safe, user-actionable OAuth failure with no provider payload., Map only Google's non-secret ``error`` code to a safe diagnostic category. (+14 more)

### Community 15 - "ExtractionFlow"
Cohesion: 0.08
Nodes (26): _bounded_metadata_prompt(), _bounded_untrusted_json(), ExtractedClaim, ExtractionFlow, ExtractorResult, _grounded_claims(), model_validator, Accept harmless omissions/aliases without inventing source facts or retrying a… (+18 more)

### Community 16 - "contracts.py"
Cohesion: 0.12
Nodes (23): CollectorProvider, ExternalItem, LlmProvider, LlmRequest, LlmResponse, BaseModel, Protocol, Narrow, testable contracts for network-backed providers. (+15 more)

### Community 17 - "test_youtube.py"
Cohesion: 0.08
Nodes (25): _matches_language(), parse_webvtt(), yt-dlp wrapper that downloads selected VTT captions but never media or audio., Run blocking yt-dlp work off the event loop and enforce a total timeout., Prefer configured language, then Turkish/English, before another available…, Keep legacy requests unchanged, but request only the configured language family., Parse standard WebVTT cues while keeping their source timings intact., Convert ``HH:MM:SS.mmm`` or ``MM:SS.mmm`` VTT timestamps to seconds. (+17 more)

### Community 18 - "gmail_runtime.py"
Cohesion: 0.14
Nodes (23): GmailBatch, GmailAccountRecord, GmailRuntimeJob, Gmail job wiring that keeps credentials and message bodies outside…, Run bounded account syncs independently so a Gmail failure cannot stop RSS., message(), asyncio, datetime (+15 more)

### Community 19 - "TelegramBotClient"
Cohesion: 0.06
Nodes (31): get_settings(), Return the process-wide settings instance., main(), Explicit VDS-only webhook setup; it never runs during application startup., RuntimeError, Disable a prior webhook without discarding queued Telegram updates., Receive one bounded long-poll batch without retaining provider response bodies., Safe outbound error category; provider details must never leave the client. (+23 more)

### Community 20 - "datetime"
Cohesion: 0.08
Nodes (37): CorrelationPolicy, CorrelationResult, MemoryEvent, BaseModel, M4 deterministic escalation and compact, evidence-bound correlation records., Model boundary: relation remains an inference with explicit event/claim…, Use a strong reasoner only for meaningful, already-narrowed candidates., Keep only top relevant historical memories; never send the whole event store. (+29 more)

### Community 21 - "rss.py"
Cohesion: 0.12
Nodes (20): Safe, Turkish-first presentation models for persisted briefings., Bounded RSS/Atom collection and compact item normalization., YouTube channel discovery and caption-only transcript support., _ignore_post_llm_failure(), _ignore_refresh_blocked_item(), Caption-first YouTube runtime built from the existing public Atom and yt-dlp…, Keep standalone/offline jobs side-effect free when no durable guard is supplied., Keep standalone/offline jobs side-effect free when no durable guard is supplied. (+12 more)

### Community 22 - "runtime_sources.py"
Cohesion: 0.10
Nodes (28): add_source(), disable_source(), list_sources(), _load_catalog(), _load_data(), _looks_like_youtube(), Any, Path (+20 more)

### Community 23 - "test_search.py"
Cohesion: 0.16
Nodes (26): answer_question(), KnowledgeSearchService, Answer only from bounded retained candidates; no candidates means no model…, Searchable Gmail record: no subject, sender, body, or token is retained here., Apply deterministic date/metadata narrowing then the existing hybrid ranker., SafeEmailResult, event(), asyncio (+18 more)

### Community 24 - "service.py"
Cohesion: 0.10
Nodes (23): Preserve only absolute HTTP(S) provenance links in the presentation layer., safe_links(), feedback_keyboard(), Build fixed actions; server-side token lookup supplies the event and actor…, _actor_for(), _briefing_item_text(), _callback_answer_text(), _command() (+15 more)

### Community 25 - "gmail_api.py"
Cohesion: 0.17
Nodes (15): _deduplicated(), GmailApiError, _json_mapping(), _message_ids(), _optional_string(), Any, datetime, Exception (+7 more)

### Community 26 - "Router"
Cohesion: 0.14
Nodes (16): LlmError, ProviderBusy, datetime, RuntimeError, Configuration-driven fallback router with cache, strict validation, and…, Account for every provider/cache attempt without retaining request/response…, Return cached or provider-validated structured data with safe fallback behavior., Safe LLM boundary failure that never contains request content or credentials. (+8 more)

### Community 27 - "typing"
Cohesion: 0.16
Nodes (8): Any, datetime, Bounded, opt-in PostgreSQL retention maintenance., Expire raw public content and old operational metadata without deleting…, Run maintenance immediately and periodically without provider work., RetentionJob, RetentionScheduler, typing

### Community 28 - "legacy_sections"
Cohesion: 0.09
Nodes (25): briefing_detail(), _control_center_briefing(), _control_center_briefing_history(), _control_center_briefing_view(), _control_center_search_event(), _control_center_search_event_view(), Render persisted, bounded briefing data; viewing never invokes a model., Build a bounded, escaped-template-ready view of one persisted briefing. (+17 more)

### Community 29 - "source_health.py"
Cohesion: 0.13
Nodes (19): classify_fetch_failure(), database_source_health(), failure(), FetchFailure, HealthDecision, next_retry_at(), async_sessionmaker, AsyncSession (+11 more)

### Community 30 - "BudgetTracker"
Cohesion: 0.10
Nodes (25): BudgetExceeded, BudgetPolicy, BudgetTracker, ModelSettings, OpenRouterConfig, BaseModel, Return configured primary then ordered configured fallbacks., Daily spending guardrails; email action work may use its reserved allowance. (+17 more)

### Community 31 - "rss_runtime.py"
Cohesion: 0.07
Nodes (40): BriefingItem, build_sections(), edit_compact(), EditedBriefing, BaseModel, Deterministic M6 briefing queues and local preview., Edit only a bounded, distilled briefing; empty briefings never reach this…, _render_item() (+32 more)

### Community 32 - "run_rss_now"
Cohesion: 0.07
Nodes (41): load_model_settings(), Path, Load role mappings, fallbacks, and budget limits from safe YAML., LlmResultCache, Validated structured result keyed by opaque digest, without input or raw…, claim_blocked_item(), correlate_event(), has_pending_briefing() (+33 more)

### Community 33 - "load_source_catalog"
Cohesion: 0.29
Nodes (6): load_source_catalog(), Path, Load a YAML source catalog without accepting executable YAML constructs., lifespan(), test_source_seed_loader_accepts_disabled_placeholders_and_rejects_enabled_invalid_sources(), test_rsshub_pilot_is_separate_and_contains_only_approved_routes()

### Community 34 - "Project Progress — Source of Truth"
Cohesion: 0.05
Nodes (39): Approved implementation sequence after M19, Backlog / explicitly out of current track, Blockers, Last work log, M0 — Foundation / runnable skeleton, M10 — Gmail runtime integration, M11 — YouTube daily runtime integration, M12 — Safe daily briefing operations (+31 more)

### Community 35 - "TelegramWebhookHandler"
Cohesion: 0.17
Nodes (11): Split at a readable boundary while preserving literal, non-formatted text., split_plain_text(), TelegramMessage, Actor, _hash(), Exception, Keep Telegram untrusted until secret verification and actor-pair authorization…, Run the canonical command/feedback boundary for webhook and polling transports. (+3 more)

### Community 36 - ".enabled_source_requires_http_url"
Cohesion: 0.40
Nodes (3): model_validator, Permit disabled placeholders while keeping source configuration non-secret., Reject example placeholders only when the source is switched on.

### Community 38 - "database_persistence"
Cohesion: 0.11
Nodes (23): correlation_content_hash(), Produce a deterministic cache key without including raw source content., database_persistence(), reasoner(), async_sessionmaker, AsyncSession, datetime, IsPostLlmFailed (+15 more)

### Community 39 - "test_agent_api.py"
Cohesion: 0.20
Nodes (16): _app(), _briefing(), _headers(), Offline contract and privacy regressions for the separate read-only Agent API., test_agent_api_briefing_pagination_is_bounded(), test_agent_api_enforces_request_size_and_rate_limit(), test_agent_api_is_disabled_by_default_and_token_is_separate_from_admin(), test_agent_api_limits_failed_auth_before_unbounded_audit_writes() (+8 more)

### Community 40 - "admin.py"
Cohesion: 0.11
Nodes (23): delete_source(), _display_section(), gmail_connect(), _interest_profiles(), _json_strings(), _load_briefing_sections(), Local-only operational API plus a small server-rendered admin UI., Join only briefed event provenance and compact claims, never raw source/email… (+15 more)

### Community 41 - "Usage"
Cohesion: 0.09
Nodes (13): Non-sensitive usage/cost metadata retained for operational accounting., Return safe per-role request metadata, separating provider work from cache hits., Usage, usage_breakdown(), DailySpend, InMemoryLlmRepository, LlmRepository, datetime (+5 more)

### Community 42 - "email/core.py"
Cohesion: 0.17
Nodes (12): InMemoryGmailSync, datetime, Bounded, read-only email classification without live Gmail access in tests., Independent account checkpoints and bounded initial/recovery sync for fixture…, Encrypt OAuth refresh tokens with authenticated Fernet encryption., TokenCipher, message(), datetime (+4 more)

### Community 43 - "test_security_hardening.py"
Cohesion: 0.07
Nodes (36): Response, Reject non-web and private-network targets before every outbound feed request., Fail closed when the actual connected peer is unavailable or non-public., _validate_connected_peer(), _validate_remote_url(), bind_request_id(), configure_logging(), JsonFormatter (+28 more)

### Community 44 - "main.py"
Cohesion: 0.08
Nodes (30): Safe, bounded public article fetch and offline HTML extraction boundary., Configuration loader for model-role mappings; business services never select…, Environment-backed runtime settings., Async SQLAlchemy engine lifecycle and readiness checks., Opt-in daily scheduler with durable per-day claims., Advisory OpenRouter catalog command; it never rewrites configuration., Direct OpenRouter client, strict structured outputs, cache, and budget-aware…, Async repository boundary for non-sensitive LLM cache and accounting data. (+22 more)

### Community 45 - "notifications/core.py"
Cohesion: 0.09
Nodes (29): deliver_run_notifications(), DeliveryResult, Notification, notification_key(), NotificationDispatcher, NotificationError, NotificationKind, BaseModel (+21 more)

### Community 46 - "test_poller_reuses_handler_and_advances_cursor_after_safe_skips"
Cohesion: 0.16
Nodes (8): asyncio, test_callback_answer_retries_transient_failure_and_bounds_timeout(), test_poller_reuses_handler_and_advances_cursor_after_safe_skips(), test_polling_client_deletes_webhook_and_requests_bounded_updates(), poll_transport(), test_telegram_client_rejects_provider_error_without_exposing_body(), test_telegram_client_retries_only_safe_transient_failures_and_never_uses_markup(), transport()

### Community 47 - "Request"
Cohesion: 0.15
Nodes (25): _admin_sources(), config(), _control_center_context(), control_center_page(), _control_center_scheduler_context(), control_center_scheduler_page(), _dashboard_context(), _database_details() (+17 more)

### Community 48 - "EmailMessage"
Cohesion: 0.18
Nodes (14): classify(), classify_unknown(), EmailClassification, EmailMessage, GmailAccount, BaseModel, Use the configured cheap role only after deterministic rules leave a message…, Deterministic sender/subject rules run before any optional cheap-model fallback. (+6 more)

### Community 49 - "reembedding.py"
Cohesion: 0.16
Nodes (13): Explicit, bounded re-embedding orchestration; never runs automatically at…, Re-embed only missing or incompatible compact retained records in small batches., ReembeddingRecord, ReembeddingService, EmbeddingResult, Cached, model-bound embedding result; vectors never come from a chat model., Embed, FetchRecords (+5 more)

### Community 50 - "FeedFetcher"
Cohesion: 0.17
Nodes (7): FeedFetcher, Protocol, Fetch a feed payload with an explicit response-size bound., Return one RSS or Atom XML payload., FixtureFeedFetcher, asyncio, test_youtube_discovery_uses_public_atom_metadata_without_media_download()

### Community 52 - "Base"
Cohesion: 0.11
Nodes (24): AgentApiAuditRow, Metadata-only audit records for the separate read-only Agent API., Never stores caller identity, token, question, source content, or response…, Base, Shared SQLAlchemy declarative metadata., Base class for persisted models introduced in later milestones., EmailClassificationRow, GmailAccountRow (+16 more)

### Community 53 - "find_cluster"
Cohesion: 0.27
Nodes (12): ClusterCandidate, ClusterMatch, find_cluster(), _normal(), _overlap(), datetime, timedelta, Conservative deterministic clustering for distinct sources covering one public… (+4 more)

### Community 54 - "test_csv_bulk_urls.py"
Cohesion: 0.12
Nodes (27): _csv_result(), CsvImportError, CsvImportService, CsvLimitExceeded, InvalidCsvStructure, MalformedCsv, parse_source_csv(), ValueError (+19 more)

### Community 55 - ".__init__"
Cohesion: 0.11
Nodes (15): AddSourceCallback, ProcessRateLimiter, Bound requests per opaque caller key without retaining an address or credential., async_sessionmaker, AsyncSession, BriefingCallback, DisableSourceCallback, HistoryCallback (+7 more)

### Community 56 - "FastAPI"
Cohesion: 0.12
Nodes (17): health(), HealthResponse, BaseModel, get, Request, Response, Liveness and dependency-readiness endpoints., Small health payload with no configuration or secret information. (+9 more)

### Community 57 - ".__init__"
Cohesion: 0.17
Nodes (10): Protocol, Return available manually authored and automatic VTT caption tracks., Download subtitle files only, with video/audio downloads disabled., SubtitleFetcher, datetime, IsPostLlmFailed, KnownItem, PersistEvent (+2 more)

### Community 58 - "opml.py"
Cohesion: 0.12
Nodes (26): InvalidOpmlStructure, _local_name(), MalformedOpml, _opml_result(), _opml_title(), OpmlError, OpmlLimitExceeded, OpmlService (+18 more)

### Community 59 - "GmailApiClient"
Cohesion: 0.25
Nodes (11): GmailApiClient, AsyncBaseTransport, Bounded Gmail metadata collector with retry and history-based incremental sync., asyncio, response(), test_expired_history_uses_bounded_recovery_sync(), handler(), test_incremental_history_sync_avoids_initial_mailbox_query() (+3 more)

### Community 60 - "test_source_export.py"
Cohesion: 0.10
Nodes (22): _csv_row(), RuntimeError, Deterministic read-only exports of database-managed sources., The managed-source catalog could not be read for an export., Render repository rows without modifying their persisted state., Use canonical endpoint and every Source Pack-supported persisted field., Keep only CSV-import-supported metadata; CSV imports always disable sources., _source_pack_row() (+14 more)

### Community 61 - "record_briefing_feedback"
Cohesion: 0.27
Nodes (9): _display_section(), FeedbackConnection, FeedbackResult, _json_strings(), datetime, Protocol, Shared, transaction-safe briefing feedback boundary for every user interface., Record one allowed signal without allowing a UI to alter ranking rules directly. (+1 more)

### Community 62 - "HttpFeedFetcher"
Cohesion: 0.20
Nodes (8): HttpFeedFetcher, Fetch with explicit redirect validation so a feed cannot pivot into private…, Small HTTP client with timeout, bounded retry, and a payload-size limit., Fetch a feed without logging URL query values or untrusted response content., _find_blocked_youtube_item(), datetime, Recover metadata for a legacy block only during the user's explicit retry…, Timeout

### Community 63 - "Architecture Decision Log"
Cohesion: 0.06
Nodes (31): Architecture Decision Log, D001 — Code-first runtime, no n8n core, D002 — Supabase/PostgreSQL + pgvector before Qdrant, D003 — Hierarchical taxonomy + normalized entities, not literal folders, D004 — Facts/claims separate from inference, D005 — Freshness gate before LLM, D006 — Personalized and global-news streams remain separate, D007 — Slow adaptive interests (+23 more)

### Community 64 - "database_dispatcher"
Cohesion: 0.18
Nodes (7): database_dispatcher(), async_sessionmaker, AsyncSession, Persist per-channel delivery state and permit safe retries of failed logical…, ClaimDelivery, RecordDelivery, SendNotification

### Community 65 - "SourcePackService"
Cohesion: 0.11
Nodes (19): _bulk_result(), BulkUrlError, BulkUrlLimitExceeded, InvalidBulkUrlStructure, parse_bulk_urls(), ValueError, Bounded pasted-URL parsing backed by the shared managed-source batch service., Base class for safe pasted-URL input failures. (+11 more)

### Community 66 - "Data Model"
Cohesion: 0.07
Nodes (28): `applications` (optional but included in V1 if email classification supports it cleanly), `categories`, `claims`, Core ingestion, Data Model, `email_classifications`, Email state, Embeddings (+20 more)

### Community 67 - "protect_admin_and_add_security_headers"
Cohesion: 0.32
Nodes (7): _admin_credentials_valid(), protect_admin_and_add_security_headers(), Request, Verify Basic credentials without retaining or logging either supplied value., Require the configured origin, plus the explicitly supported localhost SSH…, _request_is_https(), _same_admin_origin()

### Community 68 - "env.py"
Cohesion: 0.17
Nodes (12): app_db, app_knowledge, Connection, logging_config, do_run_migrations(), Alembic environment for asynchronous PostgreSQL migrations., Generate SQL without opening a database connection., Run migrations against an existing synchronous connection. (+4 more)

### Community 69 - "test_admin.py"
Cohesion: 0.11
Nodes (18): FakeSourceRepository, Path, _source_row(), test_admin_source_crud_uses_repository_and_never_mutates_yaml(), test_admin_source_failures_map_to_deterministic_http_errors(), test_config_and_interest_override_use_configured_temp_paths(), test_control_center_briefing_view_converts_only_timezone_aware_timestamps(), test_control_center_dashboard_is_narrow_and_never_exposes_environment_values() (+10 more)

### Community 71 - "SourceRepository"
Cohesion: 0.09
Nodes (13): async_sessionmaker, AsyncSession, Explicitly seed a pristine database once; existing rows are never changed., Claim the explicit lifecycle or mark pre-existing database sources complete., Load runtime sources exclusively from the database., Persist bounded exponential cooldown without retaining provider/source payloads., SourceRepository, Bulk URLs (+5 more)

### Community 72 - "ai-personal-assistant-open-source-research.md"
Cohesion: 0.08
Nodes (25): 0. Kısa sonuç, 19. Özellikle EKLEMEM dediğim şeyler, 1. Önerilen hedef mimari, 20. Shortlist — Codex'e analiz ettirilecek repos, 21. Codex için repo-evaluation checklist, 22. Net final architecture recommendation, 6. Mobile API client generation, 9. LLM gateway / model management (+17 more)

### Community 73 - "._normalize_entry"
Cohesion: 0.18
Nodes (10): Any, datetime, Path, Use yt-dlp's library API in a temporary directory to retain captions only., Canonicalize only known public YouTube video URLs before invoking yt-dlp., Read only yt-dlp-created VTT subtitle files from the private temporary…, Collect video metadata without downloading video or audio., _requested_subtitle_tracks() (+2 more)

### Community 74 - ".__init__"
Cohesion: 0.29
Nodes (6): datetime, DecryptToken, FetchAccount, KnownMessage, PersistClassification, UpdateCheckpoint

### Community 75 - "post"
Cohesion: 0.16
Nodes (27): add_source(), BulkUrlUpload, create_source(), CsvUpload, import_bulk_urls(), import_csv(), import_opml(), import_source_pack() (+19 more)

### Community 76 - ".normalize_to_utc"
Cohesion: 0.33
Nodes (4): datetime, field_validator, Normalize source dates at the model boundary and reject naïve timestamps., Use publication time when available; discovery time is an explicit fallback.

### Community 77 - "2. Data ingestion / web / news"
Cohesion: 0.08
Nodes (25): 2.1 RSSHub, 2.2 Trafilatura, 2.3 youtube-transcript-api, 2.4 Scrapling, 2.5 Crawl4AI, 2.6 Newspaper4k, 2.7 news-please, 2.8 SearXNG (+17 more)

### Community 78 - "source_repository.py"
Cohesion: 0.08
Nodes (38): canonicalize_endpoint(), EnabledSourceDeleteBlocked, ManagedSourceUpdate, model_validator, RuntimeError, Canonical database-managed sources with a one-time YAML bootstrap path., Return the stable endpoint identity used by the database uniqueness constraint., Base class for safe managed-source repository failures. (+30 more)

### Community 79 - "SchedulerPreference"
Cohesion: 0.12
Nodes (16): OnboardingRepository, async_sessionmaker, AsyncSession, BaseModel, field_validator, Small persisted preferences owned by the Control Center onboarding flow., SchedulerPreference, FakeOnboardingRepository (+8 more)

### Community 80 - "alembic"
Cohesion: 0.11
Nodes (5): alembic, downgrade(), Enable pgvector in the development PostgreSQL image., Remove pgvector only when explicitly downgrading an otherwise empty foundation., upgrade()

### Community 81 - "search.py"
Cohesion: 0.13
Nodes (22): _asks_for_email(), _database_error_category(), fetch_sql_candidates(), fetch_sql_event(), _json_list(), AsyncEngine, Exception, Bounded, provenance-first user search over retained event and email metadata. (+14 more)

### Community 82 - "ManagedSourceCreate"
Cohesion: 0.14
Nodes (15): ManagedSourceCreate, BaseModel, field_validator, Validated metadata accepted at the managed-source persistence boundary., telegram_add_source(), _source_create(), _row(), PackRepository (+7 more)

### Community 83 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 84 - "Verification"
Cohesion: 0.08
Nodes (24): Database Schema, Do Not Break, Goal, Important Files, Latest clean baseline, Managed Sources Handoff, Next Recommended Step, Resume Here (+16 more)

### Community 85 - "source_pack.py"
Cohesion: 0.16
Nodes (21): InvalidSourcePackStructure, MalformedSourcePack, _normalized_optional_text(), parse_source_pack(), parse_source_record(), ParsedSource, _priority(), ValueError (+13 more)

### Community 87 - "15. Full personal-assistant repos — dependency değil, architecture mine"
Cohesion: 0.10
Nodes (21): 15.1 Khoj, 15.2 ORDERLY, 15.3 Leon, 15.4 Morning Deck, 15.5 Folo, 15.6 AppFlowy, 15.7 Heatwire, 15. Full personal-assistant repos — dependency değil, architecture mine (+13 more)

### Community 93 - "4. Mobile app / sync / offline-first"
Cohesion: 0.10
Nodes (20): 4.1 RxDB, 4.2 Electric, 4.3 PowerSync, 4.4 Supabase, 4.5 Appwrite, 4. Mobile app / sync / offline-first, Ama, Artıları (+12 more)

### Community 94 - "._secret_or_file"
Cohesion: 0.10
Nodes (10): Path, Return the normalized SQLAlchemy connection URL without exposing it in logs., Return the OAuth secret from an environment value or mounted secret file., Return the Fernet key without ever rendering it in diagnostics., Return the OpenRouter credential from an environment value or secret file., Return the dedicated Agent API secret only for constant-time request…, Return the admin password only for constant-time request verification., Return the ntfy publishing token only when constructing its outbound request. (+2 more)

### Community 98 - "test_telegram_source_failures_have_concise_turkish_messages"
Cohesion: 0.12
Nodes (7): _managed_source_row(), _SourceRepository, test_telegram_control_commands_reuse_injected_runtime_callbacks(), add_source(), set_interest(), sources(), test_telegram_source_failures_have_concise_turkish_messages()

### Community 101 - "knowledge_search"
Cohesion: 0.27
Nodes (16): _audit(), _bounded_request_body(), briefing_detail(), _guard(), knowledge_search(), latest_briefing(), list_briefings(), get (+8 more)

### Community 102 - "Open-Source Integration Plan"
Cohesion: 0.12
Nodes (16): Deferred and rejected-for-now projects, Execution gates, Open-Source Integration Plan, promptfoo, Purpose, Required pre-integration checklist, RSSHub, Stage 0 — Operational truth and project-state cleanup (+8 more)

### Community 104 - "._normalize_entry"
Cohesion: 0.20
Nodes (10): _author(), ConditionalFeedResult, _entry_text(), _external_id(), Any, datetime, Fetch and normalize source entries into compact candidate items., Choose compact feed-provided summary text without fetching the linked article. (+2 more)

### Community 105 - "SearchFilters"
Cohesion: 0.20
Nodes (12): AskSynthesis, _bounded_context(), _matches_metadata(), BaseModel, Use a query vector only after deterministic candidates exist on compatible rows., Deterministic limits applied before candidate ranking or optional model use., Serialize only compact source-backed fields under the role-configured ceiling., Optional reasoner result, visibly separate from source-backed claims. (+4 more)

### Community 106 - "7. External apps / tools / actions"
Cohesion: 0.14
Nodes (14): 7.1 Model Context Protocol — MCP Servers, 7.2 Activepieces, 7.3 Composio, 7.4 Nango, 7. External apps / tools / actions, Ancak, Bizde kullanım, Bizde neden ilginç? (+6 more)

### Community 110 - "Model Routing and Cost Policy"
Cohesion: 0.15
Nodes (12): Application-level result cache, Budget policy, Editor, Embedding, Extractor, Gatekeeper, Model catalog helper, Model Routing and Cost Policy (+4 more)

### Community 133 - "5. Task app / Calendar / interoperability"
Cohesion: 0.17
Nodes (12): 5.2 Radicale, 5.3 Nextcloud Tasks, 5.4 Tasks.org, 5. Task app / Calendar / interoperability, Büyük avantaj, Karar, Karar, Ne zaman mantıklı? (+4 more)

### Community 134 - "Architecture"
Cohesion: 0.17
Nodes (11): 1. High-level flow, 2. Runtime model, 3. Service modules, 4. Deployment, 5. Idempotency, 6. Retrieval strategy, 7. Event-centric storage, 8. Future agent integration boundary (+3 more)

### Community 135 - "Product Specification"
Cohesion: 0.17
Nodes (11): 1. Product goal, 2. Primary input streams, 3. Briefing output, 4. Freshness requirements, 5. Interest behavior, 6. Knowledge organization, 7. Non-goals for V1, Gmail (+3 more)

### Community 136 - "Security and Privacy"
Cohesion: 0.17
Nodes (11): Admin and browser access, Future agent and coding-worker boundary, Gmail, LLM privacy boundary, Network/runtime, Safe operational diagnostics, Secrets, Security and Privacy (+3 more)

### Community 137 - "23. Kaynak repos"
Cohesion: 0.18
Nodes (11): 23. Kaynak repos, AI / memory / orchestration, Files / RAG, Full assistant / UX references, Ingestion / web, Notifications, Observability / testing, Sync / mobile (+3 more)

### Community 138 - "8. Notifications"
Cohesion: 0.18
Nodes (11): 8.1 ntfy, 8.2 Apprise, 8.3 Gotify, 8.4 Novu, 8. Notifications, Bizim için mükemmel intermediate çözüm, Karar, Karar (+3 more)

### Community 139 - "Interest Learning"
Cohesion: 0.18
Nodes (10): 1. Base, 2. Explicit, 3. Adaptive, Effective ranking, Free-form feedback, Goal, Interest Learning, Stability algorithm (initial policy) (+2 more)

### Community 140 - "12. Background jobs / queues / durable execution"
Cohesion: 0.20
Nodes (10): 12.1 PGMQ, 12.2 pg_cron, 12.3 Hatchet, 12.4 Temporal, 12. Background jobs / queues / durable execution, Avantaj, Karar, Karar (+2 more)

### Community 141 - "Pipelines"
Cohesion: 0.20
Nodes (9): A. RSS/news pipeline, B. YouTube pipeline, C. Gmail pipeline, D. Event dedup / clustering, E. Correlation pipeline, F. Daily briefing pipeline, Freshness gate defaults, G. Failure behavior (+1 more)

### Community 142 - "AGENTS.md — Personal Intelligence System"
Cohesion: 0.22
Nodes (8): AGENTS.md — Personal Intelligence System, Definition of done for each milestone, Engineering rules, graphify, Mandatory reading order before implementation, Mission, Non-negotiable product rules, Progress discipline

### Community 143 - "KnowledgeSearchError"
Cohesion: 0.22
Nodes (9): Run bounded user search without accepting or returning raw email/provider…, Return existing deterministic memory retrieval without a provider call., Keep the Admin usable without exposing SQL/provider details to the browser., search_ask(), search_retrieve(), _search_unavailable_response(), KnowledgeSearchError, RuntimeError (+1 more)

### Community 144 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 145 - "Research Notes (checked 2026-09-06)"
Cohesion: 0.22
Nodes (8): Codex / repository guidance, Gmail, Implementation note, OpenRouter, Research Notes (checked 2026-09-06), RSS source examples, Supabase / pgvector, YouTube / yt-dlp

### Community 146 - "Caveat olanlar"
Cohesion: 0.25
Nodes (8): 17. Strict open-source / license caveats, Caveat olanlar, Composio, Crawl4AI, Nango, Open-core projeler, PowerSync, Strict OSS tarafında rahat olduğumuz örnekler

### Community 147 - "Phase 1 — “Hazır değeri al”"
Cohesion: 0.25
Nodes (8): 18. Bizim proje için en mantıklı implementation roadmap, 1. OpenAPI Generator, 2. RSSHub, 3. Trafilatura, 4. youtube-transcript-api, 5. ntfy, 6. Docling, Phase 1 — “Hazır değeri al”

### Community 148 - "Read-only Agent API"
Cohesion: 0.25
Nodes (7): Authentication and limits, Configuration, Hermes HTTP-tool example, HTTP contract, Pre-connection security check, Purpose and trust boundary, Read-only Agent API

### Community 149 - "Agent Handoff — 2026-09-08"
Cohesion: 0.25
Nodes (7): Agent Handoff — 2026-09-08, Important limitations / likely follow-up, Last verified commands, Product/runtime completed so far, Purpose, Sensible next-agent starting sequence, Working rules

### Community 150 - "Optimization Baseline and Acceptance Gates"
Cohesion: 0.25
Nodes (7): Acceptance gates, Baseline scenarios, Delivery sequence, First disposable-database observation, Optimization Baseline and Acceptance Gates, Purpose, Reporting format

### Community 151 - "test_control_center_memory_detail_handles_result_missing_and_unavailable"
Cohesion: 0.29
Nodes (8): test_control_center_briefings_show_saved_and_incomplete_history(), detail(), history(), test_control_center_memory_detail_handles_result_missing_and_unavailable(), detail(), unavailable(), test_search_endpoint_returns_safe_migration_guidance_instead_of_500(), unavailable()

### Community 152 - "test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap"
Cohesion: 0.25
Nodes (3): _Engine, Path, test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap()

### Community 153 - "3.1 Docling"
Cohesion: 0.29
Nodes (7): 3.1 Docling, 3.2 MarkItDown, 3. Document / files / knowledge ingestion, Bizde kullanım, Karar, Karar, Kullanım stratejisi

### Community 154 - "Codex Master Prompt"
Cohesion: 0.29
Nodes (6): Codex Master Prompt, Cost discipline, Existing user projects, Implementation strategy, Initial deliverable, Objective

### Community 155 - "Gece Çalışma Planı — Production Öncesi Sertleştirme"
Cohesion: 0.29
Nodes (6): Bu gece kapsam dışı bırakılan küçük işler, En yüksek etkili maliyet iyileştirmeleri, En yüksek etkili performans/dayanıklılık iyileştirmeleri, Final doğrulama planı, Gece Çalışma Planı — Production Öncesi Sertleştirme, Mevcut durum ve kanıt

### Community 156 - "Telegram bot interface"
Cohesion: 0.29
Nodes (6): Commands, Outbound-only polling deployment, Production configuration, Security and privacy, Telegram bot interface, VDS smoke test

### Community 157 - "10.1 Mem0"
Cohesion: 0.33
Nodes (6): 10.1 Mem0, 10.2 Letta, 10. Memory / personal context, Bizim için önemli nokta, Karar, Karar

### Community 158 - "13.2 promptfoo"
Cohesion: 0.33
Nodes (6): 13.1 Langfuse, 13.2 promptfoo, 13. Observability / evals, Bizde kullanım, Karar, Karar

### Community 159 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 160 - "Production VPS deployment"
Cohesion: 0.33
Nodes (5): Before starting, M17 production verification checklist, Operations and recovery, Production VPS deployment, Start and verify

### Community 161 - "16. Automation platforms — dikkatli kullan"
Cohesion: 0.40
Nodes (5): 16. Automation platforms — dikkatli kullan, Huginn, Karar, Karar, Windmill

### Community 162 - "update_source"
Cohesion: 0.40
Nodes (5): get_source(), Expose only the non-secret managed-source projection used by Admin., _source_view(), update_source(), patch

### Community 163 - "interests"
Cohesion: 0.50
Nodes (4): interests(), Admin API, Schema, Source Packs

### Community 165 - ".handle"
Cohesion: 0.50
Nodes (4): _bounded_body(), Request, Response, Always avoid reflecting provider input; accepted updates are terminally…

### Community 166 - "RSSHub credential-free pilot"
Cohesion: 0.40
Nodes (4): Approved routes, RSSHub credential-free pilot, Run and evaluate, Scope and safety boundary

### Community 167 - "Q: Use the Graphify knowledge graph to explain the main architecture of this project. Do not inspect the whole codebase manually unless the graph is insufficient."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Use the Graphify knowledge graph to explain the main architecture of this project. Do not inspect the whole codebase manually unless the graph is insufficient., Source Nodes

### Community 168 - "test_control_center_memory_search_reuses_retrieval_and_ask_callbacks"
Cohesion: 0.40
Nodes (3): test_control_center_memory_search_reuses_retrieval_and_ask_callbacks(), test_search_endpoint_uses_injected_safe_callback(), ask()

### Community 169 - "LangGraph"
Cohesion: 0.50
Nodes (4): 11. Agent orchestration, Karar, LangGraph, Ne zaman gerek?

### Community 170 - "Pipecat"
Cohesion: 0.50
Nodes (4): 14. Voice — future, Karar, Ne zaman?, Pipecat

### Community 171 - "Phase 2 — Data quality"
Cohesion: 0.50
Nodes (4): 7. Event clustering, 8. promptfoo regression suite, 9. Langfuse, Phase 2 — Data quality

### Community 172 - "briefing_feedback"
Cohesion: 0.50
Nodes (4): briefing_feedback(), BriefingFeedback, Persist an explicit or light feedback signal without changing World ranking., One intentionally small, safe preference signal from a rendered briefing item.

### Community 174 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 175 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 176 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 177 - "Encrypted PostgreSQL backup and restore"
Cohesion: 0.50
Nodes (3): Backup, Encrypted PostgreSQL backup and restore, Isolated restore drill

## Knowledge Gaps
- **414 isolated node(s):** `backup-postgres.sh script`, `restore-postgres.sh script`, `personal-intelligence-system`, `Usage`, `What graphify is for` (+409 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1433 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **58 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_app()` connect `create_app` to `ProviderError`, `test_llm.py`, `SourceItem`, `agent.py`, `YouTubeRuntimeJob`, `DailyScheduler`, `Settings`, `SourceCatalog`, `test_gmail_oauth.py`, `ExtractionFlow`, `gmail_runtime.py`, `TelegramBotClient`, `test_search.py`, `service.py`, `test_control_center_memory_detail_handles_result_missing_and_unavailable`, `Router`, `typing`, `legacy_sections`, `source_health.py`, `BudgetTracker`, `rss_runtime.py`, `run_rss_now`, `load_source_catalog`, `TelegramWebhookHandler`, `ProviderCallCoordinator`, `database_persistence`, `test_agent_api.py`, `test_control_center_memory_search_reuses_retrieval_and_ask_callbacks`, `Usage`, `email/core.py`, `test_security_hardening.py`, `main.py`, `notifications/core.py`, `reembedding.py`, `test_control_center_briefings_handle_empty_and_unavailable_history`, `test_csv_bulk_urls.py`, `.__init__`, `FastAPI`, `opml.py`, `GmailApiClient`, `test_source_export.py`, `HttpFeedFetcher`, `database_dispatcher`, `protect_admin_and_add_security_headers`, `test_admin.py`, `SourceRepository`, `SchedulerPreference`, `search.py`, `ManagedSourceCreate`, `knowledge_search`, `SearchFilters`, `test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `Settings` connect `Settings` to `protect_admin_and_add_security_headers`, `TelegramWebhookHandler`, `knowledge_search`, `create_app`, `agent.py`, `test_agent_api.py`, `test_secret_file_precedes_environment_value_without_rendering_it`, `test_telegram.py`, `test_security_hardening.py`, `main.py`, `SourceCatalog`, `TelegramBotClient`, `.validate_production_security`, `.__init__`, `service.py`, `.allowed_host_list`, `test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap`, `._secret_or_file`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `briefings()` connect `get` to `Data Model`, `create_app`, `admin.py`, `Request`, `Architecture Decision Log`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `create_app()` (e.g. with `BriefingItem` and `Settings`) actually correct?**
  _`create_app()` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Settings` (e.g. with `_guard()` and `knowledge_search()`) actually correct?**
  _`Settings` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `ManagedSourceCreate` (e.g. with `add_source()` and `create_source()`) actually correct?**
  _`ManagedSourceCreate` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `SourceRepository` (e.g. with `_source_repository()` and `BulkUrlService`) actually correct?**
  _`SourceRepository` has 19 INFERRED edges - model-reasoned connections that need verification._