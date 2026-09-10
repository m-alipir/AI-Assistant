# Architecture Decision Log

## D001 — Code-first runtime, no n8n core
**Status:** Accepted

Core pipeline is a Python service. n8n may be added later only as optional integration glue when it clearly reduces work for a third-party SaaS integration.

## D002 — Supabase/PostgreSQL + pgvector before Qdrant
**Status:** Accepted

Reason: system needs relational state, taxonomy, email/application state, provenance, and vectors. pgvector satisfies V1 semantic retrieval without a second database.

## D003 — Hierarchical taxonomy + normalized entities, not literal folders
**Status:** Accepted

Categories are hierarchical; entities/topics are many-to-many. UI can display Technology -> Semiconductors -> AMD while data remains queryable across multiple dimensions.

## D004 — Facts/claims separate from inference
**Status:** Accepted

LLM interpretation must never be indistinguishable from source-backed information.

## D005 — Freshness gate before LLM
**Status:** Accepted

Old RSS/feed entries are filtered before expensive processing.

## D006 — Personalized and global-news streams remain separate
**Status:** Accepted

Low personal interest does not remove globally important events. They go to `World in Brief`.

## D007 — Slow adaptive interests
**Status:** Accepted

Explicit user commands apply immediately; inferred interests require repeated evidence over roughly 1–2 weeks and are rate-limited/decayed.

## D008 — Role-based OpenRouter models
**Status:** Accepted

Model IDs are config-driven (`gatekeeper`, `extractor`, `reasoner`, `editor`, `embedding`). No model family is architectural infrastructure.

## D009 — Gmail incremental polling for V1
**Status:** Accepted

Polling/history synchronization is simpler for a personal low-cost VPS than Gmail Pub/Sub push. Pub/Sub/watch is a future optimization if latency/scale justifies it.

## D010 — yt-dlp transcript path for public YouTube content
**Status:** Accepted

Prefer available subtitles/auto-subtitles without downloading media. Audio/STT is an optional fallback later.

---

## D011 — Apply migrations before the development API starts
**Date:** 2026-09-06  
**Status:** Accepted

The Compose application command runs `alembic upgrade head` before Uvicorn starts. This makes a
fresh M0 development stack operational with one `docker compose up` command and keeps migration
execution explicit in container logs. Production deployment orchestration may replace this with a
dedicated migration step in M8 if multiple application replicas make startup migrations unsafe.

---

## D012 — Metadata-only LLM operational persistence
**Date:** 2026-09-06  
**Status:** Accepted

`llm_calls` persists only operational metadata: role, configured model identifier, input/output
token counts, calculated cost, latency, cache-hit flag, outcome status, and timestamp.
`llm_result_cache` persists an opaque exact cache key, model identifier, and the validated
structured result. Prompts, raw provider responses, credentials, and arbitrary source text are
never written to these tables. This gives restart-persistent accounting/cache observability while
preserving the M2 privacy boundary; later milestones may add retention controls if operational
requirements change.

---

## D013 — Event memory uses relational provenance with pgvector embeddings
**Date:** 2026-09-06  
**Status:** Accepted

M3 stores category paths, canonical entities and aliases, topics, source-provenanced events and
claims, and model inferences in distinct relational records. Event embeddings use PostgreSQL's
`vector` type with explicit dimension metadata. Retrieval first narrows candidates by structured
fields, then combines lexical and vector similarity. Raw public content expires independently of
the distilled event, claim, inference, and source-provenance records.

---

## D014 — Correlation is a selective, evidence-bound inference step
**Date:** 2026-09-06  
**Status:** Accepted

The reasoner is eligible only after deterministic importance, tracked-entity, retrieval, or
contradiction policy triggers. It receives a bounded top-N set of compact historical events and
returns a validated inference that names linked events and supporting claim IDs. Event state and
relations preserve update/supersession handling without converting the inference into a claim.

---

---

## D015 — Durable briefing outbox and bounded provider-work coordination
**Date:** 2026-09-08
**Status:** Accepted

Events and actionable Gmail classifications stage only compact, permitted briefing metadata in a
transactional outbox. A rendered briefing deletes those rows in the same transaction; an outage
therefore recovers the briefing without repeating ingestion or LLM extraction. A shared,
non-queuing in-process provider-work coordinator protects the documented single-process deployment
from overlapping uncached provider requests, while the database cache/budget ledger remains the
restart boundary. Multi-process deployments still need a database-backed distributed work lease
before enabling concurrent app replicas.

---

## D016 — Separate agent orchestration and coding trust zones
**Date:** 2026-09-08
**Status:** Accepted

Hermes is a future orchestration/user-facing agent layer, not a replacement for the Personal
Intelligence System runtime. A future integration surface will be versioned and domain-oriented
(`briefings`, `knowledge`, `preferences`, and `system`) rather than Hermes-specific. The AI
Assistant does not grant Hermes direct database access, Gmail OAuth material, OpenRouter secrets,
or shell access. Coding automation, if later introduced, runs in an independently authorized
coding-worker/Codex CLI trust zone and does not inherit this service's credentials or data access.

Consequences: no Hermes endpoint, task/reminder feature, PC activity tracking, local-model router,
or home-PC coding bridge is added to V1/M17. Any external integration API needs a separate
authentication, authorization, rate-limit, audit, and data-minimization design before exposure.

---

## D017 — Disabled-by-default read-only Agent API
**Date:** 2026-09-08
**Status:** Accepted

The first generic integration API is limited to persisted briefing reads and the existing bounded
knowledge Search/Ask path. It uses a dedicated bearer token from environment/secret file, not Admin
Basic auth, and fails closed when disabled or configured without a strong token. API projections
exclude raw source material, mailbox identity/body/OAuth data, provider/admin/database secrets, and
operational internals. It has bounded pages/bodies/responses, a process-local rate limit, no-store
responses, and an audit table containing only time, endpoint category, outcome, and response size.

Consequences: no mutation, feedback, preference write, source/scheduler/Gmail/retry control, shell,
or coding-worker capability is added. Hermes remains merely one possible client of the generic
contract. Multi-replica deployment requires a shared rate limiter before treating the configured
limit as global.

---

## D018 — External projects integrate behind removable boundaries
**Date:** 2026-09-09
**Status:** Accepted

The FastAPI application, PostgreSQL/pgvector data, and event/claim/inference domain model remain
the canonical system of record. Open-source projects may be added only when they provide a new,
measurable capability and can be isolated as a library, adapter, generated artifact, or optional
service. They do not bypass freshness, provenance, idempotency, privacy, budget, or authorization
controls, and they must have a documented removal/rollback path.

Consequences: there is no platform rewrite to Appwrite/Supabase, no replacement of the knowledge
model with Mem0/Letta, and no replacement of deterministic ingestion/briefing with LangGraph or a
workflow product. RSSHub, ntfy, Docling, generated SDKs, future MCP tools, and similar components
remain subordinate to versioned application-owned interfaces. Full assistant repositories are
architecture/UX references rather than dependencies.

---

## D019 — Close operational and knowledge-quality gaps before expanding product scope
**Date:** 2026-09-09
**Status:** Accepted

Production operations verification is the active gate. After it closes, implementation proceeds
through real embedding/clustering/correlation behavior, safe full-article extraction, measured
source expansion and LLM evaluation, then notification delivery. Document ingestion, mobile SDKs,
tasks, offline sync, MCP actions, advanced agents, and voice follow only after their preceding
domain/API decisions are approved.

Consequences: Trafilatura is the first approved article-extraction candidate; RSSHub and promptfoo
are controlled pilots; ntfy is the first notification candidate. `youtube-transcript-api` is only
a benchmarked fallback behind the current caption interface. OpenAPI Generator waits for a stable
user/mobile API, and PGMQ/LiteLLM/Langfuse/LangGraph/Temporal-class infrastructure requires a
demonstrated operational need. The updateable execution and acceptance plan is
`docs/OPEN_SOURCE_INTEGRATION_PLAN.md`.

---

## D020 — Full-article parsing stays behind an application-owned fetch boundary
**Date:** 2026-09-10
**Status:** Accepted

Trafilatura parses only HTML bytes already fetched by the application. The application retains
ownership of URL/public-address validation on every redirect, HTTPS policy, timeout, retry,
response-size, MIME, and decompression bounds. The parser receives no URL and therefore cannot
expand the outbound network surface. A fetch or parsing failure falls back to bounded RSS metadata
instead of failing the whole run or triggering another model attempt.

Consequences: Trafilatura `>=2.2,<3` is the first removable extraction dependency (Apache-2.0 in
the current upstream release). Its removal restores metadata-only extraction without data
migration. Dynamic browser tooling, crawling, and arbitrary URL input remain out of scope.

---

## D021 — Quality regression defaults to sanitized deterministic fixtures
**Date:** 2026-09-10
**Status:** Accepted

The default M21 quality gate is a small synthetic/public-style golden dataset executed by pytest.
It exercises gatekeeper, extraction, briefing, Search/Ask, fact-versus-inference, and source
prompt-injection contracts without sending data to a provider. Promptfoo is not a normal runtime
or CI dependency: its configuration and referenced transforms/assertions are trusted executable
local inputs, so it is reserved for an explicitly approved, isolated, sanitized, budgeted manual
evaluation.

Consequences: no Gmail body, production history, credential, real source payload, cloud report, or
telemetry is permitted in the golden dataset. RSSHub remains a separate disabled pilot with an
operator-approved route allow-list; the core collector continues to operate independently.

---

## D022 — RSSHub pilot is aggregate-only and cannot activate the normal runtime
**Date:** 2026-09-10
**Status:** Accepted

The approved RSSHub experiment uses a separate, default-off Compose profile with exactly fifteen
credential-free routes. Selecting that profile suppresses the normal application service and runs
only an explicit, once-per-day collector. The collector applies existing freshness and
deduplication rules but performs no LLM, Gmail, YouTube, briefing, or scheduler work. It stores
only route name, tier, timestamp, availability, latency, aggregate item counts, and a safe error
category.

Consequences: current core sources remain independent and unaffected. The seven-day review uses
the persisted operational aggregates plus host-side Docker memory samples to select `keep`,
`disable`, or `needs-auth` per route. GitHub Trending remains deferred because it requires a
token; Reddit is not an RSSHub route and stays a separate community/discovery-only backlog item.

---

## D023 — Promptfoo provider evaluation is manual, separate-key, and bounded
**Date:** 2026-09-10
**Status:** Accepted

The M21 provider-evaluation option is a committed synthetic Promptfoo configuration, not a CI or
runtime dependency. It uses one explicitly chosen OpenAI-compatible model through OpenRouter, five
synthetic cases, at most 300 generated tokens per case, one request per minute, no sharing, and a
separate `PROMPTFOO_OPENROUTER_API_KEY` environment variable. It contains no executable assertion,
custom provider, transform, red-team generator, real source, Gmail data, production history, or
credential.

Consequences: an operator must separately approve the model, scoped key, and five-request budget
before a manual run. A provider-evaluation result cannot silently alter models, prompts, or runtime
behavior. Normal pytest remains the only default quality gate.

---

## D024 — ntfy delivery is optional, protected, and idempotent
**Date:** 2026-09-10
**Status:** Accepted

Notifications use a provider-neutral contract and an ntfy adapter that defaults to disabled. An
enabled adapter requires an HTTPS origin, topic, and token; `ntfy.sh` additionally requires explicit
public-topic acknowledgement and a long topic name. The adapter sends only fixed concise notices,
not briefing contents, email subjects/bodies, provider errors, credentials, or source payloads.

Consequences: a durable notification key claims each logical event, while ntfy's sequence ID updates
the same logical message during a failed-delivery retry. Delivery happens only after the ingestion
run's durable work and returns a safe status, so an unavailable notification channel cannot roll
back a briefing or stop source processing. A protected self-hosted ntfy service remains preferred.

---

Append future decisions here with date, status, rationale, and consequences. Do not rewrite accepted decisions silently.
