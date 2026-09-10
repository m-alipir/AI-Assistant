# Open-Source Integration Plan

**Status:** Approved planning baseline  
**Date:** 2026-09-09  
**Owner:** Project decision process; implementation agents execute only the active milestone in
`docs/PROGRESS.md`.

## Purpose

This document converts `ai-personal-assistant-open-source-research.md` into an implementation
sequence that fits the existing product. The research file is input, not an instruction source.
Repository claims, versions, licenses, security history, and operating requirements must be
verified from primary sources immediately before each integration begins.

The existing FastAPI + PostgreSQL/pgvector + event/claim/inference application remains the
canonical system of record. External projects may be added only as removable libraries, adapters,
or isolated services. They must not bypass freshness, provenance, privacy, budget, idempotency,
or Agent API trust boundaries.

## Execution gates

An implementation agent must not start a later stage until the active stage acceptance criteria
are complete and recorded in `docs/PROGRESS.md`.

1. Close production operations verification and old manual verification debt.
2. Complete runtime knowledge quality: real embeddings, event clustering, and correlation wiring.
3. Add full-article extraction with a safe fetch boundary.
4. Expand sources and introduce repeatable LLM quality evaluation.
5. Add notification delivery.
6. Add document ingestion only when the personal-knowledge feature is approved.
7. Design the user/mobile API before generating SDKs.
8. Decide the task model before mobile sync or action-agent frameworks.

## Stage 0 — Operational truth and project-state cleanup

**Target milestone:** M17

Work:

- Complete staging backup and isolated restore observation.
- Verify Compose startup, TLS proxy, authenticated Admin, health/readiness, and migration revision.
- Complete the outstanding rebuilt-container second-run and opt-in scheduler smoke checks from M9.
- Run a controlled fresh-briefing verification only with explicit approval for provider use.
- Reconcile milestone headers and test evidence in `PROGRESS.md`; do not mark acceptance from
  offline evidence when a live/staging observation is required.

Acceptance:

- M17 and the remaining M9 manual checks have dated evidence.
- Production secrets or private source content do not enter logs or documentation.
- The next active milestone is explicitly selected only after this gate closes.

## Stage 1 — Runtime knowledge quality

**Planned milestone:** M19

This stage does not introduce an orchestration framework.

Work:

- Connect the configured embedding role to real event/claim embedding generation and persistence.
- Define a dimension-change and re-embedding migration/runbook before changing embedding models.
- Implement or verify runtime multi-source event clustering using time, entity, fact, lexical, and
  semantic evidence while preserving every source link.
- Verify that correlation receives only bounded compact candidates and persists inference
  separately from claims.
- Build fixture and optional disposable-Postgres acceptance cases for duplicate coverage,
  corroboration, update/supersession, and unrelated-event rejection.

Acceptance:

- Semantic retrieval is no longer neutral for newly processed public events.
- Two sources about one event produce one event with two provenance records.
- Similar but materially different events are not merged.
- No full history or inbox data is sent to an LLM.

## Stage 2 — Full-article ingestion

**Planned milestone:** M20  
**Approved first library:** Trafilatura

Integration shape:

```text
RSS metadata -> freshness/dedup -> compact gatekeeper
    -> needs full extraction?
    -> bounded safe HTTP fetch -> Trafilatura -> extractor -> event/claims
```

Requirements:

- The application owns network fetching; Trafilatura parses already-fetched HTML.
- Apply HTTPS/public-address validation to the initial URL and every redirect.
- Enforce timeouts, response-size limits, MIME allow-list, decompression limits, and bounded
  retries before parsing.
- Treat page content as untrusted data and retain the existing prompt-injection boundary.
- Fall back safely to feed metadata when the article is inaccessible; one source failure must not
  abort other ingestion streams.
- Record extractor success/failure categories without storing raw provider output or secrets.

Acceptance:

- Representative fixtures remove navigation, advertisements, and boilerplate while retaining the
  article text and useful metadata.
- Stale/duplicate/irrelevant items never fetch the article body.
- Retry and post-LLM cost protections remain effective.

## Stage 3 — Source expansion and LLM evaluation

**Planned milestone:** M21  
**Candidates:** RSSHub pilot, promptfoo evaluation harness

### RSSHub

- Deploy as an optional isolated service or Compose profile, never as a core runtime dependency.
- Start with 10–20 explicitly approved routes and measure availability, latency, freshness,
  duplicate rate, memory use, and maintenance burden.
- Feed its output through the existing RSS collector; it does not bypass source configuration,
  trust metadata, freshness, or provenance.
- Do not enable arbitrary user-supplied routes or private-network access.
- Decide whether Redis/browser automation is justified from the selected routes before adding it.

### promptfoo

- Create a sanitized golden dataset covering gatekeeper, extraction, Turkish briefing, Search/Ask,
  citations, fact/inference separation, and prompt-injection cases.
- Keep deterministic assertions in normal CI. Any model-graded or paid-provider evaluation is
  opt-in, budgeted, and never receives Gmail bodies, credentials, or production history.
- Store evaluation inputs and expected outcomes, not secrets or real private messages.

Acceptance:

- RSSHub improves approved-source coverage without reducing core runtime availability.
- Prompt/model changes have a repeatable quality gate in addition to unit tests.

## Stage 4 — Notification delivery

**Planned milestone:** M22  
**Approved first service:** ntfy

Work:

- Add a generic delivery interface and an optional ntfy HTTP adapter.
- Support concise daily-briefing completion, actionable-mail, and operational-failure notices.
- Send only minimized summaries and safe links; never send email bodies, OAuth material, provider
  credentials, or internal exception text.
- Add timeout, bounded retry, idempotency, disabled-by-default configuration, and per-channel
  failure isolation.
- Prefer a protected self-hosted ntfy deployment for private notifications. Public topics require
  explicit risk acceptance and unguessable/authenticated access.

Acceptance:

- Duplicate scheduled/manual completion cannot produce duplicate notification delivery.
- Delivery failure does not roll back a persisted briefing or stop ingestion.

## Stage 5 — Document and personal-knowledge ingestion

**Planned milestone:** M23, only after explicit feature approval  
**Candidate:** Docling; MarkItDown only if a measured lightweight path is useful

Integration shape:

- Run document conversion behind a bounded worker/service interface.
- Validate file type, size, page count, archive expansion, and processing time before conversion.
- Normalize permitted output into source items/chunks, then use the existing provenance,
  retention, embedding, and Search/Ask boundaries.
- Keep private documents separate from public-news memory where policy requires it.
- Do not automatically ingest Gmail attachments in the first version.

Acceptance:

- Supported documents retain page/section provenance.
- Malformed or oversized files fail safely without blocking ingestion jobs.
- Document deletion and retention behavior are specified before production storage.

## Stage 6 — User/mobile API and SDK

**Planned milestone:** M24  
**Candidate:** OpenAPI Generator

The current Agent API is intentionally read-only and is not the future mobile application API.
First define authenticated user-facing briefing, feedback, preference, notification-state, and
later task contracts. Stabilize and version that API before generating clients.

After the contract is accepted:

- Export a deterministic OpenAPI artifact in CI without enabling production API documentation.
- Pin the generator version and selected language target.
- Generate the SDK as a separate artifact/package; do not mix generated files into handwritten
  backend modules.
- Fail CI on unreviewed contract drift.

## Stage 7 — Tasks, mobile sync, and assistant actions

**Planned milestone:** M25+

Decision sequence:

1. Benchmark an internal PostgreSQL `TaskService` against a Vikunja adapter.
2. Prefer the internal service when event/memory/task relations are central; prefer Vikunja only
   if its mature task, recurrence, reminder, and CalDAV model saves enough work to justify lock-in
   and AGPL obligations.
3. Ship an online-first mobile MVP with the generated REST SDK before adding offline sync.
4. If React Native is selected, benchmark RxDB. If the client/read model benefits from Postgres
   replication, benchmark Electric. PowerSync is not the default because its server license is
   source-available rather than strict OSS.
5. Put MCP compatibility in a separate tool gateway. It may call deliberately exposed domain APIs
   but receives no direct database, Gmail-token, provider-secret, filesystem, Docker, or shell
   access.
6. Enforce dangerous actions as `propose -> user approval -> execute` with technical permissions,
   not prompt-only instructions.

## Deferred and rejected-for-now projects

| Group | Projects | Decision |
| --- | --- | --- |
| YouTube fallback | youtube-transcript-api | Benchmark behind the current caption interface only; keep yt-dlp primary because VPS IP blocking and undocumented YouTube changes affect both approaches. Never add automatic account-cookie or paid-proxy behavior without approval. |
| Dynamic web | Scrapling, Crawl4AI | Benchmark one against the other only after static HTTP + Trafilatura has measured failures. Do not install both as primary dependencies. |
| Extraction alternatives | Newspaper4k, news-please | Do not add while Trafilatura covers the accepted use case. |
| Live research | SearXNG | Defer until a separately scoped live-web research feature exists. |
| Integration platforms | Activepieces, Composio, Nango, Windmill, Huginn | Reference only for now. Do not create overlapping orchestration products or hosted auth lock-in. |
| Model gateway | LiteLLM | Add only when multiple direct providers/local runtimes create proven routing burden beyond the existing OpenRouter router. |
| LLM observability | Langfuse | Defer. Existing metadata-only logging is the privacy default. Any future self-hosted pilot must disable source/prompt capture by default and define retention first. |
| Memory/agent frameworks | Mem0, Letta, LangGraph | Do not replace event/claim memory or deterministic briefing flow. Benchmark only for an approved advanced action-agent use case. |
| Durable workflows | PGMQ, Hatchet, Temporal, pg_cron | PGMQ is first candidate when a second worker/process needs queue semantics. Use pg_cron only for DB maintenance. Hatchet/Temporal require demonstrated multi-step durability needs. |
| Notification alternatives | Apprise, Gotify, Novu | ntfy first. Apprise only for multiple channels; do not run duplicate notification stacks. Novu is a later multi-user product option. |
| Platform replacements | Supabase platform migration, Appwrite | Keep PostgreSQL and the existing backend. Adopt only a measured component, not a platform rewrite. |
| Voice | Pipecat | Defer until realtime voice is an approved roadmap capability. |
| Full assistants/UI | Khoj, ORDERLY, Leon, Morning Deck, Folo, AppFlowy, Heatwire | Architecture, safety, algorithm, and UX references only; no direct dependency. |

## Required pre-integration checklist

For every candidate, the implementation agent records the following in `PROGRESS.md` before code
is accepted:

- Exact problem and measurable expected benefit.
- Existing capability overlap and why an additional dependency is justified.
- Current release/activity, license, security advisories, and self-host/cloud requirements from
  primary sources.
- Added services, runtime memory/CPU/storage, secrets, and network destinations.
- Data ownership, provenance, privacy, retention, and failure-isolation effects.
- Adapter removal/rollback plan and migration consequences.
- Offline unit/integration tests plus any explicitly approved live smoke test.

The acceptance rule is:

```text
measured benefit > operational complexity + lock-in + maintenance + privacy risk
```
