# Project Progress — Source of Truth

**Project state:** IN PROGRESS
**Current milestone:** M22.2 remaining Telegram/budget/timing and CI repairs authorized; summary review active;
M22.3 operator acceptance; M22.4 planned (M21 RSSHub observation deferred)
**Last updated:** 2026-09-26
**Completion estimate:** withheld until operator acceptance; implemented and planned work are listed
below

The system turns fresh RSS, YouTube, and read-only Gmail signals into a short sourced briefing,
keeps event memory, and exposes controls through Admin and Telegram. The VDS app, database, and
poller were rebuilt and passed basic health checks. The user reported M22.2 output and feedback
defects on 2026-09-26; live acceptance is not complete. M22.4 category-first source onboarding is
only a plan. See those milestones below
for the exact boundary; dated test and work logs are historical evidence.

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
**Status:** [~] DEFERRED — remaining live provider/scheduler checks need a controlled run

- [x] durable source-item idempotency before LLM work
- [x] provider-cost / configured-estimate / unavailable cost status
- [x] opt-in daily scheduler with configured local time and timezone
- [x] durable per-day scheduler claim to prevent restart double-runs
- [x] offline scheduler and repeated-run tests
- [~] rebuilt-container second manual-run verification — deferred until a controlled live provider
  run; Docker availability is no longer the blocker
- [~] scheduler opt-in smoke verification — deferred until a controlled live run; restore
  `SCHEDULER_ENABLED=false` immediately after the smoke if it was enabled only for the check

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
- [x] early wakeups retry the same local-day target until due or durably claimed
- [x] a shared non-queuing coordinator makes concurrent manual/scheduled runs skip rather than
  overlap provider work
- [x] empty/no-new-item runs retain zero provider/editor work and do not create a briefing
- [x] Admin shows enabled state, timezone, next run, current-process status/skip/error, and durable
  scheduled-run history without source payloads or secrets

**Acceptance:** with scheduling explicitly enabled, a single local-day scheduled claim survives
restart and prevents a second briefing/LLM run; an early wakeup cannot advance past an unclaimed
local day. A concurrent manual run is safely skipped or the scheduled attempt records an active-run
skip. Empty runs create neither a briefing nor an editor call.

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
**Status:** [x] COMPLETE — all architecture-applicable production, recovery, and reader observations
verified

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
- [x] production encrypted backup and isolated restore observation: PG17 custom dump encrypted with
  a permanent off-host age identity, checksum verified off-host, and restored into a disposable
  network-disabled tmpfs PostgreSQL container without copying the private identity to the VPS.
  Schema/migration/count checks matched production; the plaintext archive and restore target were
  removed while encrypted backup copies and the public recipient were retained
- [x] production runtime-role observation: app and Telegram poller use dedicated
  `intelligence_runtime` sessions rather than the migration/admin role; the role is login-only,
  owns no objects, has no role memberships or database/schema creation rights, has documented CRUD
  table and sequence grants, and has no elevated table grants. The previously shared runtime/admin
  configuration was corrected and affected credentials were rotated without exposing replacement
  values
- [x] database TLS applicability observed without changing architecture: production uses local
  Compose PostgreSQL on an internal-only Docker network with no published database port, so remote
  hostname/certificate TLS is not applicable. The documented `verify-full`/CA path remains
  unexercised and becomes required only if production moves to remote/managed PostgreSQL
- [x] architecture-applicable deployment checklist observed: only SSH is publicly listening; UFW
  defaults to deny inbound and permits only SSH; app port `8000` is loopback-only; no TLS proxy is
  installed; health/readiness return `200`; unauthenticated Admin returns `401`; invalid Host returns
  `400`; docs/OpenAPI return `404`; Admin responses carry no-store, CSP, frame, referrer, and
  nosniff headers. Authenticated Control Center and POST behavior through the documented SSH tunnel
  were already verified. Internet-facing TLS proxy forwarding is not applicable to this SSH-only
  deployment
- [x] explicitly approved single fresh-briefing observation: one manual run fetched 20 RSS items,
  processed 7, made 35 provider calls, persisted 7 events and one new briefing, and left scheduler
  disabled. Three gatekeeper failures and one YouTube caption-access failure were isolated safely;
  briefing render/persistence had no failures. The new structured briefing rendered one sourced
  card with Turkish summary and `Ne değişti`; viewing it made no additional provider call
- [x] M17 scheduler-off requirement observed after the manual run. The rebuilt-container second-run
  and explicitly enabled scheduler smoke remain separate M9 acceptance work and are not an M17
  blocker

**Acceptance:** a staging or production operator records the safe checklist observations after a
tested backup/restore and confirms the hardened deployment, migration revision, and reader behavior
without exposing secrets or enabling unapproved live integrations. Core deployment observations are
now recorded and all checks applicable to the current architecture are complete. This milestone
is complete. Remote database TLS becomes acceptance work only if that architecture is adopted.

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
**Status:** [~] IN PROGRESS — fresh isolated RSSHub pilot Day 1 of 7 recorded; route decision pending

- [x] add a sanitized, offline golden quality dataset for gatekeeper, extractor, briefing, Search,
  fact/inference separation, and source prompt-injection contracts
- [x] keep deterministic assertions in pytest with no provider, mailbox, production-history, or
  external evaluator request
- [x] define an operator-approved 15-route RSSHub allow-list and an isolated, default-off Compose
  profile; normal RSS/YouTube, Gmail, OpenRouter, and scheduler paths remain outside it
- [~] persist aggregate-only route metrics (availability, latency, freshness, duplicates,
  retained candidates, and error rate); run the approved profile once daily for seven days and
  capture host-side RSSHub memory before the per-route `keep / disable / needs-auth` decision.
  Fresh pilot Day 1/7 ran on 2026-09-21; do not combine it with the stale 2026-09-10 observation
- [x] add an explicit, separately budgeted manual provider-evaluation option with a sanitized
  Promptfoo-compatible configuration, separate scoped-key variable, one model, five cases,
  300-output-token cap, one-request-per-minute limit, and sharing disabled

**Acceptance:** quality regressions have an offline, sanitized baseline; an approved RSSHub pilot
improves source coverage without becoming a runtime dependency or lowering core availability.

**Pilot route findings (2026-09-10):** GitHub Trending is **needs-auth/deferred**: current route
`/github/trending/:since/:language/:spoken_language?` requires `GITHUB_ACCESS_TOKEN`, which this
pilot must not request or create. Current RSSHub upstream has no Reddit route namespace; Reddit is
excluded from this pilot.

**Fresh pilot Day 1 findings (2026-09-21):** 7/15 routes were available. Apple Security Releases,
AP Top News, and all six The Verge routes recorded safe `ProviderError` failures; all six Hacker News
routes and Epic Free Games were available. This is observation-only evidence, not a keep/disable/
needs-auth decision.

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
**Status:** [x] COMPLETE — production safety/recovery smoke passed after the no-match retrieval fix

- [x] add a disabled-by-default Telegram Bot API adapter without duplicating Search, Ask, briefing,
  interest, or notification business logic
- [x] use a production HTTPS webhook with Telegram's secret-token header; development polling, if
  added at all, must be explicit and must never run beside the webhook
- [x] require allow-listed numeric user and chat IDs before any command, model call, database read,
  feedback mutation, or audit write; `/start` must not self-enrol a user
- [x] support Turkish-first `/ozet`, `/ara <sorgu>`, `/sor <soru>`, and `/durum` commands through the
  existing bounded services; `/sor` must retain current OpenRouter budgets and source citations
- [x] expose bounded Turkish help, briefing history, persisted source add/list/disable, and stable
  interest list/add/remove controls through the same allow-listed command boundary
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
- [x] verify the deployed polling worker and Telegram command responses; production has 6 managed
  sources, 2 enabled
- [x] complete the explicit VDS safety/recovery smoke: unauthorized identities, duplicate-update
  suppression, restart recovery, temporary Telegram failure isolation, and safe approved-command
  behavior all passed in production; no-match and positive-match Search behavior were re-tested
  after deployment of `44c7e70`

**Acceptance:** only allow-listed identities can use the bot; duplicate Telegram updates cannot
repeat a model call or feedback action; approved commands return bounded, sourced results using the
canonical services; Telegram failure cannot affect ingestion/site availability; no secret or private
content appears in Git, logs, callback responses, or notification history.

---

## M22.2 — Scheduled Telegram daily assistant
**Status:** [~] DEPLOYED — summary under review; remaining reported repairs assigned with evidence gates

- [x] keep the existing daily scheduler, normal RSS/YouTube/Gmail runtime, coordinator, durable
  briefing outbox, and channel-scoped notification dispatcher
- [x] deliver the newly persisted briefing through the existing `/ozet` renderer after a non-empty
  run; empty runs do not notify
- [x] preserve briefing/ingestion state when Telegram delivery fails and reuse notification
  idempotency when a failed delivery is explicitly submitted again; automatic replay of a prior
  failed briefing is not implemented
- [x] ask up to three metadata-derived interest questions during the first 14 successfully
  delivered local briefing days, using one-use existing Telegram feedback tokens
- [x] apply calibration answers as bounded adaptive signals without an additional model call
- [x] add migration, regression tests, configuration examples, and the production runbook steps
- [ ] operator verifies the configured local delivery time, Telegram notification destination,
  and performs
  the first controlled production smoke after checking any persisted Control Center scheduler
  preference (which overrides environment values)
- [x] close a conditional production source-fetch proxy boundary found in the 2026-09-25
  security pilot: direct egress confirmed, narrow RSS/article client fix and proxy-environment
  negative test passed offline, and independent review found no blocking issue
- [~] diagnose the 2026-09-25 safe-error alert and why the 14:00 daily delivery arrived around
  14:08: scheduled time was the work start, not send time; safe counts confirm four RSS and two
  YouTube failures, but the historical categories and actual start timestamp are unavailable.
  Future runs persist bounded category counts without source/provider/Telegram content or secrets
- [~] send a concise Turkish editorial briefing with clear sections, meaningful developments,
  reasons to care, and source links instead of repeated raw title/summary/change blocks; focused
  local tests passed, but the 2026-09-26 user report shows separate cards, English, and technical
  field labels. Acceptance requires one short daily message, not a series of article summaries
- [~] investigate invalid first-14-day Yes/No feedback: check shared state between the application
  and poller, expiry, identity binding, consumption, and restart behavior. Tokens are DB-backed;
  first-click cause remains unproven, with a conditional shared-chat actor mismatch found by review
- [x] make first-14-day feedback ask about concrete subjects such as Google Photos features or
  Waymo developments, not publishers, feeds, event names, or duplicate labels; focused negative
  fixtures and independent review passed, production output still pending
- [x] separate pre-delivery processing from the configured local delivery target, starting
  preparation 15 minutes before it; preserve durable idempotency and a deterministic time-bound
  regression. If fresh content is not ready at the configured delivery time, deliver it when ready
  with an explicit delay; do not present an old briefing as new. Offline tests and independent
  review passed; production delivery remains unverified

**Scope note:** M21 RSSHub work is not a prerequisite and was not continued.

---

## M22.3 — Source management UI and automatic categorization
**Status:** [~] DEPLOYED — PostgreSQL accepted; Telegram runtime acceptance pending

- [x] keep the Sources table usable with many entries and long endpoints at desktop and narrow
  widths; 12-long-URL fixture and headless Chrome desktop/500px layout check passed for both source
  screens. A separate non-source table on `/admin` still extends document width by 85px at 500px
- [x] edit an existing source's name, endpoint, topic/category, and relevant source settings through
  the same validated database-backed path as creation; preserve stable identity and ingestion history
- [x] assign a meaningful source topic/category automatically on add, beyond the current
  `tech/world/personal` presentation, while keeping the result visible and user-correctable;
  if deterministic metadata is ambiguous, ask the allow-listed operator through Telegram and
  persist the answer instead of calling a model; Admin-created questions go only to one
  configured operator chat that is also on the exact user/chat allow-list
- [x] retain World in Brief independence, source authorization/URL guards, canonical duplicate
  checks, disabled-by-default creation, and no unrequested live provider calls in offline checks
- [x] run the full suite against a disposable migrated pgvector/PostgreSQL container: 345 passed,
  none skipped or failed; Alembic head `20260923_0028`, Ruff, compileall, and offline SQL passed.
  The temporary container was removed. Live Telegram and VDS checks remain pending

**Acceptance:** a fixture with many long-URL sources remains operable; edit and automatic category
selection pass focused Admin/repository tests without losing existing source state. An ambiguous
source creates one bounded, authorized Telegram category question and its answer updates only that
source; no model call or duplicate question is made.

---

## M22.4 — Category-first source onboarding
**Status:** [ ] PLANNED — no implementation or acceptance claimed

- [ ] For one RSS feed or YouTube channel added in Telegram, identify the source by name and ask
  for its category before it begins following; offer built-in and previously created categories
  plus free-form entry for a new category
- [ ] For OPML import, take per-feed categories from the file or collect missing choices as part
  of import; do not create a stream of UUID-only questions after import
- [ ] Keep category separate from the `tech`/`world` editorial stream and preserve source URL,
  authorization, duplicate, disabled-source, and bounded-import guards
- [ ] Replace the current background UUID-only category question path only after the new single
  and bulk flows cover existing pending sources without losing user choices
- [ ] Verify the Telegram interaction, OPML round trip/preview, restart behavior, and authorized
  negative paths with focused tests before controlled VDS acceptance

Current behavior: known source domains receive deterministic categories; unknown sources are
created disabled and later queried by UUID in bounded batches. The user's reported cadence is
consistent with the bounded queue, not an asserted Telegram messages-per-minute limit.

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

The detailed, updateable plan is `docs/OPEN_SOURCE_INTEGRATION_PLAN.md`. M20, M22, and M22.1 are
complete; the M21 observation-only pilot remains open independently. Future milestones are planned
and their scope must not be pulled into active work.

- [x] **M20 — Full-article ingestion:** safe bounded article fetch plus Trafilatura extraction
- [~] **M21 — Source expansion and evals:** isolated RSSHub pilot plus sanitized promptfoo quality
  regression harness
- [x] **M22 — Notification delivery:** disabled-by-default, privacy-minimized ntfy adapter
- [x] **M22.1 — Telegram bot interface:** allow-listed production polling, safe commands, duplicate
  suppression, restart recovery, and Telegram failure isolation verified
- [ ] **M23 — Document ingestion:** isolated Docling boundary, only after explicit feature approval
- [ ] **M24 — User/mobile API and generated SDK:** stabilize the user API before OpenAPI Generator
- [ ] **M25+ — Tasks, mobile sync, and actions:** TaskService/Vikunja decision, then client sync and
  least-privilege MCP-compatible tools

**Sequencing rule:** M17 production operations acceptance is complete. M9 scheduler observations
remain separate and must not be inferred from M17's scheduler-off checks. M21 is the active
observation milestone; later integrations remain removable adapters/services, and the existing
database and domain model remain canonical.

---

## Backlog / explicitly out of current track
- [~] **Optimization baseline (approved):** fixture-only performance and retrieval-quality gates
  are defined in `docs/OPTIMIZATION_BASELINE.md`; implementation begins only with a measured,
  reversible improvement and preserves the current PostgreSQL/pgvector architecture.
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
No active M17 or M22.1 blocker. Remaining open work is M22.2 production enablement, M21 observation,
and separate deferred M9 scheduler acceptance. Remote PostgreSQL TLS and an internet-facing TLS
proxy become acceptance work only if those architectures are adopted.

## Tests
- 2026-09-26: Separate reviewer task completed read-only investigation: 23 selected offline tests
  and Ruff passed. Confirmed separate-card rendering and unused final-editor helper; DB-backed
  feedback tokens disprove the process-local-storage hypothesis. No production or remote CI log
  was read; GitHub Actions needs safe run/job/step evidence. No code files were changed.
- 2026-09-26: Agent-role documentation was checked for required mission/work/boundary/report
  sections, existing role-file references, and whitespace. Documentation only; no code tests,
  provider calls, server inspection, or Telegram investigation were performed.
- 2026-09-25: Documentation-only review reconciled project purpose, active versus historical
  entrypoints, current Telegram/OPML behavior, deployed health evidence, and planned M22.4 scope.
  No application code or live service was changed; Markdown links and whitespace were checked.
- 2026-09-25: Headless Chrome rendered `/admin` and `/admin/sources/ui` with 12 long RSS URLs and a
  YouTube row from TestClient fakes. Desktop source cells wrapped; at 500 CSS px each source table
  scrolled locally and edit/save/status controls remained reachable. Chrome CLI could not produce a
  390 CSS px viewport. `/admin` has an adjacent unrelated table causing 85px page overflow at 500px.
  Temporary screenshots were removed; no live data or provider call was used.
- 2026-09-25: VDS checkout updated and the production Compose app/poller rebuilt with the existing
  deployment overlay and protected environment. App/database health and local `/health` returned
  success by exit-code-only checks; deployment log content was left for the operator to inspect.
  Telegram delivery, source editing, and timed briefing behavior remain operator acceptance work.
- 2026-09-25: Docker-enabled release gate: fresh disposable pgvector/PostgreSQL migrated to
  `20260923_0028`; 345 tests passed, none skipped or failed. Three stale migration assertions and
  one source-delete fixture expectation were updated to match current schema/disabled-by-default
  behavior. Ruff, compileall, offline Alembic SQL, and diff check passed; container removed.
- 2026-09-25: Integrated offline release gate after M22.2/M22.3: 339 passed, 6 skipped
  (disposable PostgreSQL integration tests), zero failed; Ruff, compileall, Alembic single head
  `20260923_0028`, offline migration SQL, and `git diff --check` passed. Independent focused
  review accepted pending-source replay and import coverage (68 passed). No real browser layout,
  PostgreSQL acceptance, VDS, provider, or Telegram delivery test was performed.
- 2026-09-25: M22.2 presentation/calibration tests passed with independent review. Timing and
  safe-error regressions cover arbitrary configured delivery time, 15-minute lead, late delivery,
  midnight and DST transitions, sequential notice order, safe counters and RSS health-record
  failures. Focused scheduler/RSS follow-up: 29 passed; earlier scheduler/Telegram/RSS/YouTube/Admin
  set: 97 passed. Independent reviewer accepted the final DST and RSS fixes. No VDS, live provider,
  or real Telegram delivery acceptance was performed.
- 2026-09-25: Proxy-environment regression failed before the narrow source-fetch fix and passed
  afterward. Security implementer: 4 focused SSRF/article tests, Ruff, and `git diff --check`
  passed. Independent reviewer: 9 proxy/outbound/article tests and 13 RSS runtime tests passed;
  no blocking findings. No live source, provider, or VDS test was performed.
- 2026-09-24: Deterministic scheduler boundary regression reproduced an early wake crossing the
  Istanbul 14:00 deadline and verified retries plus consecutive local-day claims. Scheduler/Admin
  tests: 36 passed. Full offline suite: 310 passed, 6 PostgreSQL integration skips, and 2 upstream
  deprecation warnings. Ruff, compileall, and `git diff --check` passed.
- 2026-09-23: M22.2 release-targeted offline regressions passed: 45 tests covering Telegram,
  calibration, notifications, scheduler, RSS runtime, and briefing behavior, with 2 upstream
  deprecation warnings. Ruff, compileall, Alembic head/SQL generation, and `git diff --check` passed.
  The full offline suite had previously passed: 308 passed, 6 opt-in PostgreSQL skips, and 2
  upstream deprecation warnings. A fresh full-suite rerun stops at the first TestClient test because
  the installed Starlette/httpx/anyio stack hangs even for a bare FastAPI app; no Telegram, source,
  Gmail, database, or provider request was made.
- 2026-09-21: M21 fresh isolated RSSHub pilot Day 1/7: the unique local Compose project ran only the
  explicit 15-route profile with normal app suppressed, scheduler/Gmail disabled, and OpenRouter
  empty. It persisted aggregate-only observations: 7/15 available (46.67%), 435.9 ms mean available
  route latency, 87 fresh/retained candidates, 6.98% duplicate rate, and 53.33% maintenance error
  rate. Apple Security Releases, AP Top News, and six The Verge routes recorded `ProviderError`;
  six Hacker News routes and Epic Free Games were available. RSSHub memory was 165.5 MiB before and
  247.4 MiB after the run, within its 512 MiB limit. No provider, Gmail, scheduler, normal runtime,
  production Compose, source promotion, or final route decision was used.
- 2026-09-20: Closed M17 after permanent off-host age recovery validation. Generated the private
  identity only on the trusted operator workstation outside the repository and encrypted-backup
  tree, mode `600`; provisioned only its public recipient on the VPS. A fresh production PG17 custom
  dump was encrypted directly to that recipient, copied off-host with its checksum, checksum-checked,
  and decrypted off-host to a valid `PGDMP` archive. The decrypted stream crossed SSH without the
  identity and was restored only into a network-disabled, tmpfs-backed disposable PG17 container.
  Restore checks matched revision `20260914_0027`, 34 public tables, 31 events, 8 briefings, 150 LLM
  calls, 26 Telegram updates, and 6 managed/2 enabled sources. The disposable container, plaintext
  archive, and restored database were removed; encrypted off-host/VPS backups and the public
  recipient remain. Production app/database stayed healthy. No ingestion, scheduler, Telegram,
  migration, provider, or live-database write was triggered.
- 2026-09-20: Completed the architecture-applicable M17 deployment and fresh-briefing observations.
  The VPS exposed only SSH; UFW was active with default-deny inbound; app remained loopback-only;
  PostgreSQL had no published port; and no reverse proxy was installed. Health/readiness returned
  `200`, unauthenticated Admin `401`, invalid Host `400`, docs/OpenAPI `404`, and Admin returned the
  expected no-store/CSP/frame/referrer/nosniff headers. One explicitly approved manual run fetched
  20 RSS items, processed 7, made 35 provider calls, persisted 7 events and one new briefing, and
  completed with three isolated gatekeeper failures plus one safe YouTube caption-access failure.
  The new briefing had one structured content row with title, Turkish summary, `Ne değişti`, and a
  source link; render/persistence failures were zero. Viewing it left `llm_calls=150`, confirming no
  read-time provider call. Scheduler stayed disabled; app remained healthy and Telegram polling
  running. No second ingestion run was attempted.
- 2026-09-20: M17 production database-role validation found app, poller, and migration configured
  with the same `postgres` superuser. Applied the existing `ops/bootstrap-database-roles.sql` source
  of truth to create `intelligence_runtime`, then verified `NOSUPERUSER`, `NOCREATEDB`,
  `NOCREATEROLE`, `NOINHERIT`, `NOREPLICATION`, login-only status, database `CONNECT`, schema
  `USAGE` without `CREATE`, complete documented CRUD/sequence grants, zero elevated table grants,
  zero owned objects, and zero role memberships. Recreated only app/poller with scheduler,
  managed-source bootstrap, and Gmail disabled; `/health` and `/ready` passed and two live
  application sessions used `intelligence_runtime`. A credential exposed during the operator drill
  was rotated; replacement values were not logged, migration login succeeded, Compose/migration
  credentials matched, and secret/config modes were `600`. TLS observation recorded the actual
  topology: internal-only Docker database network, no published PostgreSQL port, server SSL off,
  and two non-TLS runtime sessions. No ingestion, scheduler run, Telegram command, migration,
  provider call, or application behavior change was triggered.
- 2026-09-20: M17 production backup/restore validation passed without provider, ingestion, scheduler,
  Telegram, or live-database writes. A PG17 custom dump was encrypted with a temporary age key and
  checksum-verified; archive inspection found 179 entries, 68 table definitions, and 34 table-data
  entries. Restore into an isolated disposable PostgreSQL container completed successfully. Isolated
  and production checks matched: 34 public tables, Alembic revision `20260914_0027`, `events=24`,
  `telegram_updates=26`, and `llm_calls=115`. The temporary age key, encrypted/plaintext drill
  artifacts, container, and internal network were removed. Long-term off-host key management was not
  validated.
- 2026-09-20: M22.1 production acceptance completed after deploying `44c7e70`: unauthorized
  group identity rejection, duplicate-update idempotency, polling offset continuity across restart,
  Telegram network-failure isolation, bounded command behavior, and the controlled `/sor` check
  passed. `/ara qzv-unique-smoke-2026` and `/ara AMD` safely returned insufficient sources, while
  `/ara Moonshot` returned two matching retained events. No ingestion was triggered; the single
  `/sor` verification was the intentional provider-backed smoke call.
- 2026-09-20: M22.1 VDS safety/recovery smoke partially passed: an unauthorized group chat was
  rejected without changing `telegram_updates`/`llm_calls`; controlled duplicate replay was
  idempotent; polling offset remained continuous across a poller restart; disconnecting only the
  poller's secondary network left app health/readiness and the poller healthy; and bounded `/yardim`
  plus authorized `/durum` responses worked. The smoke found a real no-match search regression:
  `/ara qzv-unique-smoke-2026` returned unrelated existing results rather than a safe insufficient-
  sources response, with no LLM call. The subsequent `44c7e70` deployment and positive-match
  verification completed M22.1.
- 2026-09-20: Added the minimal shared-retriever guard and regression test for zero-score events;
  `tests/test_search.py` passed (9 passed) and Ruff passed. The full suite was attempted but hung at
  `tests/test_admin.py::test_admin_run_callback` and was stopped; no provider or ingestion work was
  triggered.
- 2026-09-20: Verified production state after deploying `6ed822a`: app and database healthy;
  migrations completed successfully; Telegram polling is running and commands work; the Control
  Center works through the documented SSH tunnel; production contains 6 managed sources with 2
  enabled; Memory Search POST returned HTTP 200; and an authenticated wrong-origin POST returned
  HTTP 403 as expected. No new feature implementation or scheduler/provider-triggering run was
  performed.
- 2026-09-14: Control Center smoke-regression validation: 51 focused Admin/security tests passed.
  Dashboard Telegram status now recognizes the separate polling deployment from non-secret mode
  state, and authenticated POST forms accept only the exact documented `http://localhost:8000`
  SSH-tunnel origin when configured as `https://localhost`; wrong origins and ports remain 403.
- 2026-09-14: Merge reconciliation validation: focused Telegram/RSS/Admin/Scheduler/Onboarding tests
  passed (69 passed, 1 PostgreSQL integration test skipped without a disposable URL); conflict
  markers are gone and DB-managed source callbacks remain the runtime path. Full offline, Ruff,
  and merge-diff checks remain the final gate for this merge.
- 2026-09-13: Security completion validation: 236 passed, 3 dedicated PostgreSQL integration tests
  skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset; Ruff and `git diff --check` passed.
  Locked dependency audit and `pip check` passed. Source/briefing/LLM/Admin security regressions
  cover inline URL credentials, local-only rendered links, gatekeeper delimiter closure, atomically
  written source configuration, and provider-error privacy. Base, webhook, and outbound-polling
  production Compose files resolved with synthetic secret paths. No source, provider, Gmail,
  Telegram, VDS, or user-data request was made.
- 2026-09-13: Provider-error privacy validation: 84 focused tests passed, Ruff passed. OpenRouter
  4xx logs preserve only status/model and safe compact code/type metadata; provider error messages
  are never logged, including when they contain a credential-shaped value. No provider, source,
  Gmail, Telegram, VDS, or user-data request was made.
- 2026-09-12: Security boundary and diagnostics validation: 234 passed, 3 dedicated PostgreSQL
  integration tests skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset. Process-local
  rate-limit state is bounded against synthetic client-key floods; all application responses,
  including authentication rejections, carry hardened headers and a server-generated correlation
  ID. Safe Agent API/Telegram failure categories are logged without request, command, secret, or
  provider-error content. Ruff and `git diff --check` passed. A live `pip-audit` check could not
  produce a clean result because the local editable project is not published on PyPI; this is not
  treated as a successful dependency-vulnerability audit. No source, provider, Gmail, Telegram,
  VDS, or user-data request was made.
- 2026-09-12: Optimizer conditional-RSS-cache validation: 19 focused tests passed, Ruff and
  generated Alembic SQL passed. ETag/Last-Modified validators are persisted as non-sensitive
  source-health metadata; a 304 skips feed parsing and all downstream work. No source, provider,
  Gmail, Telegram, or user-data request was made.
- 2026-09-12: Optimizer RSS metadata concurrency validation: 16 focused tests passed and Ruff
  passed. Enabled RSS sources now fetch metadata through a configurable bounded semaphore (default
  3), while freshness, deduplication, event persistence, briefing writes, and provider work remain
  deterministic and sequential. No source, provider, Gmail, Telegram, or user-data request was
  made.
- 2026-09-12: Optimizer baseline observation: a disposable PostgreSQL 17/pgvector database was
  migrated through `20260912_0022`. A rolled-back transaction with 5,000 synthetic events measured
  the current 180-day, newest-first 100-row candidate query at 1.845 ms via `EXPLAIN (ANALYZE,
  BUFFERS)`; no vector index was added because this is not a demonstrated bottleneck. A separate
  100,000-row rolled-back LLM-ledger query used the existing `ix_llm_calls_created_at` index and
  completed in 0.997 ms, so no duplicate migration was retained. Offline suite: 229 passed, 3
  dedicated PostgreSQL integration tests skipped. No source, provider, Gmail, Telegram, or
  user-data request was made.
- 2026-09-12: Optimizer Phase 0 documentation validation: 229 passed, 3 dedicated PostgreSQL
  integration tests skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset; `git diff --check`
  passed. The first test invocation could not write the host system temporary directory, so the
  same suite was rerun successfully with an isolated workspace temporary directory, which was
  removed afterwards. No runtime code, schema, external provider, source, Gmail, Telegram, or VDS
  call changed.
- 2026-09-12: Telegram control-surface validation: 226 passed, 3 dedicated PostgreSQL integration
  tests skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset. Fake transport coverage verifies
  authorized help/source/interest commands do not call a model; source tests cover atomic persistent
  RSS/YouTube addition, safe disablement, duplicate/invalid rejection, and channel URL detection.
  Ruff and `git diff --check` passed. No external provider, source, Gmail, Telegram, or VDS call
  was made.
- 2026-09-14: Managed-source Stage 14 Control Center Scheduler UI: focused Admin/scheduler
  coverage passed 34 tests with 1 opt-in PostgreSQL skip; the full offline suite passed 289 tests
  with 6 opt-in PostgreSQL skips. A uniquely named disposable pgvector PostgreSQL database
  migrated to `20260914_0026`, and persisted scheduler-preference acceptance passed before its
  container and anonymous volume were removed. Full Ruff with `--no-cache` and `git diff --check`
  passed. No separate frontend package/checker exists; server-rendered page and endpoint coverage
  exercised the UI contract. No provider, live source, production database, deployment automation,
  or scheduler run occurred.
- 2026-09-14: Managed-source Stage 13 Control Center Search / Memory: focused Admin/Search
  coverage passed 34 tests; the full offline suite passed 287 tests with 6 opt-in PostgreSQL
  skips. A uniquely named disposable pgvector PostgreSQL database migrated to `20260914_0026` and
  the real Search integration suite passed 3 tests, including compact event detail retrieval;
  its container and anonymous volume were removed. Full Ruff with `--no-cache` and
  `git diff --check` passed. The configured local PostgreSQL endpoint was unavailable for a
  browser-server smoke, while TestClient page and endpoint coverage passed. No provider, live
  source, production database, deployment automation, or knowledge mutation occurred.
- 2026-09-14: Managed-source Stage 12 Control Center Briefings history/detail: focused Admin and
  briefing coverage passed 30 tests; the full offline suite passed 284 tests with 6 opt-in
  PostgreSQL skips. A uniquely named disposable pgvector PostgreSQL database migrated to
  `20260914_0026`; direct persisted briefing history/detail reads verified complete generated
  content and timezone-aware Istanbul conversion before its container and anonymous volume were
  removed. Full Ruff with `--no-cache` and `git diff --check` passed. No provider, live source,
  production database, deployment automation, or main-worktree mutation occurred.
- 2026-09-14: Managed-source Stage 11 Control Center operational dashboard: focused Admin
  coverage passed 20 tests and the full offline suite passed 281 tests with 6 opt-in PostgreSQL
  skips. A uniquely named disposable pgvector PostgreSQL database migrated to `20260914_0026` and
  passed 11 focused onboarding/source-repository tests before its container and anonymous volume
  were removed. Full Ruff with `--no-cache` and `git diff --check` passed. Coverage proves
  server-rendered operational status, source health/failure display, latest briefing and provider
  usage fallbacks, and preserved `/admin` operations. No provider,
  live source, production database, deployment automation, or main-worktree mutation occurred.
- 2026-09-14: Managed-source Stage 10 Control Center onboarding: focused Admin/scheduler coverage
  passed 26 tests. The full offline suite passed 281 tests with 6 opt-in PostgreSQL skips. A
  uniquely named disposable pgvector PostgreSQL database migrated to `20260914_0026` and passed
  11 focused onboarding/source-repository tests before its container was removed. Coverage proves
  optional/resumable setup rendering, existing Admin API entry points, scheduler input validation,
  idle scheduler reconfiguration, and durable non-secret scheduler preferences. No provider, live
  source, production database, deployment automation, or main-worktree mutation occurred.
- 2026-09-14: Managed-source Stage 9 one-time YAML bootstrap lifecycle: focused bootstrap,
  repository, RSS, and YouTube runtime coverage passed 30 tests with 2 opt-in PostgreSQL skips.
  The full offline suite passed 279 tests with 5 opt-in PostgreSQL skips. A uniquely named
  disposable pgvector PostgreSQL database migrated to `20260914_0025` and passed all 10
  managed-source repository tests; its container and anonymous volume were removed. Coverage
  proves explicit empty-DB bootstrap, repeated/idempotent and canonical duplicate handling,
  non-default seed-default persistence, pre-existing-row preservation, and that completed/default
  startup does not load YAML while runtime/retry catalog reads remain database-only. No provider,
  live source, production database, deployment, onboarding, or main-worktree mutation occurred.
- 2026-09-14: Stage 8 Control Center validation: focused Control Center/import/export suite passed
  61 tests. The complete offline suite passed 278 tests with 4 opt-in PostgreSQL tests skipped;
  full Ruff with `--no-cache` and `git diff --check` passed. A uniquely named disposable pgvector
  container was migrated to `20260913_0024`, passed the managed-source PostgreSQL acceptance test
  (1 test), and was removed with its anonymous volume. Coverage includes the narrow shell and
  dashboard, repository availability, escaped untrusted source values, API-driven CRUD controls,
  all four import entry points, downloads, and text-node result/error rendering. No provider, live
  source, production database, deployment, onboarding, ingestion, or main-worktree mutation
  occurred.
- 2026-09-13: Stage 7 source export validation: focused export coverage passed 4 tests; export plus
  Source Pack, OPML, CSV, Admin, and repository coverage passed 68 tests with 1 opt-in PostgreSQL
  test skipped. The full offline suite passed 277 tests with 4 opt-in PostgreSQL tests skipped.
  Full Ruff and `git diff --check` passed. A disposable migrated PostgreSQL container passed the
  managed-source acceptance test (1 test) and was removed with its anonymous volume. Coverage
  includes deterministic canonical Source Pack/OPML/CSV output, disabled-source inclusion, Source
  Pack round-trip state, documented format limits, Admin attachment responses, and unavailable
  repositories. No provider, Control Center, onboarding, deployment, ingestion, or main-worktree
  mutation occurred.
- 2026-09-13: Stage 6 CSV and bulk URL validation: focused adapter coverage passed 16 tests; CSV and
  bulk URL plus Source Pack, OPML, and relevant repository/Admin coverage passed 64 tests with 1
  opt-in PostgreSQL test skipped. The full offline suite passed 273 tests with 4 opt-in PostgreSQL
  tests skipped. Full Ruff and `git diff --check` passed. A disposable migrated PostgreSQL
  container passed the managed-source acceptance test (1 test) and was removed with its anonymous
  volume. Coverage includes strict CSV/header parsing, bounds, shared normalization, pasted URL
  lines, invalid rows, existing/internal canonical duplicates, preview non-mutation, disabled
  creation, filtered/idempotent import, Admin errors, and unavailable repositories. No provider,
  Control Center, onboarding, export, deployment, or main-worktree mutation occurred.
- 2026-09-13: Stage 5 OPML validation: focused OPML coverage passed 11 tests; OPML plus
  Source Pack and relevant repository/Admin coverage passed 48 tests with 1 opt-in PostgreSQL test
  skipped. Coverage includes safe XML and DTD/entity rejection, root/body validation,
  size/source/depth bounds, nested RSS/Atom extraction, mixed invalid rows, existing/internal
  canonical duplicates, preview non-mutation, filtered/idempotent import, Admin HTTP failures, and
  unavailable repositories. The full offline suite passed 257 tests with 4 opt-in PostgreSQL tests
  skipped; full Ruff and `git diff --check` passed. A disposable migrated PostgreSQL container
  passed the managed-source acceptance test (1 test) and was removed with its anonymous volume.
  No provider, CSV/bulk URL, production deployment, or main-worktree mutation occurred.
- 2026-09-13: Stage 4 Source Pack YAML validation: focused Source Pack coverage passed 11 tests;
  Source Pack plus relevant repository/Admin coverage passed 37 tests with 1 opt-in PostgreSQL test
  skipped; the full offline suite passed 246 tests with 4 opt-in PostgreSQL tests skipped. A
  disposable migrated PostgreSQL container then passed the managed-source acceptance test (1 test)
  and was removed with its anonymous volume. Full Ruff and `git diff --check` passed. Coverage
  includes safe YAML/malformed input, pack structure and bounds, normalized fields, mixed invalid
  rows, existing/internal canonical duplicates, preview non-mutation, filtered/idempotent import,
  Admin HTTP failures, and unavailable repositories. No provider, interest mutation, OPML/CSV,
  production deployment, or main-worktree mutation occurred.
- 2026-09-13: Stage 3 Telegram DB-managed source validation: focused Telegram/repository coverage
  passed 30 tests with the opt-in PostgreSQL test skipped; the full offline suite passed 235 tests
  with 4 opt-in PostgreSQL tests skipped. Full Ruff and `git diff --check` passed. Tests cover
  canonicalized add, bounded list/detail health output, enable/disable, enabled-source delete
  rejection, safe delete, concise invalid/duplicate/not-found/unavailable messages, and absence of
  model work. Docker remained unavailable, so disposable PostgreSQL acceptance did not run. No
  provider, live Telegram/source, production DB/deployment, import/export, or main-worktree
  mutation occurred.
- 2026-09-13: Stage 2 Admin DB-managed source validation: focused Admin/repository coverage passed
  26 tests with the opt-in PostgreSQL test skipped; the full offline suite passed 233 tests with
  4 opt-in PostgreSQL tests skipped. Full Ruff and `git diff --check` passed. CRUD,
  canonicalization visibility, duplicate/invalid/not-found/unsafe-delete HTTP mapping,
  repository-unavailable behavior, compatibility routes, and zero source-YAML mutation are
  covered. Docker remained unavailable, so disposable PostgreSQL acceptance did not run. No
  provider, live source, production DB/deployment, Telegram source-management, or main-worktree
  mutation occurred.
- 2026-09-13: Managed-source repository CRUD/health validation: full Ruff and
  `git diff --check` passed; Alembic static SQL emitted `20260913_0024`; the focused suite passed
  29 tests with only its opt-in PostgreSQL persistence test skipped, and the full offline suite
  passed 232 tests with 4 opt-in PostgreSQL tests skipped. RSS/YouTube fakes verify success and
  safe feed-access failure persistence. No provider, live source, production DB, deployment, or
  main-worktree mutation occurred. Docker daemon was unavailable, so the new disposable
  PostgreSQL acceptance test remains opt-in and unexecuted.
- 2026-09-12: OpenRouter 4xx diagnostic validation: 222 passed, 3 PostgreSQL integration tests
  skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset. The fake client covers one-attempt
  4xx handling, bounded safe error metadata, and secret-like error-message redaction. Ruff and
  `git diff --check` passed. No provider, source, Telegram, VDS, or user-data request was made.
- 2026-09-12: Extractor reasoning-control validation: 220 passed, 3 PostgreSQL integration tests
  skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset. The fake OpenRouter response covers
  the current completion parameter, explicit extractor reasoning disablement, strict provider
  parameter routing, and safe finish/reasoning-token metadata parsing. Ruff and `git diff --check`
  passed. No provider, source, Telegram, VDS, or user-data request was made.
- 2026-09-12: Extractor compact-output validation: 219 passed, 3 PostgreSQL integration tests
  skipped because `SEARCH_INTEGRATION_DATABASE_URL` is unset. The strict extractor schema now
  bounds summaries, titles, claims, and collection sizes; prompt and schema cache versions were
  advanced so prior unbounded outputs cannot be reused. Ruff and `git diff --check` passed. No
  provider, source, Telegram, VDS, or user-data request was made.
- 2026-09-11: M22.1 polling validation: 213 passed, 0 skipped against disposable PostgreSQL
  migrated through `20260911_0021`. Fake Bot API coverage validates webhook removal, bounded
  getUpdates, cursor advancement, shared command routing, and polling-mode configuration. Ruff,
  static Alembic SQL, both synthetic-secret production Compose resolutions, and `git diff --check`
  passed. No live Telegram, VDS, provider, or user-data request was made.
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

- CI failure repaired locally: source-bootstrap startup test fake lacked newly used `gmail_polling_preference`; fake now returns default GmailPollingPreference. Exact failing test reproduced then passed in clean Python 3.12.10 archive without dotenv; full CI-equivalent pytest: 360 passed, 6 skipped, one warning. Ruff/diff check passed; no production-code change. Publication and remote CI result pending. Existing Fixer now eligible for queued summary/daily task after this final report.

- Queued user screenshot follow-up after active CI repair finishes: summary still English/verbose with headings/source-row residue and no blank-line separation; desired exact shape is `Bugün şunlar oldu:` plus short numbered Turkish event sentences separated by blank lines. `/daily` reported silent for 15 minutes; `/gmail` reports polling disabled and connection UX unclear. No new assignment sent while Fixer completes CI; connection simplification remains queued.

- User reported GitHub `python -m pytest` failure and authorized diagnosis/fix. Safe run metadata confirms ci.yml failures 36268154425 / 36268047429, older 36263815469 success. Assigned existing Fixer to filter pytest evidence, reproduce CI Python 3.12 and minimally repair without weakening checks; no production action, Google-login task remains deferred.

- Deployed feature commit `912b563` with explicit user authorization: local commit/push passed; VDS new stash object verified, only that stash popped with index restored, prior stash reference preserved, protected `.env.production` comparison unchanged. Migration service completed 0029 before application recreation. App and DB healthy, all Compose services running, localhost `/health` HTTP 200. `/daily` and `/gmail` live user acceptance pending; no manual ingestion/provider/mailbox test triggered. Personal Google-login task remains deferred.

- Migration 0029 accepted on an isolated disposable PostgreSQL/pgvector container: 0028→0029 upgrade passed; prior completed 14:00 Istanbul run/history preserved and exact UTC slot backfilled; repeated backfill and original-slot claim stayed deduplicated; same-day different slot accepted; concurrent same-slot claims yielded exactly one winner. Gmail default 60, persisted 90, valid endpoints 15/1440 and rejected 14/1441 verified on real DB. Test container cleaned up without host mounts/volumes. Feature locally accepted (92 prior focused tests plus DB acceptance); production unchanged. Deployment must apply Alembic 0029 before starting new app. Personal Google-login work remains deferred.

- Migration acceptance blocked: local Docker Linux daemon unavailable and no local PostgreSQL runtime found. No DB test or migration executed; 0029 remains unverified on PostgreSQL. User asked to make Docker Desktop ready for an isolated disposable DB test. Deploy must run migration before new app startup because Gmail preference column and delivery-slot table are required; current server kept unchanged.

- Fixer implemented fresh `/daily`, persisted `/gmail` interval (15–1440 minutes), separate bounded Gmail polling, source-link-free Telegram summary, and UTC delivery-slot claims with additive migration `20260926_0029_delivery_slots_gmail_interval.py`. Reported 92 focused tests passed, changed-file Ruff passed, Graphify updated. Local DB migration/history/idempotency acceptance requested from same Fixer before deployment readiness. No commit, push or VDS deployment for this change; personal Google-login work remains deferred.

- User approved removing coarse one-run-per-day restriction: keep idempotency per planned delivery slot, allowing a changed future time on the same day while preventing same-slot restart/concurrency duplicates. `/daily` remains an explicit manual invocation with busy/budget guards. Fixer assigned minimal backwards-compatible change and focused slot/midnight regressions; production unchanged.

- Approved safe VDS diagnosis at 22:17 Istanbul: scheduler enabled, effective env time 22:00, no DB override. September 26 scheduled run already completed_with_errors at 14:00:03 after 13:45 preparation. Same-day durable claim is the leading explanation for no second 22:00 run; Fixer assigned code/fake confirmation without weakening automatic dedup. Queried Telegram delivery aggregate empty; this does not establish absence of other sending paths. No production settings or ingestion changed.

- New user request: investigate missing 22:00 delivery observed at 22:07; add fresh manual `/daily`, hourly read-only Gmail polling and configurable `/gmail` interval; omit displayed daily-summary source links while retaining provenance. Assigned one reused Fixer for related scheduler/Telegram work, focused offline checks and safely scoped production diagnostics. Live ingestion and next deployment not yet authorized.

- Deployed reviewed repair commit `21df390`: local commit/push succeeded; server tracked overrides backed up, stashed, fast-forwarded and popped successfully. Production app/polling Compose rebuilt. Strict backup umask caused eight checked-out Python source files to be unreadable to the container; source permissions restored and rebuild passed. App/DB healthy and localhost `/health` HTTP 200. No migration, provider call or manual ingestion triggered; live Telegram/Actions acceptance remains pending.

- Reviewer accepted final tie-order delta: all shared selector callers supply event ID; SQL tie-break and actual RSS same-date regression verified. Reviewer reran one focused regression: passed. Current repair is locally accepted; GitHub Actions, live DB/Telegram and deployment acceptance remain unverified. Server transfer authorized by user with settings preservation; sensitive command/output approval still required.

- Fixer reports equal-date ordering fixed with shared ascending event-ID tie-break, including SQL detail ordering. Real RSS same-date/reversed-ID regression included; four focused checks, Ruff and diff check passed; Graphify updated. Final independent delta review pending. No remote or deployment actions performed.

- Final reviewer found an equal-date ordering blocker: section/date keys preserve differing caller order, producing different five-item sets. Fixer assigned shared event-ID tie-break and real RSS equal-date regression. User authorized server transfer after acceptance, preserving settings via backup/stash/pop; no transfer performed, sensitive command/output permissions still apply.

- Final date-selection repair reported by Fixer: fresh RSS and YouTube briefing items use `freshness_reference_at`, matching persisted event timestamps. RSS/YouTube scoped tests: 32 passed; Ruff and diff check passed; Graphify updated. Reviewer assigned only this final delta. Local acceptance pending review; GitHub Actions evidence and VDS acceptance remain pending. No commit, push or deployment performed.
- 2026-09-26: Reviewer closed map/atomicity blockers but found fresh RSS BriefingItem missing the
  event date, so editor/detail selection can still diverge. Returned only that producer-path fix
  and realistic regression to Fixer; callback and budget/failure separation remain accepted locally.
- 2026-09-26: Fixer reported editor candidate ordering/cap aligned with visible digest and atomic
  result-map application, with real-Router >5/unsectioned regression and budget-skip accounting.
  78 focused tests, Ruff and diff check passed; sent only the blocker delta for independent review.
- 2026-09-26: Reviewer accepted the callback/token-alphabet repair and renderer boundaries. Editor
  review found a <=5-ID map indexed for all items and a mismatch between edited/visible candidates;
  returned these blockers to Fixer. Stored legacy English briefings are not retro-translated.
- 2026-09-26: Fixer proved a callback issuer/parser token-length mismatch (16 versus required 20)
  through a failing synthetic regression and reported local repair plus 88 focused tests passed.
  Added callback/token-alphabet checks to independent review; live behavior remains unverified.
- 2026-09-26: Fixer reported expanded summary/editor, budget-skip, and delay-label changes with
  87 focused tests passed; assigned independent scoped review. Invalid-feedback and GitHub Actions
  remain unresolved. Requested callback-scope clarification and narrow CI metadata permission.
- 2026-09-26: Reviewer returned `changes required` for the compact-summary repair: both stored
  text branches can retain English, and the revised fixture misses that path. A long first sentence
  can lose its description. Passed bounds/link/feedback mapping checks; returned the scoped blockers
  to the existing fixer. No runtime acceptance or deployment is claimed.
- 2026-09-26: Received Fixer's final report: Telegram service/tests changed, four focused tests,
  Ruff and diff check passed. Assigned independent diff-only review with Luna high. The user
  explicitly authorized two-way task reporting; workers now send final or decision messages to
  the coordinator. No commit/push or deployment was performed for this repair.
- 2026-09-26: Received only the separate reviewer's final/decision outputs. Rendering mismatch is
  confirmed; feedback first-click cause and GitHub Actions failure remain pending evidence. A
  PowerShell command attempted in Bash explains the metadata-collection error, not the CI failure.
- 2026-09-26: Added four concise role profiles under `docs/agent_roles` for reviewer, fixer,
  optimizer, and security review. `AGENTS.md` requires the selected role to be read before each
  assignment and defines a common safe final report. The pending Telegram investigation remains
  read-only and awaits approval; no new agent was created for this documentation task.
- 2026-09-25: Refreshed the local Markdown entrypoints, product brief, Telegram/OPML guides,
  architecture, pipeline, and active handoff. Removed contradictory Telegram command descriptions
  and the stale M9 Docker blocker. M22.4 records the user's category-first flow as planned work,
  separate from the currently deployed UUID-only questions.
- 2026-09-25: M22.3 offline implementation added bounded source-table layout, validated per-row
  editing, deterministic category suggestions, and one allow-listed Telegram category question
  for ambiguous sources. Pending questions survive Telegram unavailability and include bulk
  imports without model calls; independent review and full offline gate passed. Browser viewport,
  disposable PostgreSQL, and live operator-chat checks remain separate acceptance work.
- 2026-09-25: Repaired M22.2 offline: compact Turkish Telegram rendering, subject-based calibration,
  preparation relative to the configured send time, explicit late fresh delivery, ordered safe
  warnings, and bounded error categories. Independent reviews found and closed DST fold/gap and
  RSS health-count edge cases. Historical 2026-09-25 error subcategories remain unavailable;
  production smoke is required before claiming live acceptance. Began M22.3 Admin overflow/edit
  and deterministic category/Telegram operator follow-up.
- 2026-09-25: User supplied actual Telegram output: a safe-error alert, 14:08 delivery despite a
  14:00 target, verbose item-by-item text, and first-14-day questions about publishers/events.
  The safe scheduled summary reports `completed_with_errors`, 8 processed, 4 RSS failures,
  2 YouTube failures, 42 LLM calls, and no Gmail failures; exact error categories and run start
  remain unknown. Opened focused M22.2 diagnosis and repair.
- 2026-09-25: Luna xhigh pilot confirmed M22.2 code paths but found no automatic replay
  of a previously failed Telegram briefing and a saved scheduler preference that can override env
  configuration. Optimizer found no measured gain justifying code changes. Security review found a
  conditional proxy-environment SSRF boundary in production feed/article clients; the scoped offline
  fix and independent review passed. Production smoke remains pending.
- 2026-09-25: Added a concise delegated-delivery protocol and one replaceable active agent brief.
  Started read-only reviewer, optimizer, and security pilots for M22.2. No application code,
  production configuration, provider, or VDS action was changed.
- 2026-09-24: Fixed the daily scheduler boundary race: a non-due wake retries the pinned scheduled
  target instead of recomputing tomorrow; the existing durable per-day claim remains the duplicate
  guard. Added deterministic early-wakeup and consecutive-day coverage. Also replaced a stale fixed
  `next_run` assertion in the Admin test with the runtime value. No production deployment or push.
- 2026-09-23: Implemented M22.2 scheduled Telegram daily assistant behavior. The existing normal
  RSS/YouTube/Gmail runtime now identifies a newly persisted briefing and sends it through the
  existing `/ozet` renderer and channel-scoped notification idempotency. Empty runs stay silent;
  delivery errors remain isolated. Added bounded metadata-derived calibration questions for the
  first 14 successful local briefing days, durable progress/subject migration, small adaptive
  feedback updates, offline regressions, and 12:30 production configuration guidance. M21 RSSHub
  observation was not continued.
- 2026-09-21: Started a fresh M21 seven-day RSSHub observation window with Day 1 of the existing
  exact 15-route isolated profile. Captured aggregate route health and 512 MiB-bound memory only;
  no core source/runtime configuration or provider path changed. Route decisions remain deferred
  until the seven-day report.
- 2026-09-20: Completed M17 with permanent off-host age recovery-key management and a full isolated
  restore drill. The private identity never entered the VPS, repository, backup tree, logs, or
  application secret set; only the public recipient was provisioned. Off-host checksum/decryption,
  isolated PG17 restore, migration/schema/count checks, and secure disposable cleanup passed.
  M21 is now the active milestone; M9 scheduler acceptance remains separate and deferred.
- 2026-09-20: Finished all M17 live observations applicable to the current internal-DB,
  SSH-tunnel-only architecture, including firewall/port boundaries, HTTP security behavior, and one
  fresh structured Turkish briefing. Remote DB TLS and an internet-facing TLS proxy were recorded as
  conditional rather than forced architecture changes; M9 scheduler smoke remains separate. M17
  stays open solely for durable off-host age recovery-key management.
- 2026-09-20: Completed the M17 production runtime-role validation and remediation. Production had
  been using the migration/admin `postgres` role at runtime; app and poller now use the verified
  least-privilege `intelligence_runtime` role and remain healthy. Rotated credentials affected by
  the drill and tightened production env-file permissions. The local internal PostgreSQL topology
  was confirmed to be non-TLS by design; remote hostname/certificate TLS validation remains open
  until production uses a remote database endpoint.
- 2026-09-20: Completed the M17 encrypted backup and isolated restore validation on production. The
  backup was generated with PG17 tooling in the database image, encrypted with a temporary drill-only
  age key, restored only into disposable tmpfs PostgreSQL, and matched production schema/revision and
  representative aggregate counts. Temporary secrets and artifacts were cleaned up; runtime-role/TLS
  validation and long-term off-host key management remain open.
- 2026-09-20: Closed M22.1 after deploying `44c7e70` and completing the Telegram safety/recovery
  smoke. Confirmed unauthorized rejection, duplicate suppression, restart offset continuity,
  failure isolation, bounded commands, safe no-match Search, positive Search matching, and the
  intentional `/sor` provider smoke. M17 is now the active milestone.
- 2026-09-20: Safety/recovery smoke exposed a production search bug: no-match `/ara` queries were
  returning zero-score recent events. Added a focused regression test and the smallest shared
  `HybridRetriever` fix; local search tests and Ruff pass. Production deploy/retest is required
  before M22.1 can close.
- 2026-09-20: Reconciled production status after the `6ed822a` deployment. Recorded healthy app/
  database state, successful migrations, working Telegram polling and commands, 6 managed sources
  with 2 enabled, SSH-tunnel Control Center access, successful Memory Search POST, and expected
  authenticated wrong-origin rejection. M17 and M22.1 now distinguish verified deployment smoke
  from remaining backup, TLS/restore, scheduler, and Telegram safety/recovery acceptance.
- 2026-09-14: Fixed two production Control Center issues. Dashboard status no longer requires a
  Telegram handler in the web process when the supported separate polling worker is configured.
  Admin CSRF now has a narrow localhost SSH-tunnel exception tied to `https://localhost`, while
  normal configured-origin and rejection behavior remains unchanged. Added regression coverage for
  dashboard status and search/run/scheduler POST guards.
- 2026-09-14: Reconciled `main` with `feature/db-managed-sources` while preserving the mainline
  GPT-OSS/reasoning and Telegram hardening. Runtime source reads and Telegram source mutations stay
  database-backed; YAML remains bootstrap-only. RSS 304 responses now persist source health before
  the no-op fast path. Final full-suite and merge checks are pending.
- 2026-09-13: Completed the offline security hardening pass. Gatekeeper title/snippet metadata now
  uses the same escaped, bounded untrusted JSON boundary as full extraction; its prompt/cache
  version advanced to avoid reuse of older results. Source configuration rejects inline URL
  credentials through both Admin and Telegram control paths, Admin writes configuration atomically,
  and rendered provenance links reject local-only targets. Locked dependency and requirement
  consistency checks passed; live VDS/TLS/Telegram and multi-replica limiter checks remain
  environment-dependent.
- 2026-09-13: Removed OpenRouter provider error-message logging. Safe diagnostics retain only
  HTTP status, configured model, and constrained error code/type, preventing a provider/proxy from
  reflecting prompts, source content, or credential-like text into operational logs.
- 2026-09-12: Hardened the process-local rate limiter so synthetic distinct client keys cannot
  retain unbounded in-memory state. Added privacy-preserving `X-Request-ID` correlation and fixed
  diagnostic categories for Agent API and Telegram failures; sensitive command, request, provider,
  credential, and exception text remains excluded from logs. Security headers now apply to early
  authentication/origin rejections as well. Multi-replica shared limiting and a clean external
  dependency-vulnerability audit remain environment-dependent follow-ups.
- 2026-09-12: Added RSS conditional HTTP caching. Per-source ETag and Last-Modified values are
  retained only as bounded source-health metadata; a 304 result is observable and avoids parsing,
  deduplication, article work, and LLM work. Redirect validation, cooldown, source ordering, and
  all safety bounds remain intact. Migration `20260912_0023` is required before validator reuse.
- 2026-09-12: Added bounded RSS metadata-fetch concurrency behind
  `RSS_MAX_CONCURRENT_FETCHES` (default 3). Only independent source collection is concurrent;
  source-health handling is retained and downstream item/LLM processing remains ordered, bounded,
  and unchanged. The setting is documented in `.env.example`.
- 2026-09-12: Verified that the LLM-ledger daily-budget, Admin newest-first, and retention paths
  already have the required `llm_calls.created_at` index from `20260908_0014`; a 100,000-row
  rolled-back synthetic query used it and completed in 0.997 ms. No duplicate migration or index
  was retained.
- 2026-09-12: Captured the first optimizer baseline against a current disposable PostgreSQL schema.
  The small synthetic corpus does not justify ANN/vector indexing, so the current exact pgvector
  strategy remains unchanged; future retrieval work requires larger-corpus evidence and quality
  metrics before a reversible SQL candidate-selection change.
- 2026-09-12: Added the optimizer Phase 0 baseline/acceptance specification. It defines
  sanitized fixture scenarios, retrieval quality and cost gates, before/after PostgreSQL plan
  capture, and rollback requirements; no runtime behavior, schema, source, provider, or user data
  changed. The pending source-health and Telegram worktree changes were preserved.
- 2026-09-12: Added a pre-LLM resilient retrieval layer. RSS sources now persist only safe health
  metadata and skip their cooldown window; terminal invalid/unsupported failures are not retried,
  while timeout/network/429/5xx failures use bounded deterministic backoff. Article extraction now
  falls back from Trafilatura to a bounded visible-text parser, and YouTube prefers configured
  captions before Turkish/English/available tracks and may use a sufficiently long public
  description as explicitly lower-confidence fallback. No CAPTCHA, login/paywall bypass, browser,
  private-content, or LLM scraper was introduced. Migration `20260912_0022` is required before
  the health state is active; live source behavior remains pending VDS verification.
- 2026-09-12: Extended the authorized Telegram control surface without adding a second ingestion or
  assistant path. Allow-listed users can now see help/history/status, maintain the protected
  RSS/YouTube catalog atomically, and manage explicit interests through the existing database
  profile. Source changes keep normal scheduler, freshness, SSRF, deduplication, retry, caption,
  and model-budget boundaries; Gmail remains the existing read-only browser OAuth onboarding flow.
  Offline control-flow/source tests passed; no external service, production configuration, or
  migration changed. VDS polling/webhook and scheduler smoke evidence remains pending.
- 2026-09-14: Completed the isolated Control Center Scheduler UI slice in
  `feature/db-managed-sources`. The new Scheduler page exposes existing daily briefing state,
  timezone, next/last run status, persisted preference, and bounded scheduled-run history. Its
  save form reuses the onboarding scheduler endpoint, retaining backend validation, idle-run 409
  protection, DB persistence, and runtime reconfiguration without a YAML path or frontend
  scheduler logic. Existing onboarding, `/admin`, Gmail/AI settings, deployment, and main-worktree
  behavior remain untouched.
- 2026-09-14: Completed the isolated Control Center Search / Memory slice in
  `feature/db-managed-sources`. The new read-only page reuses existing deterministic retrieval
  and optional bounded Ask callbacks, displays safe compact source/title/date snippets, and opens
  escaped persisted-event detail views. Empty, invalid, unavailable, and missing-result states are
  handled without copying retrieval logic into the browser. Istanbul display converts only
  timezone-aware timestamps; naive legacy values remain unavailable rather than being shifted.
  Existing `/admin`, Briefings, scheduler, AI settings, and main-worktree behavior remain
  untouched.
- 2026-09-14: Completed the isolated Control Center Briefings history and detail slice in
  `feature/db-managed-sources`. The read-only pages list the newest 50 persisted briefings with
  status and summary, render complete escaped generated content, and distinguish empty,
  unavailable, incomplete, and unknown states. Istanbul rendering uses only timezone-aware values;
  naive legacy timestamps are not shifted. Existing `/admin/briefings/{id}`, feedback, storage,
  scheduler, Search/Memory, AI settings, and main-worktree behavior remain untouched.
- 2026-09-14: Implemented the isolated Control Center operational dashboard in
  `feature/db-managed-sources`. It presents database/source health, last ingestion and next
  briefing status, source counts and recent failures, the latest briefing, Telegram/Gmail/provider
  readiness, available provider usage, and links to Sources, setup, and Operations. It reuses the
  existing Admin/runtime services and preserves `/admin`, `/admin/control-center`, and source
  management behavior; no backend operational logic was copied into browser code.
- 2026-09-14: Completed the isolated first-run Control Center onboarding flow in
  `feature/db-managed-sources`. The optional Setup page guides Telegram status/setup, Gmail
  connect-or-skip, managed source add/import, interest overrides, daily briefing schedule choice,
  and readiness. Existing installations remain on the normal dashboard; only an empty catalog sees
  the setup prompt. `control_center_settings` persists scheduler choices without accepting browser
  secrets. No deployment automation or unrelated backend refactor was added.
- 2026-09-14: Completed the isolated managed-source one-time YAML bootstrap lifecycle in
  `feature/db-managed-sources`. `MANAGED_SOURCES_BOOTSTRAP` is default-off and is checked only at
  startup; `20260914_0025` records lifecycle completion. An explicit bootstrap seeds only an empty
  database, persists validated seed defaults, recognizes existing sources without altering them,
  and never rereads YAML after completion. Scheduler/ingestion and blocked RSS/YouTube retries now
  load only the database catalog. Added focused lifecycle and PostgreSQL acceptance coverage;
  onboarding, deployment, source-management UI/API behavior, and the main worktree remain
  untouched.
- 2026-09-14: Refreshed the managed-source continuation handoff after Stage 8. The next isolated
  slice is the explicit one-time YAML bootstrap/development-fixture lifecycle; onboarding and
  production deployment still require a separate explicit request. Recorded the clean baseline
  (`44afab6`), `/admin/control-center` versus preserved `/admin` route boundary, local test runner
  notes, disposable PostgreSQL cleanup rule, and the source-management invariants the next agent
  must preserve.
- 2026-09-14: Completed Stage 8 Control Center foundation in the isolated
  `feature/db-managed-sources` worktree. Added a shared shell at `/admin/control-center`,
  a narrow source-status Dashboard, and a database-backed Sources page for list/create,
  enable-disable, safe-delete, Source Pack/OPML/CSV preview/import, and deterministic
  Source Pack/OPML/CSV downloads. Browser code delegates all validation, canonicalization, and
  persistence to existing Admin endpoints; the existing `/admin` operational page remains
  available, and untrusted values/errors are escaped or set via text
  nodes. Onboarding, Gmail/scheduler/briefing/memory/search/budget/model UI, deployment, ingestion,
  and the main worktree remain untouched. Full evidence: 61 focused tests, 278 offline tests with
  4 opt-in PostgreSQL skips, one disposable PostgreSQL acceptance test, Ruff, and diff check.
- 2026-09-13: Completed Stage 7 deterministic database-managed source export in the isolated
  `feature/db-managed-sources` worktree. Added a read-only exporter and minimal Admin download
  endpoints for Source Pack YAML, OPML, and CSV; exports include disabled rows and canonical
  endpoints. Source Pack preserves all import-supported source metadata; OPML and CSV explicitly
  document their format limits. Control Center, onboarding, deployment, ingestion behavior, and
  main-worktree changes remain untouched.
- 2026-09-13: Completed Stage 6 CSV and bulk URL preview/import in the isolated
  `feature/db-managed-sources` worktree. Added bounded CSV and one-URL-per-line adapters, reused the
  shared Source Pack row/batch workflow, exposed four minimal Admin endpoints, forced disabled
  creation, and documented the formats in `docs/CSV_AND_BULK_URLS.md`. Control Center, onboarding,
  source export, production deployment, and ingestion behavior remain untouched.
- 2026-09-13: Completed Stage 5 OPML preview/import in the isolated
  `feature/db-managed-sources` worktree. Added a safe bounded OPML adapter, shared Source Pack batch
  analysis/import reuse, minimal Admin transport, deterministic row/count results, and focused
  tests. CSV/bulk URL, Control Center, onboarding, production deployment, and ingestion behavior
  remain untouched.
- 2026-09-13: Completed Stage 4 Source Pack YAML preview/import in the isolated
  `feature/db-managed-sources` worktree. Added a reusable safe/bounded parser and service, a minimal
  Admin transport, deterministic per-source/aggregate results, repository-only persistence, and
  retry-safe duplicate handling. Interests/exclude are preview metadata only. The schema/API is
  documented in `docs/SOURCE_PACKS.md`; OPML/CSV/bulk URL, Control Center, onboarding, production
  deployment, and the bootstrap lifecycle remain untouched.
- 2026-09-13: Completed Stage 3 Telegram source management in the isolated
  `feature/db-managed-sources` worktree. The allow-listed chat interface now uses the same database
  repository as Admin and ingestion for source list/detail, validated add, enable/disable, and safe
  delete. It exposes only compact health state and safe error categories in Turkish; Telegram has
  no remaining source YAML path. Import/export, Control Center, onboarding, production deployment,
  and the explicit one-time bootstrap lifecycle remain untouched.
- 2026-09-13: Completed Stage 2 Admin source management in the isolated
  `feature/db-managed-sources` worktree. Admin dashboard/config reads plus get/list/create/update,
  enable-disable, and safe-delete operations now use the database repository as their only runtime
  source of truth; legacy Admin UI routes are repository-backed compatibility wrappers. Admin has
  no remaining source YAML read/write path. Telegram and all later source-import/UI/onboarding work
  remain untouched and are the next separate stages.
- 2026-09-13: Completed the handoff's recommended managed-source repository slice in the isolated
  `feature/db-managed-sources` worktree. Create/get/list/update/enable/disable/safe-delete,
  canonical endpoint validation, duplicate mapping, and RSS/YouTube discovery health persistence
  are implemented and covered offline. Admin/Telegram still use YAML and remain the next cutover;
  do not merge or deploy until that single-source-of-truth transition and real disposable-DB
  acceptance are complete.
- 2026-09-13: Isolated branch `feature/db-managed-sources` / worktree
  `AI-Personal-Assistant-db-managed-sources` started the managed-source cutover. Migration
  `20260913_0024` and DB runtime lookup bootstrap exist; Admin/Telegram CRUD, imports, health
  wiring, UI, and tests remain unfinished. Do not merge or deploy this worktree yet.
- 2026-09-12: Added bounded OpenRouter 4xx diagnostics without logging request payloads or
  credentials. The current `openai/gpt-oss-120b` public model metadata requires reasoning and
  advertises `max_tokens`, so production must use its supported low reasoning effort instead of
  `none`; no model slug, Compose, environment, or database change was made.
- 2026-09-12: Corrected the extractor's OpenRouter completion request after a production
  truncation diagnosis. DeepSeek V4 Flash defaults to high reasoning when no reasoning request is
  supplied; the extractor now opts out explicitly, uses the current completion-limit parameter,
  requires structured-output parameter support from the selected provider, and safely observes
  finish/reasoning-token metadata without retaining response content. A live provider/VDS
  confirmation remains pending.
- 2026-09-12: Bounded the RSS extractor's strict structured output to prevent long source items
  from consuming the configured response ceiling. The compact prompt now explicitly forbids
  article rewrites, and prompt/schema cache versions isolate the new contract from old entries.
  No same-model retry was added because a deterministic truncation retry would repeat provider
  cost without improving recovery.
- 2026-09-11: Added the M22.1 outbound-only polling mode. `TELEGRAM_MODE=webhook|polling` keeps
  webhook as the default and uses a separate hardened poller service in polling mode. The worker
  deletes any webhook without dropping pending updates, persists only its numeric offset, and routes
  updates through the same authorization, deduplication, command, feedback, and callback boundary.
  The polling Compose override exposes no host HTTP port; real VDS/Telegram smoke verification is
  still required.
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
