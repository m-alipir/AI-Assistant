# Agent Handoff — 2026-09-08

## Purpose

This note lets another coding agent continue the Personal Intelligence System without repeating discovery work. It intentionally contains **no credentials, tokens, email bodies, provider output, or real account data**.

## Working rules

- Workspace: `C:\Users\Mali\Documents\ChatGPT\AI Personal Assistant`
- Read `AGENTS.md` first. Its mandatory document order and privacy/idempotency rules apply.
- `docs/PROGRESS.md` is the implementation source of truth. Current milestone is **M16**.
- The worktree is already dirty with substantial, user-owned and prior milestone changes. Preserve unrelated edits; do not reset, checkout, or mass-format files.
- Use Alembic for schema changes. Do not make destructive migrations.
- Offline tests must never contact Google, OpenRouter, YouTube, RSS, or real user accounts.
- Secrets never belong in source, tests, fixtures, logs, prompts, docs, or this file.

## Product/runtime completed so far

The application is a FastAPI + Jinja2 local/VPS admin product, with no separate JS build system.

- RSS: bounded fetch, freshness/future-date filtering and durable idempotency before LLM work; OpenRouter gatekeeper/extractor; persisted events, claims/provenance and briefings.
- Gmail: opt-in readonly OAuth (`gmail.readonly`), Fernet-protected refresh tokens, bounded initial sync plus `historyId` incremental sync, deterministic noise filtering, Action Required items.
- YouTube: public channel Atom discovery, 72-hour freshness, video/fingerprint dedup, caption-only processing, optional `tr`/`en` preferred captions, Worth Watching, and post-LLM retry protection.
- Scheduler: opt-in daily local-time operation, DB daily claim, collision protection, no-content/no-editor cost protection.
- Search/Ask: bounded deterministic/hybrid event retrieval with Turkish UI, safe Gmail metadata-only boundary, citations, degraded model-summary fallback, and an optional PostgreSQL integration test.
- Production hardening: production Admin authentication/host/origin controls, secure headers, secret redaction, safe OAuth/source fetch policies and a hardened Compose profile.

## Most recent work: M16 briefing reader quality refinement

The Admin briefing detail route is `/admin/briefings/{briefing_id}`. It must never call an LLM while rendering.

Implemented in the current worktree:

1. Fixed, Turkish-first reader sections and Istanbul time rendering.
2. New extractor prompt requests `briefing_title`, `compact_summary`, and `what_changed` in Turkish. Source claims remain source-language facts and appear under a separate label.
3. New migration `20260908_0015` adds nullable Turkish fields to `briefing_outbox` and creates `briefing_item_content`. At briefing persistence, the safe snapshot is stored transactionally. Existing briefings are not rewritten.
4. Reader joins `briefing_item_content` when available. Legacy/no-snapshot items are displayed as `Kaynak/orijinal metin`; no page-time translation or fabricated Turkish text is attempted.
5. Generic “important because” / placement filler text was removed. Placement explanations only appear for concrete signals: explicit/adaptive preference, World global importance, Action Required classification, or Worth Watching classification.
6. Feedback endpoint uses existing `feedback_events` and `interest_profile`: `more`/`less` change only explicit interest immediately; one `not_useful` event does not alter adaptive interest. World in Brief feedback is recorded but cannot affect its ranking/profile.
7. The browser now presents a Turkish confirmation, marks the clicked feedback action selected, and restores an existing explicit `more`/`less` choice after reload (including a title fallback where an event has no entity metadata).

Important files:

- `app/llm/core.py` — `ExtractorResult`, `ExtractionFlow.extract`
- `app/briefing/core.py` — `BriefingItem` persisted display fields
- `app/jobs/rss_runtime.py` — outbox persistence and transactional snapshot creation
- `app/jobs/youtube_runtime.py` — passes Turkish extraction fields to briefing candidates
- `app/briefing/presentation.py` — safe reader models, legacy fallback, placement explanation
- `app/api/admin.py` — briefing detail load and feedback endpoint
- `app/templates/briefing.html` — reader and feedback UI
- `migrations/versions/20260908_0015_briefing_turkish_snapshot.py`
- `tests/test_briefing.py`, `tests/test_admin.py`

## Important limitations / likely follow-up

- Do not claim a real deployment has the latest code until the operator rebuilds/restarts the app and runs Alembic migration `20260908_0015`.
- Existing historical briefings do not have snapshots and intentionally stay original-language with a label. They do not have structured per-item feedback.
- `briefing_title` is optional in the current structured extractor schema for compatibility with prior cached/provider outputs. New provider output is explicitly instructed to return it in Turkish; if absent, the reader safely falls back to the source title and labels source/original text. If stricter Turkish-title enforcement is desired, introduce it carefully with cache/version migration and fixture updates rather than breaking old structured cache records.
- `why_important_tr` is deliberately blank unless a justified persisted value exists. Model inferences are shown separately and explicitly labelled; do not reinstate generic relevance prose.
- Gmail outbox entries predate the new snapshot enrichment path and may use their safe classification summary. Preserve the existing no-email-body boundary.
- The default full suite skips `tests/test_search_postgres_integration.py` unless `SEARCH_INTEGRATION_DATABASE_URL` points to a dedicated disposable migrated PostgreSQL database.

## Last verified commands

Run from workspace root using the existing virtual environment:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\ruff.exe check .
& .\.venv\Scripts\alembic.exe upgrade head --sql
git diff --check
```

Latest result after the M16 refinement: **128 passed, 1 skipped, 2 upstream deprecation warnings**; Ruff, generated Alembic SQL through `20260908_0015`, and `git diff --check` passed. No external API call was made.

## Sensible next-agent starting sequence

1. Read `AGENTS.md`, `docs/PROGRESS.md`, then this note; inspect `git status` before edits.
2. Confirm the operator’s next requested milestone. Do not infer permission to make live provider calls, alter OAuth configuration, migrate production DBs, or expose any private data.
3. If validating M16 in a real local deployment, first back up the database, apply the non-destructive migration, rebuild/restart, create a fresh briefing from newly processed content, and inspect only the rendered safe metadata. Do not use a new live run unless the user explicitly requests it.
4. Keep `PROGRESS.md` current: acceptance criteria, exact offline test result, relevant migration, and known limitation.
