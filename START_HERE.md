# Start Here

1. Put this pack at the root of a new repository.
2. Open the repository in Codex.
3. Give Codex the contents of `CODEX_MASTER_PROMPT.md` as the initial task.
4. Codex should read `AGENTS.md` and the docs automatically as instructed.
5. Let it work milestone-by-milestone and require `docs/PROGRESS.md` to be updated on every task.

Do not add real API keys before M0/M1 unit tests work with fakes.

When you want Codex to reuse existing projects, provide their local paths/repository names and say:

> Inspect these projects before implementing the related integration. Reuse only proven yt-dlp/OpenRouter client, parsing, retry, or error-handling logic that fits this architecture. Refactor it behind the interfaces in this repository and record reused components in `docs/PROGRESS.md`.

Recommended first Codex instruction is exactly `CODEX_MASTER_PROMPT.md`; do not ask it to invent a second architecture before starting.
