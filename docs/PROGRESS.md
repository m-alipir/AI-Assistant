# Project Progress — Source of Truth

**Project state:** IN PROGRESS  
**Current milestone:** M6  
**Last updated:** 2026-09-06

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
- [ ] classes: action/application/recruiter/security/transactional/recommendation/newsletter/personal/other
- [x] action/deadline extraction
- [x] job-application state linkage where possible
- [x] email raw-body retention policy
- [x] no general memory embedding of irrelevant emails

**Acceptance:** fixtures show LinkedIn-style recommendations suppressed/de-emphasized while application rejection/interview/security messages surface correctly; account checkpoints are independent.

## M6 — Daily briefing + global news stream
**Status:** [ ] TODO

- [ ] `Action Required`
- [ ] `For You`
- [ ] `Tech & Industry`
- [ ] `Connections / Why It Matters`
- [ ] `World in Brief / Dünyada Neler Oldu?`
- [ ] `Worth Watching`
- [ ] global-news selection independent of personal interest score
- [ ] event/source dedup in briefing
- [ ] source links/provenance rendered
- [ ] daily editor model
- [ ] persisted briefing history
- [ ] at least one delivery adapter + stdout/local preview

**Acceptance:** fixture day produces a coherent briefing where a globally important low-interest story remains visible under World in Brief.

## M7 — Stable adaptive interest learning
**Status:** [ ] TODO

- [ ] base/explicit/adaptive interest layers
- [ ] feedback event logging
- [ ] explicit natural-language more/less mapping
- [ ] nightly 14-day candidate scoring
- [ ] minimum-signal/day thresholds
- [ ] 7-day rate cap
- [ ] ~21-day adaptive decay toward neutral
- [ ] explanation/history/rollback
- [ ] ranking integration
- [ ] world stream unaffected by personal weights

**Acceptance:** one interaction has negligible/no persistent effect; repeated AMD-like interaction over multiple days increases ranking; explicit “more NVIDIA” changes immediately; global-news section is unchanged.

## M8 — Admin UI/API + deployment hardening
**Status:** [ ] TODO

- [ ] source CRUD/enable-disable
- [ ] model role config view
- [ ] interest profile view/override
- [ ] run-now action
- [ ] recent briefings
- [ ] run/LLM cost metrics
- [ ] health/error overview
- [ ] production Docker Compose/example
- [ ] backup/migration notes
- [ ] non-root/runtime hardening where practical
- [ ] VPS deployment guide

**Acceptance:** fresh install can be configured without editing Python source; local -> VPS deployment path documented and tested.

---

## Backlog / explicitly out of current track
- [ ] Gmail Pub/Sub push/watch if polling latency becomes a real issue
- [ ] Audio download + STT fallback when no YouTube captions exist
- [ ] Telegram/Discord richer interactive feedback buttons
- [ ] Qdrant migration only if pgvector scale proves inadequate
- [ ] browser automation for non-RSS/paywalled/dynamic sources
- [ ] richer Q&A/chat over the knowledge base
- [ ] automatic source-quality learning

## Blockers
None. Credentials are not required for M0 unit tests or local defaults.

## Tests
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
