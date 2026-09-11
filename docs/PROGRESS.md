# Project Progress — Source of Truth

**Project state:** IN PROGRESS
**Current milestone:** M22.1 — Telegram bot interface (implementation authorized; M21 pilot
observation continues independently)
**Last updated:** 2026-09-11

## Rules for Codex
- Read this file before every task.
- Work on the current milestone unless a prerequisite fix is needed.
- Change `[ ]` to `[x]` only after acceptance criteria and tests pass.
- Use `[~]` for in-progress and `[!]` for blocked.
- At the end of each task update `Last work log`, `Tests`, and `Current milestone`.
- Never put secrets here.

---

## M0 — Foundation / runnable skeleton
**Status:** [x] COMPLETE

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
**Status:** [!] BLOCKED / DEFERRED — Docker daemon available when

- [x] durable source-item idempotency before LLM work
- [x] provider-cost / configured-estimate / unavailable cost status
- [x] opt-in daily scheduler with configured local time and timezone
- [x] durable per-day scheduler claim to prevent restart double-runs
- [x] offline scheduler and repeated-run tests
- [!] rebuilt-container second manual-run verification — BLOCKED / DEFERRED: Docker CLI is
  installed but its daemon is unavailable in the current workspace. Run when Docker is available;
  do not enable a real provider or leave the scheduler enabled.
- [!] scheduler opt-in smoke verification (manual, explicit only) — BLOCKED / DEFERRED: requires
  the same local Docker runtime. Restore `SCHEDULER_ENABLED=false` immediately after the smoke.

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

**Known limitations / accepted risks:** Basic auth is single-operator rather than MFA/RBAC. OAuth
state and authentication/request limiters are memory-local for the single-process deployment.
Put production Admin behind VPN/identity-aware proxy where possible. Multi-replica deployment needs
shared OAuth state and limiting; adding Redis only for single-process V1 is explicitly deferred.

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
**Status:** [!] BLOCKED / DEFERRED — VPS ready when

- [x] offline production preflight remains covered: fail-closed settings, Admin/origin controls,
  source-fetch restrictions, Compose network/least-privilege topology, and generated migration SQL
- [x] production separates one-shot migration-owner and runtime-role DSNs; remote database TLS
  verifies hostname/certificate and supports an explicit CA file
- [x] encrypted pg_dump/age and checksum-verified isolated restore scripts/runbook are present
- [x] VPS runbook now sequences encrypted backup/isolated restore, startup/migration confirmation,
  TLS/Admin/health validation, M16 legacy-reader checking, and a scheduler-off default
- [x] M16 migration `20260908_0015` is explicitly included in the operational verification path
- [x] Hermes is documented as a separate orchestration layer with generic future domain API
  namespaces; direct DB, Gmail-token, OpenRouter-secret, and shell access remain prohibited
- [!] staging VPS backup and isolated restore observation — BLOCKED / DEFERRED: VPS ready when
- [!] runtime-role grant and remote PostgreSQL TLS observation — pending VPS validation
- [!] staging/production Compose startup, TLS proxy, authenticated Admin, health/readiness, and
  migration-revision observation — BLOCKED / DEFERRED: VPS ready when
- [!] explicitly approved controlled fresh-briefing verification, if a newly persisted Turkish
  snapshot is required — BLOCKED / DEFERRED: VPS ready when; never enable the scheduler or use
  providers implicitly
- [!] close M9 rebuilt-container second manual-run and explicitly enabled scheduler smoke
  observations, then reconcile the M9 status without duplicating provider work — BLOCKED / DEFERRED:
  Docker daemon available when

**Acceptance:** a staging or production operator records the safe checklist observations after a
tested backup/restore and confirms the hardened deployment, migration revision, and reader behavior
without exposing secrets or enabling unapproved live integrations. Offline evidence alone cannot
close this milestone. This milestone remains incomplete until the deferred observations are recorded.

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

## M21 — Source expansion and evals
**Status:** [~] IN PROGRESS

- [x] add a sanitized, offline golden quality dataset for gatekeeper, extractor, briefing, Search,
  fact/inference separation, and source prompt-injection contracts
- [x] keep deterministic assertions in pytest with no provider, mailbox, production-history, or
  external evaluator request
- [x] define an operator-approved 15-route RSSHub allow-list and an isolated, default-off Compose
  profile; normal RSS/YouTube, Gmail, OpenRouter, and scheduler paths remain outside it
- [~] persist aggregate-only route metrics (availability, latency, freshness, duplicates,
  retained candidates, and error rate); run the approved profile once daily for seven days and
  capture host-side RSSHub memory before the per-route `keep / disable / needs-auth` decision
- [x] add an explicit, separately budgeted manual provider-evaluation option with a sanitized
  Promptfoo-compatible configuration, separate scoped-key variable, one model, five cases,
  300-output-token cap, one-request-per-minute limit, and sharing disabled

**Acceptance:** quality regressions have an offline, sanitized baseline; an approved RSSHub pilot
improves source coverage without becoming a runtime dependency or lowering core availability.

**Pilot route findings (2026-09-10):** GitHub Trending is **needs-auth/deferred**: current route
`/github/trending/:since/:language/:spoken_language?` requires `GITHUB_ACCESS_TOKEN`, which this
pilot must not request or create. Current RSSHub upstream has no Reddit route namespace; Reddit is
excluded from this pilot.

---

## M22 — Notification delivery
**Status:** [x] COMPLETE

- [x] add a generic notification contract and an optional ntfy HTTP adapter
- [x] default the adapter to disabled and require HTTPS, a protected token, and explicit public-topic
  risk acknowledgement when using `ntfy.sh`
- [x] send only concise briefing-ready, actionable-mail, and operational-failure notices
- [x] use durable notification keys plus ntfy sequence IDs to suppress duplicate logical notices
- [x] use bounded timeout/retry and isolate delivery failure after ingestion/briefing persistence
- [x] run full offline regression and disposable-PostgreSQL migration/idempotency validation

**Acceptance:** duplicate scheduled/manual completion cannot produce duplicate delivery; notification
failure cannot roll back a persisted briefing or stop ingestion; disabled defaults make no request.

---

## M22.1 — Telegram bot interface
**Status:** [~] IN PROGRESS — offline implementation complete; VDS smoke test pending

- [x] add a disabled-by-default Telegram Bot API adapter without duplicating Search, Ask, briefing,
  interest, or notification business logic
- [x] use a production HTTPS webhook with Telegram's secret-token header; development polling, if
  added at all, must be explicit and must never run beside the webhook
- [x] require allow-listed numeric user and chat IDs before any command, model call, database read,
  feedback mutation, or audit write; `/start` must not self-enrol a user
- [x] support Turkish-first `/ozet`, `/ara <sorgu>`, `/sor <soru>`, and `/durum` commands through the
  existing bounded services; `/sor` must retain current OpenRouter budgets and source citations
- [x] add explicit feedback controls only through the existing stable interest-learning boundary;
  do not create unrestricted tasks, shell access, browsing, or general agent actions
- [x] optionally deliver the existing privacy-minimized notification kinds through Telegram with
  per-channel idempotency; never send email bodies, credentials, raw source text, or exception data
- [x] store the bot token and webhook secret only through absolute external secret files in
  production; redact Telegram identifiers/content from logs and keep audit metadata minimal
- [x] bound request size, message length, command/query length, concurrency, timeout, retry, and
  per-user/chat rate; deduplicate webhook updates durably by `update_id`
- [x] escape Telegram formatting and allow only validated HTTPS provenance/admin links; split long
  replies safely within Telegram message limits
- [x] add fake-transport unit/integration coverage with no live Telegram or paid-provider calls;
  update production Compose, environment examples, security notes, and VDS runbook
- [ ] complete an explicit VDS smoke test for webhook verification, unauthorized-user rejection,
  duplicate-update suppression, all approved commands, safe failure behavior, and restart recovery

**Acceptance:** only allow-listed identities can use the bot; duplicate Telegram updates cannot
repeat a model call or feedback action; approved commands return bounded, sourced results using the
canonical services; Telegram failure cannot affect ingestion/site availability; no secret or private
content appears in Git, logs, callback responses, or notification history.

---

## M20 — Full-article ingestion
**Status:** [x] COMPLETE

- [x] add a bounded HTML-only article fetcher with redirect-by-redirect source validation
- [x] parse already-fetched public HTML through Trafilatura; parsing cannot initiate network work
- [x] retain RSS metadata fallback when the page is inaccessible or not extractable
- [x] add article-body use only after the gatekeeper requests full extraction in all RSS paths
- [x] add representative extraction, redirect, MIME, response-size, freshness/dedup, and retry tests
- [x] document dependency review, operational limits, and removal path

**Acceptance:** representative fixtures remove navigation, advertisements, and boilerplate while
retaining useful article text; stale/duplicate/irrelevant items never fetch an article; fetch and
parse failures fall back safely without bypassing existing retry/post-LLM protections.

---

## M19 — Runtime knowledge quality
**Status:** [x] COMPLETE

- [x] persist embeddings for newly processed public events and claims through the configured
  `embedding` role
- [x] define model-dimension compatibility, migration, and re-embedding behavior before a model
  change
- [x] cluster multi-source coverage into one event while retaining every source provenance link
- [x] keep materially distinct but similar events separate
- [x] wire bounded correlation retrieval/runtime verification without sending full history or inbox
  data to a model
- [x] add fixture and disposable-PostgreSQL coverage for embedding persistence, corroboration,
  update/supersession, and unrelated-event rejection

**Acceptance:** semantic retrieval is non-neutral for newly processed public events; two sources
about one event create one event with two source links; similar but different events do not merge;
and correlation keeps claims and inferences separate with bounded context.

---

## Approved implementation sequence after M19

The detailed, updateable plan is `docs/OPEN_SOURCE_INTEGRATION_PLAN.md`. M20 and M22 are complete;
M22.1 is the authorized implementation milestone while the M21 observation-only pilot remains
open independently. Future milestones are planned and their scope must not be pulled into active
work.

- [x] **M20 — Full-article ingestion:** safe bounded article fetch plus Trafilatura extraction
- [~] **M21 — Source expansion and evals:** isolated RSSHub pilot plus sanitized promptfoo quality
  regression harness
- [x] **M22 — Notification delivery:** disabled-by-default, privacy-minimized ntfy adapter
- [ ] **M22.1 — Telegram bot interface:** allow-listed, webhook-based access to existing bounded
  briefing, Search, Ask, status, feedback, and notification services
- [ ] **M23 — Document ingestion:** isolated Docling boundary, only after explicit feature approval
- [ ] **M24 — User/mobile API and generated SDK:** stabilize the user API before OpenAPI Generator
- [ ] **M25+ — Tasks, mobile sync, and actions:** TaskService/Vikunja decision, then client sync and
  least-privilege MCP-compatible tools

**Sequencing rule:** M17 and linked M9 live observations remain deferred until the necessary
environment is available. M19 is authorized by the project owner; later integrations remain
removable adapters/services, and the existing database and domain model remain canonical.

---

## Backlog / explicitly out of current track
- [ ] Gmail Pub/Sub push/watch if polling latency becomes a real issue
- [ ] Audio download + STT fallback when no YouTube captions exist
- [ ] Discord integration; Telegram is now authorized separately as M22.1
- [ ] Qdrant migration only if pgvector scale proves inadequate
- [ ] browser automation for non-RSS/paywalled/dynamic sources
- [ ] Direct Reddit RSS decision: consider only as a separately approved `community/discovery`
  source tier; it must never be treated as verified news on its own and is not part of RSSHub M21.
- [ ] richer Q&A/chat over the knowledge base
- [ ] automatic source-quality learning
- [ ] task/reminder workflows, PC activity tracking, local model routing, and home-PC coding bridge
  (separate future scope; not part of AI Assistant M18)

## Blockers
None. Credentials are not required for offline tests or local defaults.

## Tests
- 2026-09-11: M22.1 callback completion validation: 209 passed, 0 skipped against a disposable
  PostgreSQL instance migrated through `20260911_0020`. The integration check verifies both
  Telegram tables and the channel-scoped notification primary key. Callback fake-transport tests
  cover acknowledgement, expiry/actor binding, one-use and duplicate-update suppression, plus
  Bot API error/timeout categories. Ruff, static Alembic SQL, synthetic Compose secret-mount
  resolution, and `git diff --check` passed. No live Telegram, VDS, provider, or user-data request
  was made.
- 2026-09-11: M22.1 final offline validation: 199 passed, 2 PostgreSQL-integration tests skipped
  because `SEARCH_INTEGRATION_DATABASE_URL` is unset. Ruff and generated Alembic SQL passed
  through `20260911_0020`. Coverage includes disabled/default settings,
  exact user/chat-pair authorization before persistence/model work, secret/content-type/body
  guards, duplicate update model suppression, transient retry, safe provider failures, and
  literal message splitting. No Bot API, OpenRouter, Gmail, source, scheduler, VDS, or user-data
  request was made. Explicit VDS webhook smoke remains required.
- 2026-09-11: Telegram M22.1 planning-only update; no runtime files changed and no tests were
  required. Implementation acceptance requires offline fake-transport coverage plus an explicit
  VDS webhook smoke test; neither is claimed by this planning entry.
- 2026-09-10: Final pre-VDS release validation: 190 passed, 0 skipped against a disposable
  pgvector PostgreSQL migrated through `20260910_0019`; Ruff, uv lock consistency, Alembic static
  SQL, synthetic production Compose resolution, production Docker image build, dependency audit
  (no known vulnerabilities), and `git diff --check` passed. Pytest and pytest-asyncio were moved
  to their compatible secure release lines; tracked test/lint caches were removed from Git.
  Live TLS, database-role grants, and encrypted backup/restore remain VPS acceptance work.
- 2026-09-10: Security remediation validation: 190 passed, 0 skipped against a disposable pgvector
  PostgreSQL migrated through `20260910_0019`; Ruff, uv lock consistency, Alembic head/static SQL,
  synthetic production and isolated RSSHub Compose configuration, dependency audit (no known
  vulnerabilities), and `git diff --check` passed. All external application integrations remained
  mocked/off; VPS TLS, live role grants, and real encrypted backup/restore remain pending VPS
  validation.
- 2026-09-10: Release QA: 167 passed, 0 skipped, with 2 upstream deprecation warnings against
  a uniquely named disposable PostgreSQL Compose project migrated through `20260910_0019`.
  Ruff passed with 0 errors; Alembic static SQL generation through `head`, production Compose
  configuration with synthetic environment values, and `git diff --check` all passed. No
  OpenRouter, Gmail, YouTube, RSSHub, ntfy, scheduler, VPS, or user-data request was made.
  Existing M21 day-1 pilot observations were not independently re-verified in this QA run, because
  the approved QA boundary forbids RSSHub or other external-service requests; they remain neither
  changed nor completion evidence for the seven-day pilot.
- 2026-09-10: M22 final validation: 167 passed, 0 skipped, 2 upstream deprecation warnings.
  Disposable local PostgreSQL migrated through `20260910_0019`; notification tests cover disabled
  defaults, protected ntfy configuration, sequence-ID retries, duplicate suppression, and isolated
  delivery failure. No ntfy, OpenRouter, Gmail, YouTube, RSS, scheduler, VPS, or user-data request
  was made.
- 2026-09-10: M21 Promptfoo-option validation: 8 focused offline tests passed. The committed
  configuration has five synthetic cases, source-data delimiters, static JSON assertions, no
  sharing, and a separate scoped-key name; no Promptfoo installation, provider, Gmail, source,
  RSSHub, YouTube, scheduler, VPS, or user-data call was made.
- 2026-09-10: M21 RSSHub pilot day 1: the explicit profile wrote 15 aggregate-only route
  observations. Eight routes were available; average available-route latency was 1030.1 ms; 114
  fresh/de-duplicated candidates were retained; 16 duplicate candidates were observed; seven routes
  returned safe failure categories. RSSHub host memory sample was 248 MiB / 512 MiB. No OpenRouter,
  Gmail, YouTube, scheduler, VPS, or user-data operation was run. The seven-day decision remains
  open.
- 2026-09-10: M21 day-one route diagnosis: RSSHub service logs show all six The Verge routes
  returning 503 (five provider parsing failures and one empty-route response); AP Top News returns
  503 after its upstream responds 403. These are recorded as pilot maintenance/availability
  evidence only. The approved route set remains unchanged until the seven-day review; no core
  source, provider, scheduler, Gmail, YouTube, or user-data operation changed.
- 2026-09-10: M21 RSSHub-pilot reporting validation: 6 offline tests passed. The read-only
  seven-day report correctly groups aggregate-only data by route, stream, and tier without
  refetching a source. Its first real report matched the 15 day-one observations; the current
  seven-day decision remains open.
- 2026-09-10: M21 RSSHub-pilot wiring validation: 5 offline tests passed and the isolated Compose
  profile resolved successfully before it was explicitly started. The pilot allows exactly 15
  approved routes, excludes the normal app/runtime, and records aggregate-only route health.
- 2026-09-10: M21 first-slice offline validation: 2 sanitized golden-evaluation tests passed.
  They verify required quality-contract coverage, forbid common credential/mail markers in the
  dataset, and retain prompt-injection text inside the extractor's untrusted source delimiter. No
  provider, RSSHub, promptfoo, Gmail, source, or user-data request was made.
- 2026-09-10: M20 final validation: 155 passed, 0 skipped, 2 upstream deprecation warnings.
  Disposable local PostgreSQL integration remained green. Article fixtures verify boilerplate
  removal, unsafe redirect/MIME/size rejection, bounded retry, metadata fallback, and no body
  request for stale/duplicate/irrelevant candidates. No live article, RSS, YouTube, Gmail,
  OpenRouter, scheduler, VPS, or user-data call was made.
- 2026-09-10: M20 RSS runtime wiring validation: 12 focused tests passed. The fixture verifies
  full-article text reaches extraction only after the gatekeeper signal, while fetch failure keeps
  the metadata fallback and records only the safe `article_fetch_error` category. No live request
  or provider call was made.
- 2026-09-10: M20 first-slice offline validation: 11 focused tests passed for safe article HTML
  extraction and RSS gating. Trafilatura `>=2.2,<3` was added as an Apache-2.0 parser for
  already-fetched public HTML; no live web, RSS, YouTube, Gmail, OpenRouter, scheduler, VPS, or
  user-data operation was run.
- 2026-09-10: M19 final validation: 145 passed, 0 skipped, 2 upstream deprecation warnings.
  Disposable local PostgreSQL was migrated through `20260909_0017`; its integration coverage
  verified current/legacy Search rows plus vector persistence and two-source corroboration. No
  OpenRouter, Gmail, YouTube, RSS, scheduler, VPS, user-data, or production call was made.
- 2026-09-10: M19 embedding/clustering offline validation: 140 passed, 1 skipped (dedicated
  PostgreSQL integration URL not configured), 2 upstream deprecation warnings. Ruff and generated
  Alembic SQL passed through `20260909_0017`. Added fixture coverage for corroborating
  multi-source event clustering and rejection of similarly named but distinct events. Docker was
  used only as an isolated test runner; no RSS, YouTube, Gmail, OpenRouter, scheduler, or VPS
  operation was run.
- 2026-09-09: M19 embedding first slice: added offline unit coverage for the dedicated OpenRouter
  embedding endpoint, deterministic response ordering, dimensionality validation, and cache reuse.
  The workspace currently has neither a Python/uv executable nor the prior `.venv`, so pytest,
  Ruff, and generated Alembic SQL could not be run; `git diff --check` passed. No provider,
  Docker, scheduler, source, Gmail, or VPS request was made.
- 2026-09-09: M17/M9 local-runtime availability check: Docker CLI is present but the Docker daemon
  is unavailable, so no container, provider, scheduler, or source run was attempted. `git diff
  --check` passed. VPS-dependent M17 observations and Docker-dependent M9 smoke checks are
  explicitly deferred; M19 is now active by project-owner decision.
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
- 2026-09-11: Completed the M22.1 callback acknowledgement boundary with bounded
  `answerCallbackQuery` delivery after every accepted feedback callback. Existing actor-bound,
  expiring one-use tokens and transactional feedback receipt remain intact; fake transport tests
  cover safe success, invalid/expired/other-actor, repeated-button, duplicate-update, API-error,
  and timeout paths. A disposable PostgreSQL database applied `20260911_0020` and passed the
  zero-skip suite; live VDS/Telegram smoke verification remains open.
- 2026-09-11: Implemented the offline M22.1 Telegram boundary. It uses direct bounded Bot API
  calls, a secret-verified HTTPS webhook, exact user/chat-pair authorization, durable update
  receipts, transaction-safe one-use feedback tokens, and plain-text safe replies over canonical
  briefing/Search/Ask services. Telegram notifications now use channel-scoped idempotency beside
  ntfy. Production secret mounts, VDS setup/smoke instructions, and the Telegram threat model are
  documented; live Telegram/VDS verification remains open and no external call was made.
- 2026-09-11: Authorized and specified M22.1 as the next implementation milestone. Telegram is an
  allow-listed user interface over canonical services, not a second assistant stack; production
  uses a secret-verified HTTPS webhook and all live Telegram/VDS evidence remains pending.
- 2026-09-10: Prepared the security-remediated tree for VDS staging: refreshed the locked test
  toolchain after a current dependency audit, confirmed the production image builds, and removed
  generated pytest/Ruff caches from version control. No VDS connection or external application
  integration was attempted; VPS-specific M17/M9 acceptance remains open.
- 2026-09-10: Applied the accepted P1/P2 production security remediations locally: immutable
  dependencies/images and deny-by-default build context; pre-audit auth/request limits; trusted
  proxy, SSRF/redirect/peer and YouTube URL boundaries; runtime/migration DB split and verifying
  TLS; opt-in retention; conservative claim grounding and hostile-feed bounds; PKCE/POST-only OAuth,
  nonce CSP, stricter secret/ntfy/log/link handling, RSSHub network isolation, and encrypted
  backup/restore tooling. Single-process limiting is an accepted risk; multi-replica sharing and
  every real VPS/TLS/backup acceptance item remain deferred.
- 2026-09-10: Release QA corrected ten Ruff line-length errors without changing runtime behavior.
  The full offline suite passed against a uniquely named migrated disposable PostgreSQL instance;
  production Compose resolved with synthetic values. M19–M22 runtime wiring was exercised by its
  focused and full regression coverage with no additional reproducible runtime bug found. M21
  remains in progress: its existing day-1 pilot observations were not re-verified in this QA run
  and do not complete the required seven-day decision.
- 2026-09-10: Started M21 Source expansion and evals. Added a normal-pytest synthetic/public-style
  golden dataset for core quality contracts and a prompt-injection boundary regression. Promptfoo
  remains deliberately uninstalled and manual because its configuration can execute trusted local
  code; no paid or model-graded evaluation is enabled. RSSHub remains disabled pending an explicit
  10–20 route allow-list and isolated-pilot operating decision.
- 2026-09-10: Completed M20 Full-article ingestion. The application owns bounded public HTML
  retrieval and validates every redirect before Trafilatura parses the received bytes. Normal and
  explicit-retry RSS paths use the same policy; failures preserve the metadata path and existing
  post-LLM protections. M21 is now active; no source expansion or model evaluation implementation
  has begun.
- 2026-09-10: Extended M20 through the normal and explicit-retry RSS paths. Both now receive the
  configured bounded article fetcher. Full extraction uses article text only after the gatekeeper
  requests it; inaccessible pages retain the feed-snippet input and a safe operational category.
  MIME/size and broader retry fixture coverage remain open.
- 2026-09-10: Started M20 Full-article ingestion. Added a bounded HTML-only fetcher with the
  existing redirect-by-redirect public-address validation, timeout/retry/response limits, and
  MIME checks. Trafilatura parses only the received response; an inaccessible or low-quality page
  safely falls back to feed metadata. RSS invokes it only after the gatekeeper requests full
  extraction. Remaining M20 coverage and all-path runtime wiring are still open.
- 2026-09-10: Completed M19 Runtime knowledge quality. Newly extracted compact public event and
  claim text is embedded through the configured role with model/dimension binding; re-embedding is
  explicit and bounded. Conservative clustering retains each source link, and RSS correlation
  retrieves at most 50 same-entity candidates before passing at most five compact records to the
  reasoner; invalid links/evidence are rejected and inferences remain separate. The disposable
  PostgreSQL suite passed with no skipped tests. M20 is now active; no M20 implementation began.
- 2026-09-10: Extended M19 with conservative deterministic event clustering. A new source may join
  a recent event only when title, normalized entity, and (where needed) source-backed claim overlap
  meet the threshold; it is then stored as `corroborating` provenance and metadata is merged rather
  than replaced. Ambiguous or materially distinct coverage remains separate. The runtime embedding
  first slice and clustering are covered offline; re-embedding and bounded correlation runtime
  wiring remain in progress.
- 2026-09-09: Started M19 Runtime knowledge quality. The first slice adds a bounded, cached,
  budget-accounted OpenRouter embedding path for compact event/claim text only; migration
  `20260909_0017` records model IDs and dimensions with event/claim vectors. Search now attempts
  semantic reranking only after deterministic candidates exist and only for matching
  model/dimension rows. Re-embedding, clustering, and correlation runtime wiring remain open.
- 2026-09-09: The project owner deferred M17's VPS/TLS/production observations until a VPS exists
  and deferred M9's rebuilt-container/scheduler smoke until the local Docker daemon is available.
  Docker CLI was found but could not connect to its daemon, so no local containers, live sources,
  provider calls, or persistent scheduler change occurred. M17 remains incomplete; M19 Runtime
  knowledge quality is now the authorized active milestone.
- 2026-09-09: Approved and documented the post-M17 implementation sequence in
  `docs/OPEN_SOURCE_INTEGRATION_PLAN.md`. The plan prioritizes runtime embeddings, event
  clustering, full-article extraction, measured source expansion/evals, and privacy-minimized
  notification delivery before document/mobile/task/action features. External repositories remain
  removable adapters, libraries, isolated services, or references; no runtime dependency or code
  change was introduced. Reconciled M0's stale status and set M17 as the active milestone because
  its staging/production evidence and linked M9 manual checks remain open.
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
