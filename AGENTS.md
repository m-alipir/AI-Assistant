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

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Delegated delivery

- The coordinator owns scope, `docs/PROGRESS.md`, the active `docs/AGENT_BRIEF.md`, task assignment, and acceptance. Normally it does not inspect or edit application code. Assign code review to a reviewer agent. Direct code intervention is reserved for an urgent issue when delegation cannot safely resolve it.
- When the user asks to see the plan first, explain the plan and stop. Start agents or implementation only after the user explicitly approves that plan. This does not interrupt work the user has already told the coordinator to continue.
- For each requested feature or fix, update the relevant milestone and acceptance criteria in `docs/PROGRESS.md`, then replace the single active brief with a short outcome, boundaries, and 1-3 independent assignments. Use separate worktrees or non-overlapping files for simultaneous edits. Do not create permanent per-task brief archives; Git history retains them.
- Reuse a standing pool of at most three subagents across tasks; reassign idle agents instead of spawning a new one for every job. Refresh the pool periodically when its context becomes stale or roles materially change. Implementation, reviewer, optimizer, and security assignments use `gpt-6-luna` with `xhigh` reasoning by default (`max` only when useful). The coordinator waits for final deliverables rather than directing every intermediate step. Each final report states changed files, checks and results, remaining risks, and decisions needed.
- Delegate only substantial, independent work when parallel execution meaningfully shortens delivery. Keep small related tasks together instead of splitting them among agents merely to fill the three available slots.
- A reviewer checks code changes before acceptance. An optimizer and a security reviewer audit after major milestones or roughly 20 small changes; earlier review is appropriate for a measured regression or a changed trust boundary. Their audits start read-only. Implement only concrete, scoped fixes after evidence supports them.
- Optimizer: measure a representative baseline and after result, preserve behavior, and prefer deleting duplication or using existing facilities. Skip speculative caches, dependencies, and micro-optimizations without meaningful measured gain. Security reviewer: check authorization, injection, secrets, unsafe output and VDS-facing boundaries; preserve narrow fail-closed guards and add a negative-path check for each fix.
- Keep production/VDS actions, live provider spending, secret handling, and destructive data changes out of delegated work unless the user has authorized the exact scope. Ask the user for material product choices or unavailable credentials after independent work is complete.
