# AGENTS.md — Personal Intelligence System

## Mission
Build a self-hosted, low-cost personal intelligence system that ingests fresh public information and email, distills it into sourced structured knowledge, connects new events to relevant historical memory, and produces a concise daily briefing.

This repository is intentionally **code-first, LLM-escalation-second**. Deterministic code must handle work that does not require semantic understanding. LLM calls are reserved for classification ambiguity, extraction, correlation/reasoning, and final editorial synthesis.

## Mandatory reading order before implementation
1. `docs/PRODUCT_SPEC.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/PIPELINES.md`
5. `docs/MODEL_ROUTING.md`
6. `docs/INTEREST_LEARNING.md`
7. `docs/SECURITY_AND_PRIVACY.md`
8. `docs/PROGRESS.md`
9. `docs/DECISIONS.md`

If a task touches only one subsystem, still read `PRODUCT_SPEC.md`, `PROGRESS.md`, and the relevant subsystem document before editing.

## Non-negotiable product rules
- Do not drop globally important news just because it does not match the user's interests. Put it in a separate **World in Brief / Dünyada Neler Oldu?** section.
- Apply freshness filtering **before expensive processing**. RSS feeds may contain weeks-old entries.
- Never use a frontier/expensive LLM for work deterministic code or a cheap model can do.
- Do not send entire historical memory or entire inboxes to an LLM.
- Facts/source claims and model inferences must be stored separately.
- Every retained fact/event must preserve provenance back to source item(s).
- Interest learning must be slow and stable. Do not mutate the profile on every message or click.
- Explicit user preferences (e.g. “show me more NVIDIA”) take effect immediately; inferred preference changes require repeated evidence over time.
- Model IDs must be configuration-driven. Do not hardcode a specific frontier model into business logic.
- Prefer direct OpenRouter HTTP/API integration. Do not introduce LangChain/LlamaIndex unless a concrete requirement justifies the dependency.
- Prefer PostgreSQL/Supabase + pgvector. Qdrant is not part of V1 unless scale/performance evidence justifies it.
- Gmail access is read-only in V1.
- Existing user code for yt-dlp/OpenRouter may be reused only after inspection and refactoring; never blindly copy it.

## Engineering rules
- Python 3.12+.
- Type hints on public functions and service interfaces.
- Pydantic models for external/LLM structured data boundaries.
- Async I/O for network-bound ingestion where useful, but avoid needless async complexity.
- Database migrations via Alembic.
- Unit tests for deterministic logic; integration tests must use fakes/mocks by default and must not spend API credits.
- External calls must have timeouts, bounded retries, and structured error logging.
- Idempotency is mandatory for ingestion and scheduled jobs.
- Store timestamps in UTC; render user-facing times in configured timezone (`Europe/Istanbul` by default).
- Secrets never enter Git, logs, prompts, fixtures, or `PROGRESS.md`.
- No destructive DB migrations without an explicit migration path/backfill plan.

## Progress discipline
`docs/PROGRESS.md` is the source of truth for implementation state.

For every meaningful task:
1. Read it first.
2. Work only inside the currently active milestone unless a prerequisite fix is required.
3. Run the tests listed for that milestone.
4. Update checkboxes/status, tests run, relevant files, and blockers before ending the task.
5. Do not mark a feature complete just because code exists; mark complete only when acceptance criteria and tests pass.
6. Record architectural changes in `docs/DECISIONS.md`.

Do not silently expand scope. Put non-blocking ideas in the Backlog section of `PROGRESS.md`.

## Definition of done for each milestone
- Implementation complete.
- Tests added/updated and passing.
- Config/example files updated if behavior changed.
- Failure modes produce actionable logs.
- `PROGRESS.md` updated.
- No secrets or credentials committed.
