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

Append future decisions here with date, status, rationale, and consequences. Do not rewrite accepted decisions silently.
