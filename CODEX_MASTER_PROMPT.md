# Codex Master Prompt

You are implementing the Personal Intelligence System described in this repository.

Start by reading `AGENTS.md` and all documents it marks as mandatory. Treat those files as the product contract. Do not redesign the architecture casually.

## Objective
Create a Dockerized personal intelligence service that:
- ingests fresh technology/general-world news from configurable RSS feeds;
- monitors configured YouTube channels/videos and extracts available subtitles/transcripts using yt-dlp-based tooling, with optional transcription fallback later;
- monitors two or more Gmail accounts in read-only mode and surfaces only relevant/actionable mail;
- rejects stale RSS/video content before LLM processing;
- normalizes, deduplicates, categorizes, and clusters related sources into events;
- stores structured long-term memory in PostgreSQL/Supabase, with pgvector for semantic retrieval;
- organizes knowledge hierarchically by categories while also maintaining normalized entities and topics;
- stores source-backed facts/claims separately from LLM-generated inferences;
- selectively retrieves historical memory and reasons about meaningful connections;
- adapts interest weights slowly from repeated behavior while preserving a separate globally important-news stream;
- routes LLM work by role/cost/capability through OpenRouter;
- produces a concise daily briefing with provenance links and actionable email items;
- exposes a minimal local/admin API/UI for health, sources, model-role config, interest state, recent briefings, and manual runs.

## Implementation strategy
Proceed milestone-by-milestone using `docs/PROGRESS.md`. Do not attempt a giant one-shot implementation.

For each milestone:
1. State the milestone you are working on.
2. Inspect relevant existing code before creating parallel implementations.
3. Implement the smallest complete vertical slice that satisfies the milestone acceptance criteria.
4. Add tests.
5. Run tests and any lint/type checks configured by the project.
6. Update `docs/PROGRESS.md` with exact status and evidence.
7. Continue to the next milestone without asking for confirmation unless blocked by credentials, unavailable external resources, or a genuinely irreversible product decision.

## Cost discipline
Treat LLM tokens as a scarce resource.
- Run freshness, URL/GUID/content-hash dedup, sender rules, known aliases, and deterministic filters before LLM calls.
- Gatekeeper inputs should use title/description/metadata and only a small content sample where possible.
- Use structured outputs/JSON Schema for all machine-consumed LLM outputs.
- Use cheap models for gatekeeping/extraction; strong reasoning models only for high-value correlation and final editorial synthesis.
- Add response/result caching keyed by content hash + prompt version + model role/model ID.
- Track token usage and estimated cost per role/run/day.
- Never automatically switch production model IDs merely because a new cheaper model appears. A catalog refresh may suggest candidates; model changes remain configuration changes.

## Existing user projects
The user may provide paths/repositories containing proven yt-dlp and OpenRouter implementations (including a yt-dlp UI project and a Premiere plugin using OpenRouter). If available:
- inspect them first;
- extract only reusable clients/parsing/error-handling patterns;
- refactor into this project's interfaces;
- do not copy UI or unrelated application structure;
- record what was reused in `docs/PROGRESS.md`.

## Initial deliverable
Begin with Milestone M0 from `docs/PROGRESS.md`. Build the repository skeleton, config system, Docker development environment, database migration foundation, logging, health endpoint, test harness, and provider interfaces/fakes. Then continue in milestone order as far as the environment permits.
