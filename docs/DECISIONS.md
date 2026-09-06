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

Append future decisions here with date, status, rationale, and consequences. Do not rewrite accepted decisions silently.
