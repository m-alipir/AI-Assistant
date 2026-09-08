# Project Progress — Source of Truth

**Project state:** IN PROGRESS
**Current milestone:** M18
**Last updated:** 2026-09-08

## Rules for Codex
- Read this file before every task.
- Work on the current milestone unless a prerequisite fix is needed.
- Change `[ ]` to `[x]` only after acceptance criteria and tests pass.
- Use `[~]` for in-progress and `[!]` for blocked.
- At the end of each task update `Last work log`, `Tests`, and `Current milestone`.
- Never put secrets here.

---

## M0 — Foundation / runnable skeleton
**Status:** [~] IN PROGRESS

- [x] Python project/package structure
- [x] Dockerfile + Docker Compose dev stack
- [x] Postgres + pgvector local development service
- [x] Settings/config loader + `.env.example`
- [x] Structured logging
- [x] FastAPI `/health` and `/ready`
- [x] SQLAlchemy + Alembic foundation
- [x] External provider interfaces and test fakes
- [x] pytest harness
- [x] CI/local commands documented

**Acceptance:** `docker compose up` starts app + DB; health works; migrations run; unit test baseline passes; no external API key is required for tests.

## M1 — RSS/YouTube ingestion + freshness + deterministic dedup
**Status:** [x] COMPLETE

- [x] RSS/Atom collector
- [x] source configuration/seed loader
- [x] normalized timestamps/UTC
- [x] configurable freshness gates
- [x] first-run bounded lookback
- [x] future-date quarantine
- [x] canonical URL/GUID/video-ID dedup
- [x] content fingerprint cache
- [x] YouTube discovery
- [x] yt-dlp subtitle/auto-subtitle extraction wrapper
- [x] transcript timestamps preserved where possible
- [x] stale items skipped before LLM

**Acceptance:** fixture feeds containing old/new/duplicate items produce only fresh unique processing candidates; sample YouTube fixture/wrapper tests pass without media download.

## M2 — OpenRouter gateway + model router + structured extraction
**Status:** [x] COMPLETE

- [x] OpenRouter direct client
- [x] role-based model config + fallbacks
- [x] strict JSON-schema response handling
- [x] gatekeeper schema/flow
- [x] extractor schema/flow
- [x] application-level LLM result cache
- [x] token/cost/latency accounting (metadata-only durable records)
- [x] soft/hard daily budget policy (total/role limits, UTC rollover, email reserve)
- [x] fake provider for tests
- [x] model catalog advisory command

**Acceptance:** mocked end-to-end item can be gated/extracted; invalid output fails safely; duplicate content hits cache; business code never names a fixed model slug.

## M3 — Taxonomy, entities, event memory, pgvector retrieval
**Status:** [x] COMPLETE

- [x] hierarchical categories
- [x] normalized entities + aliases
- [x] topics/tags
- [x] source-backed claims
- [x] separate inferences
- [x] event/source provenance
- [x] embeddings + dimension metadata
- [x] structured filters
- [x] lexical retrieval
- [x] pgvector semantic retrieval
- [x] hybrid candidate reranking
- [x] raw/public-content retention job

**Acceptance:** a new AMD/TSMC-style event is discoverable through category, entity, date, lexical, and semantic retrieval while preserving sources.

## M4 — Correlation / historical reasoning
**Status:** [x] COMPLETE

- [x] correlation escalation policy
- [x] top-N historical retrieval context
- [x] reasoner structured schema
- [x] contradiction/update/supersession handling
- [x] temporal validity/status on knowledge
- [x] evidence IDs attached to inference
- [x] strong-model use only above threshold

**Acceptance:** fixture scenario connects a new event to relevant historical events without sending unrelated memory; inference remains visibly separate from claims.

## M5 — Gmail multi-account intelligence
**Status:** [x] COMPLETE

- [x] OAuth read-only flow for multiple accounts
- [x] encrypted/protected token storage
- [x] bounded initial sync
- [x] `historyId` incremental sync/checkpoints
- [x] deterministic sender/pattern rules
- [x] cheap LLM fallback classifier
- [x] classes: action/application/recruiter/security/transactional/recommendation/newsletter/personal/other
- [x] action/deadline extraction
- [x] job-application state linkage where possible
- [x] email raw-body retention policy
- [x] no general memory embedding of irrelevant emails

**Acceptance:** fixtures show LinkedIn-style recommendations suppressed/de-emphasized while application rejection/interview/security messages surface correctly; account checkpoints are independent.

## M6 — Daily briefing + global news stream
**Status:** [x] COMPLETE

- [x] `Action Required`
- [x] `For You`
- [x] `Tech & Industry`
- [x] `Connections / Why It Matters`
- [x] `World in Brief / Dünyada Neler Oldu?`
- [x] `Worth Watching`
- [x] global-news selection independent of personal interest score
- [x] event/source dedup in briefing
- [x] source links/provenance rendered
- [x] daily editor model
- [x] persisted briefing history
- [x] at least one delivery adapter + stdout/local preview

**Acceptance:** fixture day produces a coherent briefing where a globally important low-interest story remains visible under World in Brief.

## M7 — Stable adaptive interest learning
**Status:** [x] COMPLETE

- [x] base/explicit/adaptive interest layers
- [x] feedback event logging
- [x] explicit natural-language more/less mapping
- [x] nightly 14-day candidate scoring
- [x] minimum-signal/day thresholds
- [x] 7-day rate cap
- [x] ~21-day adaptive decay toward neutral
- [x] explanation/history/rollback
- [x] ranking integration
- [x] world stream unaffected by personal weights

**Acceptance:** one interaction has negligible/no persistent effect; repeated AMD-like interaction over multiple days increases ranking; explicit “more NVIDIA” changes immediately; global-news section is unchanged.

## M8 — Admin UI/API + deployment hardening
**Status:** [x] COMPLETE

- [x] local server-rendered admin dashboard for testing/operation
- [x] RSS-only runtime manual trigger (collector → filters → LLM → persistence → briefing)
- [x] source CRUD/enable-disable
- [x] model role config view
- [x] interest profile view/override
- [x] run-now action
- [x] recent briefings
- [x] run/LLM cost metrics
- [x] health/error overview
- [x] production Docker Compose/example
- [x] backup/migration notes
- [x] non-root/runtime hardening where practical
- [x] VPS deployment guide

**Acceptance:** fresh install can be configured without editing Python source; local -> VPS deployment path documented and tested. RSS runtime acceptance passed with a real TechCrunch → OpenRouter → event → briefing run.

## M9 — Safe daily RSS operation
**Status:** [~] IN PROGRESS

- [x] durable source-item idempotency before LLM work
- [x] provider-cost / configured-estimate / unavailable cost status
- [x] opt-in daily scheduler with configured local time and timezone
- [x] durable per-day scheduler claim to prevent restart double-runs
- [x] offline scheduler and repeated-run tests
- [ ] rebuilt-container second manual-run verification
- [ ] scheduler opt-in smoke verification (manual, explicit only)

**Acceptance:** a repeated manual RSS run makes no LLM calls for already persisted fresh items; the UI distinguishes unavailable cost from zero; scheduler defaults disabled and cannot create two scheduled briefings for one local day across restarts.

## M10 — Gmail runtime integration
**Status:** [x] COMPLETE

- [x] Gmail remains disabled by default and cannot break RSS-only runs
- [x] manual/scheduled runtime exposes Gmail processed/muted/failed/action-item counts
- [x] deterministic LinkedIn/newsletter suppression before any LLM fallback
- [x] panel shows configured state and authorized-account sync metadata without secrets/bodies
- [x] offline fake-sync tests
- [x] authorization-code OAuth callback with one-time expiring state and encrypted refresh-token storage
- [x] authenticated Fernet refresh-token encryption with encryption-key validation
- [x] legacy XOR token scheme marked for explicit reauthorization; no unsafe decryption migration
- [x] safe OAuth callback diagnostics for state, client, redirect, upstream, token, and storage failures
- [x] bounded Gmail REST metadata sync with refresh-token exchange and bounded retry/timeout
- [x] historyId checkpoint/incremental sync, INBOX filtering, and message-id idempotency
- [x] actionable email metadata joins the same persisted briefing under `Action Required`
- [x] Gmail failures are counted without aborting RSS; safe per-run Gmail metrics render in Admin

**Acceptance:** configured authorized accounts sync read-only mail into Action Required without exposing bodies/tokens; RSS/World behavior remains unchanged. Offline fake transports verify first sync, incremental history, history recovery, deduplication, and isolated Gmail failure behavior.

## M11 — YouTube daily runtime integration
**Status:** [x] COMPLETE

- [x] enabled public channel IDs use YouTube's Atom channel feed only
- [x] 72-hour source freshness/future filtering before captions or LLM work
- [x] video-ID, URL, fingerprint, and durable source-provenance idempotency
- [x] existing caption-only yt-dlp/VTT support with no video or audio download
- [x] existing gatekeeper/extractor flow persists caption-backed events
- [x] `Worth Watching` briefing entries contain source URL, publication time, and reason to watch
- [x] Admin exposes separate YouTube fetched/stale/duplicate/relevant/processed/caption/failed/LLM counts
- [x] offline fixture/fake coverage including stale, duplicate, and captionless cases
- [x] optional per-source `tr`/`en` caption preference persists through Admin YAML management
- [x] deterministic regional language matching and manual-over-automatic caption selection
- [x] wrong-language captions safely skip before LLM with distinct no-caption/access error counts
- [x] post-LLM failure categories distinguish gatekeeper, extractor, event persistence, briefing
  item/render, and provider-access outcomes without exposing source or provider payloads
- [x] durable post-LLM extraction/event-persistence guard prevents automatic repeat LLM spend
  for that video
- [x] Admin lists safe blocked-video metadata and atomically claims one user-selected retry
- [x] retry success clears the block and persists a Worth Watching briefing; retry failure re-blocks
  with a safe category
- [x] extractor accepts safe compact/fenced structured provider output without a second provider
  request; missing optional extraction lists do not turn a valid summary into a retry loop
- [x] per-run LLM accounting separates real provider calls from cache metadata and reports RSS,
  Gmail, YouTube, and briefing-editor role breakdowns in Admin
- [x] explicit real public-channel smoke test confirmed by the operator

**Acceptance:** an enabled public channel produces only fresh, unique, captioned video candidates;
relevant videos enter `Worth Watching`, while missing captions are counted as a safe skip. RSS and
Gmail remain independently usable if a YouTube source or caption request fails.

---

## M12 — Safe daily briefing operations
**Status:** [x] COMPLETE

- [x] scheduler remains opt-in (`SCHEDULER_ENABLED=false` by default)
- [x] `APP_TIMEZONE` and strict `SCHEDULER_DAILY_TIME=HH:MM` validation drive the local schedule
- [x] PostgreSQL `scheduled_runs.run_date` remains the durable one-claim-per-local-day guard
- [x] claimed schedule rows persist a safe completion status, timestamp, and aggregate-only summary
- [x] restart/repeated scheduler attempts safely report the already-claimed local-day skip
- [x] a shared non-queuing coordinator makes concurrent manual/scheduled runs skip rather than
  overlap provider work
- [x] empty/no-new-item runs retain zero provider/editor work and do not create a briefing
- [x] Admin shows enabled state, timezone, next run, current-process status/skip/error, and durable
  scheduled-run history without source payloads or secrets

**Acceptance:** with scheduling explicitly enabled, a single local-day scheduled claim survives
restart and prevents a second briefing/LLM run; a concurrent manual run is safely skipped or the
scheduled attempt records an active-run skip. Empty runs create neither a briefing nor an editor
call.

**Use:** set `APP_TIMEZONE=Europe/Istanbul`, `SCHEDULER_DAILY_TIME=08:00`, and
`SCHEDULER_ENABLED=true` in `.env`, then rebuild/restart. First choose a time a few minutes ahead,
watch the Scheduler panel for its claimed row and safe summary, then restore the desired daily time.
Leave `SCHEDULER_ENABLED=false` until that manual scheduling observation is complete.

---

## M13 — User Search / Ask over retained knowledge
**Status:** [x] COMPLETE

- [x] Admin Search / Ask accepts Turkish questions plus date, entity, category, topic, and source
  type filters
- [x] deterministic filter narrowing and the existing hybrid lexical/vector ranker run before any
  model call; only the top five compact candidates may reach the configured `reasoner` role
- [x] source-backed claims/facts, source URLs, dates, stored inferences, and fresh model inferences
  are visibly separated
- [x] no-candidate result returns `Yeterli kaynak bulunamadı.` without a model request
- [x] Gmail search reads only existing classification/action summary/deadline/company metadata;
  no subject, sender, body, OAuth material, or mailbox scan is used
- [x] new event persistence records safe source URL/type and category/entity/topic metadata for
  future filtering; legacy events remain searchable lexically
- [x] reasoner calls retain existing router budgets, cache, durable ledger accounting, and provider
  versus cache visibility in the response

**Acceptance:** a Turkish question produces a bounded, source-linked event list and a clearly
separate inference section, while empty results do not call a model. Gmail action records stay
within the existing privacy boundary.

**Limitations:** events persisted before migration `20260907_0013` may not have an original source
URL or category/entity/topic metadata; they are still title/claim/date searchable. Existing runtime
does not persist real embeddings, so the hybrid semantic component is neutral until embedding
storage is wired; deterministic filters and lexical ranking remain active.

---

## M14 — Production security hardening
**Status:** [x] COMPLETE

- [x] documented threat model covering Admin, OAuth, provider secrets/tokens, database/Docker,
  untrusted source data, and Search/Ask boundaries
- [x] production fail-closed Admin Basic authentication, explicit host allow-list, same-origin
  mutation guard, disabled API docs, browser security headers, and Admin no-store responses
- [x] production-only HTTPS origin/redirect validation and optional proxy-aware HTTPS enforcement
- [x] file-backed secret settings plus process-wide log redaction for known values and common
  credential/query shapes; no secret values added to configuration or tests
- [x] bounded OAuth authorization state attempts and bounded callback query parameters
- [x] production RSS/YouTube feed request guard: HTTPS-only, public DNS/IP validation, and validated
  bounded redirects; local fixture/private-source behavior remains opt-in development behavior
- [x] production Compose least-privilege app hardening: non-root image, read-only root filesystem,
  dropped capabilities, no-new-privileges, bounded tmpfs/PID count, private database network,
  health checks, restart policy, and localhost-only app port
- [x] deployment, backup/restore, token-revocation, and accepted-risk runbook updated
- [x] offline regressions for unauthenticated/CSRF Admin access, fail-closed production settings,
  private/insecure feed denial, and log redaction

**Acceptance:** production configuration cannot boot with an unprotected Admin surface or permissive
source-fetch policy; unauthenticated/cross-origin Admin mutation is rejected; no test makes a real
provider request; the deployment guide gives a TLS, backup, and secret-handling path.

**Known limitations / accepted risks:** Basic auth is single-operator rather than MFA/RBAC/rate
limited, OAuth state is memory-local for this single-process deployment, and public DNS can still
change after resolution. Put a production Admin behind VPN/identity-aware proxy where possible;
multi-replica deployment needs shared OAuth state and external secret management. No destructive
email metadata-retention migration was added; a retention job needs a separately approved
backup/legal-retention plan.

---

## M15 — Production cost, recovery, and query-path hardening
**Status:** [x] COMPLETE

- [x] role-configured LLM input ceilings now bound gatekeeper metadata, extractor source text,
  Search/Ask context, and the editor's distilled briefing input; cache prompt versions were bumped
  where deterministic truncation changed the effective prompt
- [x] unknown provider cost remains visibly `unavailable` and cannot cause unbounded work: a
  configuration-driven daily provider-call ceiling is persisted/hydrated alongside USD budgets
- [x] shared non-queuing provider-work coordination prevents overlapping uncached manual,
  scheduler, retry, and Ask calls in the documented single-process runtime; busy/budget skips are
  retryable and never become a permanent post-LLM block
- [x] RSS now has the same post-extraction/event-persistence failure block semantics as YouTube,
  plus an atomically claimed explicit RSS retry endpoint; automatic runs never repeat that cost
- [x] safe briefing candidates are transactionally staged in a bounded outbox with event/action
  persistence, and drained under row locks; a partial briefing failure recovers on a later run
  without rerunning LLM work
- [x] Gmail action briefing recovery uses retained action summaries rather than email subjects
- [x] run results expose safe RSS/Gmail/YouTube error categories, including provider-busy and
  budget-exhausted states; no raw source/provider payload is added
- [x] real query paths gained only targeted forward indexes: briefing/LLM/email recency, source-item
  dedup, source-kind Search filtering, and blocked-item listing. Search now bounds per-event facts,
  inferences, and links before materializing candidates.

**Acceptance:** fixture/mocked RSS, Gmail, YouTube, retry, scheduler, Search/Ask, editor cache,
and cost-guard scenarios run without external requests; empty briefings make no editor call;
partial briefing persistence retains a safe recoverable outbox record; and production read paths
stay bounded.

**Known limitation:** provider-work coordination is intentionally process-local. The existing
single-process production profile is protected; a future multi-replica deployment requires a
database-backed distributed work lease/reservation before concurrent replicas are enabled.

---

## M16 — Readable personalized briefing experience
**Status:** [x] COMPLETE

- [x] persisted briefing detail renders fixed Turkish-first sections with Istanbul-local display time
- [x] compact claims and provenance links are bounded; model inferences are visibly labelled
- [x] detail display never invokes an LLM and old rendered briefings retain a safe legacy fallback
- [x] item feedback writes existing feedback events; explicit more/less updates stable explicit
  interest immediately while a single `Faydalı değil` signal does not alter adaptive interest
- [x] World in Brief feedback is recorded but cannot alter world ranking or profile weight
- [x] new briefing snapshots persist Turkish extractor/editor fields at creation time; the reader
  never translates or calls a model on view
- [x] legacy/source-language fallback is visibly labelled, generic importance/explanation text is
  omitted, and only stored model inferences are labelled as such
- [x] feedback shows a Turkish confirmation, selected state, and persisted explicit more/less state
  after reload without changing adaptive interest from one click

**Limitations:** old records do not contain structured item snapshots, so their safe fallback has no
per-item feedback and remains in its original language. Newly generated summaries depend on the
configured extractor following its Turkish structured-output instruction; a source-language fallback
is labelled rather than translated at read time.

---

## M17 — Production operations verification
**Status:** [~] IN PROGRESS

- [x] offline production preflight remains covered: fail-closed settings, Admin/origin controls,
  source-fetch restrictions, Compose network/least-privilege topology, and generated migration SQL
- [x] VPS runbook now sequences encrypted backup/isolated restore, startup/migration confirmation,
  TLS/Admin/health validation, M16 legacy-reader checking, and a scheduler-off default
- [x] M16 migration `20260908_0015` is explicitly included in the operational verification path
- [x] Hermes is documented as a separate orchestration layer with generic future domain API
  namespaces; direct DB, Gmail-token, OpenRouter-secret, and shell access remain prohibited
- [ ] staging VPS backup and isolated restore observation
- [ ] staging/production Compose startup, TLS proxy, authenticated Admin, health/readiness, and
  migration-revision observation
- [ ] explicitly approved controlled fresh-briefing verification, if a newly persisted Turkish
  snapshot is required (must not enable scheduler or use providers implicitly)

**Acceptance:** a staging or production operator records the safe checklist observations after a
tested backup/restore and confirms the hardened deployment, migration revision, and reader behavior
without exposing secrets or enabling unapproved live integrations. Offline evidence alone cannot
close this milestone.

---

## M18 — Secure read-only Agent API
**Status:** [x] COMPLETE

- [x] generic versioned read-only briefing latest/list/detail endpoints under `/api/v1/briefings/...`
- [x] bounded `/api/v1/knowledge/search` delegates to the existing deterministic Search/Ask path
  and projects facts, stored/model inferences, source links, and safe Gmail action metadata only
- [x] API is disabled by default and uses a dedicated environment/secret-file bearer token that is
  distinct from Admin Basic auth and omitted from logs, responses, Admin, and audit data
- [x] bounded pagination, request/response sizes, process-local rate limit, no-store responses,
  and generic failure responses protect the integration surface
- [x] metadata-only audit persistence adds only timestamp, endpoint, outcome, and response bytes
  through migration `20260908_0016`; it contains no caller, token, question, source, or payload
- [x] no mutation endpoints; Admin-only feedback, source, scheduler, Gmail, and retry controls stay
  outside this API
- [x] full offline regression, lint, generated migration SQL, and diff validation

**Acceptance:** a configured external HTTP client can retrieve only bounded persisted briefing and
knowledge projections with a dedicated token; disabled/wrong-token/oversize/rate-limit cases fail
safely; facts and inferences remain distinct; Gmail identity/body/token and operational/provider
secrets never appear; metadata-only audit persists without request content.

---

## Backlog / explicitly out of current track
- [ ] Gmail Pub/Sub push/watch if polling latency becomes a real issue
- [ ] Audio download + STT fallback when no YouTube captions exist
- [ ] Telegram/Discord richer interactive feedback buttons
- [ ] Qdrant migration only if pgvector scale proves inadequate
- [ ] browser automation for non-RSS/paywalled/dynamic sources
- [ ] richer Q&A/chat over the knowledge base
- [ ] automatic source-quality learning
- [ ] task/reminder workflows, PC activity tracking, local model routing, and home-PC coding bridge
  (separate future scope; not part of AI Assistant M18)

## Blockers
None. Credentials are not required for offline tests or local defaults.

## Tests
- 2026-09-08: M18 secure read-only Agent API: 137 passed, 1 skipped (dedicated PostgreSQL
  integration URL not configured), 2 upstream deprecation warnings; Ruff, generated Alembic SQL
  through `20260908_0016`, and `git diff --check` passed. New offline coverage verifies disabled,
  missing/wrong-token, strong-token fail-closed, bounded briefing/list output, source-fact versus
  inference separation, Gmail safe-action projection, no-result/zero-provider projection,
  request/response limits, rate limit, no-store/Vary headers, and metadata-only audit callback.
  No real Hermes, OpenRouter, Gmail, YouTube, RSS, database, or user-data request was made.
- 2026-09-08: M17 offline production-operations preflight: 128 passed, 1 skipped (dedicated
  PostgreSQL integration URL not configured), 2 upstream deprecation warnings; Ruff, generated
  Alembic SQL through `20260908_0015`, and `git diff --check` passed. The VPS checklist deliberately
  makes backup/restore, proxy, container, and migration observations operator-run; no live provider,
  Gmail, YouTube, or RSS request was made.
- 2026-09-08: M16 Turkish briefing/feedback refinement: 128 passed, 1 skipped (dedicated PostgreSQL
  integration URL not configured), 2 upstream deprecation warnings; Ruff, Alembic SQL through
  `20260908_0015`, and `git diff --check` passed. Offline coverage confirms Turkish snapshot versus
  legacy original-text behavior, no generic placement explanation, selected feedback UI state, and
  a zero-LLM reader contract. No external provider, Gmail, YouTube, or RSS call was made.
- 2026-09-08: M16 briefing experience validation: focused offline tests cover legacy rendering,
  Istanbul timestamp formatting, fixed section/feedback UI controls, World preference isolation,
  and existing stable-interest behavior. No LLM, Gmail, YouTube, or RSS request was made.
- 2026-09-08: Search/Ask PostgreSQL runtime recovery: 124 tests passed (2 upstream deprecation
  warnings), including a real PostgreSQL integration database migrated through `20260908_0014`.
  The integration fixture verified current NVIDIA RSS metadata/provenance, a metadata-less legacy
  event, and a Gmail security action row, then removed its temporary database. The root cause was
  an asyncpg ambiguous-type failure caused by binding `NULL` into `:source_kind IS NULL`; the query
  now adds that predicate only when an RSS/YouTube filter is selected. Regression coverage also
  confirms source results survive reasoner validation/provider/budget failures and Admin returns
  safe migration/database guidance rather than a 500. No real Gmail, OpenRouter, YouTube, or RSS
  request was made.
- 2026-09-08: M15 final offline validation: `.venv\Scripts\python.exe -m pytest` — 118 passed
  (2 upstream FastAPI/Starlette deprecation warnings); `.venv\Scripts\ruff.exe check .` — passed;
  `.venv\Scripts\alembic.exe upgrade head --sql` — passed through `20260908_0014`; and
  `git diff --check` — passed. New fixture/mocked coverage verifies unknown-cost provider-call
  capping, shared provider-work collision rejection, bounded gatekeeper/Search/Ask/editor inputs,
  RSS post-LLM automatic blocking plus explicit retry, pending-briefing recovery, RSS/Gmail/YouTube
  safe run accounting, scheduler collision behavior, and Search/Ask no-source behavior. No real
  OpenRouter, Gmail, YouTube, RSS, database, secret, or user-data request was made.
- 2026-09-08: M14 security hardening validation: 108 full offline tests passed (2 upstream
  deprecation warnings). New fixtures cover production Admin authentication and same-origin
  mutation protection, fail-closed production settings, private/insecure feed target rejection,
  and known/common-secret log redaction. No real Gmail, OpenRouter, YouTube, RSS, or database
  request was made. Production Compose was statically reviewed; Docker runtime verification is an
  operator pre-deployment checklist item because it requires the user's host/proxy/secrets.
- 2026-09-07: M13 Search / Ask validation: fixture/mocked tests cover Turkish `bu hafta` date
  inference, deterministic metadata narrowing + hybrid ranking, source links, no-source no-model
  behavior, bounded reasoner synthesis with separately rendered inferences, safe Gmail summaries,
  Admin API/template rendering, and persistence regression. No OpenRouter, Gmail, YouTube, or RSS
  request was made. Migration SQL generated cleanly through `20260907_0013`.
- 2026-09-07: M12 scheduler validation: 97 full offline tests passed (2 upstream deprecation
  warnings); Ruff and `git diff --check` passed, and Alembic SQL generated cleanly through
  `20260907_0012`. Coverage includes Istanbul
  local-time calculation, opt-in disabling, same-day/restart durable claim rejection,
  manual/scheduled collision skip, zero-work aggregate accounting, Admin rendering, and settings
  validation. No external API request was made.
- 2026-09-07: M11 retry/accounting regression validation: 93 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Tests cover a compact/fenced
  extractor response completing in one provider request, safe provider-versus-cache / role
  accounting, panel per-flow rendering, blocked-video retry success, and automatic blocked-video
  skip. No YouTube, OpenRouter, Gmail, or other external request was made. A rebuilt deployment
  and an explicit user-selected real retry remain required to validate the existing blocked item.
- 2026-09-07: M11 controlled blocked-video retry validation: 90 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Fixtures cover normal blocked skipping
  without LLM work, one explicit retry producing a briefing item, safe retry failure re-blocking,
  and a duplicate retry endpoint request returning 409. Migration `20260907_0011` generated valid
  PostgreSQL SQL. No YouTube or LLM request was made.
- 2026-09-07: M11 post-LLM failure regression validation: 88 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Tests cover successful Worth Watching
  rendering, gatekeeper/extractor/event-persistence/briefing-item failure categories, safe
  briefing-render categorization, and a second post-persistence-failure run blocked before LLM
  work. Migration `20260907_0010` generated valid PostgreSQL SQL. No YouTube or LLM request was
  made.
- 2026-09-07: M11 language-preference validation: 83 offline tests passed (2 upstream deprecation
  warnings). Fixtures/mocks cover `tr`/`en`, regional variants, human-over-automatic selection,
  wrong-language no-LLM skip, yt-dlp language request narrowing, safe caption-access
  categorization, and Admin YAML add/edit persistence. No YouTube or LLM network request was made.
- 2026-09-07: M11 YouTube runtime validation: 78 offline tests passed (2 upstream deprecation
  warnings); Ruff and `git diff --check` passed. Fixture tests verify public Atom discovery,
  72-hour freshness before captions/LLM, human-caption VTT processing, persistent duplicate skip,
  captionless safe skip, Worth Watching metadata, and Admin count rendering. No YouTube download
  or external API request was made. A real public-channel smoke test remains user-selected.
- 2026-09-07: M10 Gmail runtime completion validation: 75 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Mock Gmail REST tests cover bounded
  metadata-only initial sync, INBOX-filtered history sync, expired-history recovery, deterministic
  noise muting, classification persistence without bodies, per-message idempotency, checkpoint
  updates, and Gmail failure isolation from RSS. No connected account or Google endpoint was used.
- 2026-09-07: OAuth callback diagnostic validation: 68 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Mock Google token responses cover
  invalid client/redirect/upstream codes and missing refresh tokens; callback tests cover all safe
  categories and ensure authorization codes and refresh tokens do not appear in the response. No
  Google request was made.
- 2026-09-07: Gmail token-storage security validation: 56 offline tests passed (2 upstream
  deprecation warnings); Ruff and `git diff --check` passed. Tests cover Fernet encrypt/decrypt,
  wrong-key and tampered-ciphertext rejection, invalid key format, and OAuth callback storage that
  never returns a refresh token. Migration SQL was generated successfully through revision
  `20260907_0009`; no Google request was made.
- 2026-09-07: OAuth validation: 52 offline tests passed (2 upstream deprecation warnings); Ruff
  passed. Tests assert the authorization URL asks only for `gmail.readonly`, does not expose the
  client secret, and rejects invalid state before network access.
- 2026-09-07: M10 offline validation: 50 passed (2 upstream deprecation warnings); Ruff passed.
  Fake Gmail tests verify disabled mode makes no transport call and LinkedIn recommendation noise is
  muted while a security alert becomes an action item. No Google API call was made.
- 2026-09-07: M9 offline validation: 48 passed (2 upstream deprecation warnings); Ruff passed.
  Tests cover OpenRouter provider-cost parsing, a second run skipping known source-item hashes before
  LLM calls, disabled scheduler behavior, and one durable scheduler claim per Istanbul day. A real
  second-run check awaits rebuilding the application image.
- 2026-09-07: RSS runtime offline validation: fixture run confirms 4 fetched entries are reduced
  to one fresh unique LLM candidate before gatekeeper/extractor work; it persists an event and a
  briefing through injected writers and reports exact run counts. Admin tests cover both an
  unbound callback (`completed_noop`) and an awaited bound callback returning counts.
- 2026-09-07: Admin dashboard validation: focused dashboard/API action tests cover the setup
  banner with API-key redaction, RSS add/enable/delete, model-ID persistence, explicit interest
  actions, and honest `completed_noop` run reporting. Full suite: 43 passed (2 upstream
  deprecation warnings); Ruff passed. Docker CLI was unavailable on this host, so the currently
  running localhost container could not be rebuilt for a new-image smoke test.
- 2026-09-07: M8 runtime-fix offline validation: Ruff passed; pytest 40 passed (2 upstream
  deprecation warnings); `docker compose -f compose.production.yaml config` passed with an
  ephemeral `POSTGRES_PASSWORD` for interpolation. This earlier retry could not run normal Docker
  smoke because the Linux engine was unavailable; it was subsequently re-run successfully below.
- 2026-09-07: M8 final runtime validation: normal `docker compose up --build -d` rebuilt the app;
  app/db were healthy (ports 8000/5433); `/health` returned `ok`; `/ready` returned `ready`; DB
  revision was `20260907_0007`. `/admin` returned 200 and `/admin/config`, `/admin/status`,
  `/admin/briefings`, `/admin/sources`, `/admin/interests`, and `/admin/run-now` all returned
  successfully. Config was loaded from container paths without file errors; run-now returned the
  safe `completed_noop` result. The full offline suite was 40 passed with Ruff clean.
- 2026-09-07: M8 final validation: Ruff passed; pytest 36 passed (2 upstream deprecation warnings).
  Docker rebuild passed with app/db healthy; `/health` `ok`; `/ready` `ready`; admin HTML returned
  200 and status/config/sources/interests/briefings/run-now API smoke checks returned successfully.
- 2026-09-07: M7 full validation: Ruff passed; pytest 36 passed (2 upstream deprecation warnings).
  Docker rebuild passed with app/db healthy, `/health` `ok`, `/ready` `ready`, revision
  `20260907_0007`, and `interest_profile`/`feedback_events`/`interest_candidates` tables present.
- 2026-09-07: M6 full validation: Ruff passed; pytest 35 passed (2 upstream deprecation warnings).
  Docker rebuild passed with app/db healthy, `/health` `ok`, `/ready` `ready`, revision
  `20260906_0006`, and `briefings`/`briefing_items` tables present.
- 2026-09-06: M5 full validation: Ruff passed; pytest 34 passed (2 upstream deprecation warnings).
  Docker rebuild passed with app/db healthy, `/health` `ok`, `/ready` `ready`, revision
  `20260906_0005`, and `gmail_accounts`/`email_classifications` tables present.
- 2026-09-06: `.venv\\Scripts\\python.exe -m pytest` — 8 passed (2 upstream
  FastAPI/Starlette deprecation warnings), including configurable Compose DB host-port coverage.
- 2026-09-06: `.venv\\Scripts\\ruff.exe check .` — passed after the port configuration update.
- 2026-09-06: `.venv\\Scripts\\alembic.exe upgrade head --sql` — passed; generated
  `CREATE EXTENSION IF NOT EXISTS vector`.
- 2026-09-06: `git diff --check` — passed.
- 2026-09-06: Docker Compose runtime verification passed externally: `app` healthy on
  `0.0.0.0:8000`, `db` healthy on `0.0.0.0:5433`; `/health` returned `ok`; `/ready` returned
  `ready`; app logs recorded Alembic revision `20260906_0001`; PostgreSQL reported both
  `alembic_version=20260906_0001` and `vector` extension present.
- 2026-09-06: M1 deterministic fixture suite: `.venv\\Scripts\\python.exe -m pytest` —
  14 passed (2 upstream FastAPI/Starlette deprecation warnings). Covers fresh/old/future RSS
  handling, fresh-only downstream callback, ID/URL/fingerprint deduplication, source defaults,
  public YouTube Atom discovery, caption-only yt-dlp options, and timestamped VTT parsing.
- 2026-09-06: M1 `.venv\\Scripts\\ruff.exe check .` — passed.
- 2026-09-06: `uv lock` and `uv sync --extra dev` — passed; `uv.lock` refreshed with
  feedparser and yt-dlp dependencies.
- 2026-09-06: M1 `.venv\\Scripts\\alembic.exe upgrade head --sql` — passed.
- 2026-09-06: M1 Docker rebuild/runtime verification passed: `app` healthy on
  `0.0.0.0:8000`, `db` healthy on `0.0.0.0:5433`; `/health` returned `ok`; `/ready` returned
  `ready`; PostgreSQL returned `20260906_0001` and `vector`.
- 2026-09-06: M2 full offline validation: `.venv\\Scripts\\ruff.exe check .` — passed;
  `.venv\\Scripts\\python.exe -m pytest` — 22 passed (2 upstream FastAPI/Starlette
  deprecation warnings). The fixture-only suite covers strict-output fallback, invalid-output
  safe failure, gatekeeper/extractor validation, total/role soft-hard budgets with UTC rollover
  and email reserve, and restart-style durable cache reuse. No API key or OpenRouter request was
  used.
- 2026-09-06: M2 `.venv\\Scripts\\alembic.exe upgrade head --sql` — passed; emitted revision
  `20260906_0002` with `llm_calls` and `llm_result_cache`.
- 2026-09-06: M2 Docker rebuild/runtime verification passed: `docker compose up --build -d`
  rebuilt the app; `app` healthy on `0.0.0.0:8000` and `db` healthy on `0.0.0.0:5433`;
  `/health` returned `ok`; `/ready` returned `ready`. PostgreSQL reported
  `alembic_version=20260906_0002`; `llm_calls` has
  `id, role, model_id, input_tokens, output_tokens, estimated_cost_usd, latency_ms, cache_hit,
  status, created_at`; `llm_result_cache` has `cache_key, model_id, validated_result_json,
  created_at`.
- 2026-09-06: M3 full validation: `.venv\\Scripts\\ruff.exe check .` — passed;
  `.venv\\Scripts\\python.exe -m pytest` — 30 passed (2 upstream FastAPI/Starlette
  deprecation warnings); `.venv\\Scripts\\alembic.exe upgrade head --sql` — passed and emitted
  revision `20260906_0003`.
- 2026-09-06: M3 Docker rebuild/runtime verification passed: app/db healthy on ports 8000/5433;
  `/health` returned `ok`; `/ready` returned `ready`; PostgreSQL returned
  `alembic_version=20260906_0003`, eight M3 relational tables, and `events.embedding:vector`.
- 2026-09-06: M4 full validation: `.venv\\Scripts\\ruff.exe check .` — passed;
  `.venv\\Scripts\\python.exe -m pytest` — 32 passed (2 upstream FastAPI/Starlette
  deprecation warnings). Docker rebuild passed: app/db healthy, `/health` `ok`, `/ready` `ready`,
  and PostgreSQL reported revision `20260906_0004`, `events.status`, and `event_relations`.

## Last work log
- 2026-09-08: Completed M18 secure read-only Agent API. Added disabled-by-default separate bearer
  authentication, bounded briefing latest/list/detail reads, and a bounded Agent projection over
  the existing Search/Ask pipeline. The new `agent_api_audit_log` migration retains timestamp,
  endpoint, outcome, and response size only. No Admin/write route, secret/token, mailbox identity
  or body, raw source material, provider metadata, shell, or Hermes-specific dependency was added.
  Documented the generic HTTP contract and connection checklist in `docs/AGENT_API.md`.
- 2026-09-08: Started M17 production operations verification. Documented the safe staging/VPS
  sequence for backup/isolated restore, hardened Compose/TLS/Admin checks, `20260908_0015`
  confirmation, and no-provider M16 reader observation. Recorded the separate Hermes orchestration
  and coding-worker trust zones; no integration endpoint or out-of-scope automation feature was
  added. Real environment observations remain required to close M17.
- 2026-09-08: Refined M16 briefing reader quality. New briefing outbox rows persist Turkish title,
    summary, and change snapshots at generation, then store the selected item snapshot transactionally
    with the briefing. The reader does not invoke a model or fabricate translation for older records;
    it labels their original/source text instead. Feedback now returns a visible Turkish confirmation
    and selected state, and reloads explicit more/less preferences safely. Generic importance and
    placement filler was removed; World in Brief remains profile-independent.
- 2026-09-08: Recovered Search/Ask against the migrated PostgreSQL runtime. The optional
  `source_kind` SQL predicate is now built only for selected RSS/YouTube filters, avoiding
  asyncpg's untyped-NULL preparation error. Legacy metadata-less events and safe Gmail
  classifications tolerate missing optional fields; Gmail's timestamp is correctly mapped to
  `recorded_at`. Retrieval/database failures are categorized safely, while reasoner/ledger/schema
  failures preserve retrieved sources and render a short Turkish degraded-summary message.
- 2026-09-08: Completed M15 production cost, recovery, and query-path hardening. Added bounded,
  versioned role prompts; a durable daily logical-provider-call cap for unavailable prices; and a
  shared non-queuing provider-work guard. RSS now joins YouTube's post-LLM block/explicit-retry
  safety model, while a transactionally drained briefing outbox makes partial briefing writes
  restart-safe without re-extracting or recharging. Added only query-proven indexes and bounded
  Search materialization; Gmail recovery reuses action summaries instead of subjects. All work was
  fixture/mocked and offline.
- 2026-09-08: Completed M14 production security hardening. Production now fails closed without
  authenticated Admin access, an HTTPS public origin/host allow-list, and public HTTPS-only source
  fetch policy. Admin mutations use same-origin CSRF protection; secret-file support, defensive log
  redaction, bounded OAuth-state allocation, browser headers, and a least-privilege production
  Compose profile were added. The security/deployment guides record the threat model, backup and
  revocation path, and accepted single-process/Basic-auth limitations. No secrets, token values, or
  real provider requests were used.
- 2026-09-07: Completed M13 Search / Ask. The user-facing Admin screen reuses bounded event-memory
  retrieval, adds deterministic filters and provenance metadata for new events, and optionally
  calls the configured reasoner only with compact top candidates. Source-backed facts, stored
  inference, and fresh model inference are separate; Gmail search remains classification-only.
- 2026-09-07: Completed M12 daily operations hardening by retaining the existing scheduler and
  adding safe result persistence, strict timezone/time validation, a shared manual/scheduled
  non-queuing execution guard, and Admin scheduler history/status. The daily database claim remains
  authoritative across restart; no empty run creates a briefing/editor request.
- 2026-09-07: Hardened the explicit YouTube retry against a common safe extractor-output shape:
  fenced JSON, `summary` alias, omitted optional extraction lists, and string claims are normalized
  locally before strict validation without logging or re-sending captions. A truly malformed output
  still remains safely blocked. Manual/scheduled runs now report reset-per-run provider calls apart
  from cache-hit ledger metadata, by RSS/Gmail/YouTube/briefing-editor and role; the outdated Admin
  `completed_noop` explanation was replaced with the connected-runtime behavior.
- 2026-09-07: Added safe, controlled Admin retry for blocked YouTube videos. The new migration
  stores only operational retry metadata (title/channel/time/URL hash/category), claims retries
  atomically to prevent double LLM spending, and clears or re-blocks the record after the explicit
  attempt. Regular and scheduled ingestion remain blocked.
- 2026-09-07: Split YouTube's post-caption `processing_error` into safe gatekeeper, extractor,
  event-persistence, and briefing-item categories. Added a migration-backed, hash-only
  post-LLM-failure guard for extractor or event-persistence failures so manual/scheduled retries
  do not repeat a costly LLM attempt; no transcript, token, provider response, or secret is
  retained by the guard. Briefing rendering/persistence is also now safely categorized.
- 2026-09-07: Added optional `tr`/`en` YouTube source language preferences to the existing Admin,
  YAML catalog, and caption-only runtime. Preferred-language tracks are selected deterministically
  (manual before automatic); a missing preference is a safe pre-LLM skip, while feed access,
  yt-dlp caption access, and processing failures remain separately observable. Existing sources
  without a language setting retain their prior behavior.
- 2026-09-07: Started M11 YouTube runtime integration. Reused public channel Atom discovery and
  caption-only yt-dlp/VTT tooling in a bounded job that joins Gmail/RSS in one persisted briefing.
  No general web crawling, media/audio download, or live YouTube request was added. Real
  public-channel testing is intentionally left as an explicit user action.
- 2026-09-07: Completed M10 Gmail runtime integration. Existing Fernet/OAuth account records now
  drive bounded metadata-only Gmail REST sync with refresh-token exchange, `historyId` checkpoints,
  safe deterministic classification/idempotency, and Action Required briefing items. New optional
  bounded-sync settings have safe defaults; no additional secret is required. Real manual testing
  remains an explicit user action and was not performed by Codex.
- 2026-09-07: Replaced the OAuth callback's indistinguishable failure with safe categorized
  diagnostics. Server logs now contain only a whitelisted category and the callback provides a
  Turkish remediation message plus that category; Google response bodies and secret material are
  deliberately ignored.
- 2026-09-07: Replaced the test-stage SHA-256/repeating-XOR refresh-token protection with Fernet
  authenticated encryption. Added strict `APP_ENCRYPTION_KEY` validation, Compose propagation,
  `fernet-v1` token-scheme persistence, and a safe reauthorization path for legacy XOR rows;
  no token material is migrated, displayed, or logged.
- 2026-09-07: Added Google authorization-code OAuth entry/callback endpoints with a single-use,
  10-minute state, configurable redirect URI, bounded token exchange, and encrypted refresh-token
  persistence. The existing Gmail runtime remains safe when disabled. Gmail REST list/history
  retrieval still needs to be connected before a mailbox can be synced.
- 2026-09-07: Started M10 Gmail runtime integration. Connected safe opt-in Gmail result accounting
  to manual/scheduled runs and panel status, retaining deterministic noise filtering. The inherited
  project has token encryption and fixtures but no Google OAuth callback or REST transport, so live
  account authorization/sync remains explicitly blocked rather than simulated.
- 2026-09-07: Started M9 safe daily RSS operation. Added durable pre-LLM idempotency using source
  provenance, honest LLM cost provenance (`provider_reported`, `configured_estimate`, or
  `unavailable`), and an opt-in `Europe/Istanbul` daily scheduler with a durable per-day claim.
  Gmail and YouTube were not expanded. Rebuilt-container manual verification remains pending.
- 2026-09-07: Added an RSS-only runtime job and bound it at application startup when the database
  engine is present. Each manual run reloads source/model configuration, fetches enabled RSS feeds,
  applies freshness/future/dedup before OpenRouter gatekeeper/extractor calls, writes event/claim
  provenance and briefing rows, and returns safe operational counts/errors. M8 is in progress
  pending a rebuilt-container real RSS run.
- 2026-09-07: Replaced the `/admin` placeholder with a lightweight Jinja2 dashboard while keeping
  the existing JSON endpoints. The dashboard supports safe YAML-backed RSS/YouTube source
  management, role model-ID updates without exposing credentials, interest overrides, manual run
  status, persisted briefing/event/LLM-ledger views, and honest diagnostics for unavailable
  runtime capabilities. It explicitly reports that no ingestion callback is wired, so a real
  RSS-to-briefing first run cannot yet succeed from configuration alone.
- 2026-09-06: Product architecture/spec package created before implementation. No code written yet.
- 2026-09-06: M0 foundation implemented: Docker Compose app + pgvector service, automatic
  startup migration, FastAPI health/readiness endpoints, validated environment settings,
  structured JSON logging, async SQLAlchemy/Alembic base, offline provider contracts/fakes,
  unit tests, and CI/local setup documentation. M0 remains in progress until Docker runtime
  verification can be performed.
- 2026-09-06: Compose image build was confirmed externally, but startup failed only because host
  port 5432 was already allocated. Changed the non-destructive default host DB port to 5433 and
  added `POSTGRES_HOST_PORT` configuration plus rerun instructions. M0 remains in progress
  pending successful stack, migration, and endpoint verification.
- 2026-09-06: Revised Compose stack verified with health, readiness, migration, and pgvector
  extension checks. M0 accepted; M1 is now active.
- 2026-09-06: M1 accepted with an offline, fixture-driven ingestion vertical slice: bounded
  RSS/Atom and YouTube channel discovery, source-file freshness defaults, UTC normalization,
  freshness/future quarantine before downstream work, deterministic identity cache, and
  caption-only yt-dlp/VTT support. No LLM or media download was introduced. M2 is now active.
- 2026-09-06: M1 image rebuilt with feedparser, PyYAML, httpx, and yt-dlp dependencies; Compose
  health/readiness and existing migration/pgvector checks passed with host DB port 5433 retained.
- 2026-09-06: M2 core implementation added direct bounded OpenRouter HTTP client, YAML role
  routing/fallbacks, strict Pydantic structured outputs, cache keys, usage metadata, budget
  reserve foundation, and advisory catalog command. Remains in progress for durable accounting
  and complete role/total budget enforcement.
- 2026-09-06: M2 accepted: added metadata-only SQLAlchemy operational cache/accounting models,
  async repository boundary and in-memory fake, Alembic revision `20260906_0002`, exact-key
  restart-persistent result reuse, and complete total/role budget enforcement. Offline and Docker
  acceptance evidence passed; M3 is now active.
- 2026-09-06: M3 accepted with hierarchical category paths, normalized entity aliases/topics,
  source-provenanced events/claims kept separate from inferences, dimension-aware pgvector event
  storage, deterministic structured/lexical/cosine hybrid retrieval, and raw-content expiry that
  preserves distilled records. AMD/TSMC fixture acceptance passed; M4 is now active.
- 2026-09-06: M4 accepted with deterministic escalation before any reasoner call, bounded
  top-N compact context, strict evidence-bound correlation inference schema, and persisted event
  relation/status support. M5 is now active.
