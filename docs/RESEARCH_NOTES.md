# Research Notes (checked 2026-09-06)

These references justify architecture choices but are not a substitute for checking current docs while implementing.

## Codex / repository guidance
- OpenAI documents `AGENTS.md` as repository guidance for navigation, test commands, conventions, and persistent project context.
  - https://openai.com/index/introducing-codex/
  - https://openai.com/business/guides-and-resources/how-openai-uses-codex/

## OpenRouter
- Structured Outputs support JSON Schema (`response_format.type=json_schema`) and strict schemas on compatible models.
  - https://openrouter.ai/docs/guides/features/structured-outputs
- The Models API exposes model IDs, supported parameters, pricing and sorting/filtering, useful for an advisory model-catalog view.
  - https://openrouter.ai/docs/guides/overview/models
  - https://openrouter.ai/docs/api/api-reference/models/get-models
- Embeddings are available through `/api/v1/embeddings`.
  - https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings
- Prompt caching exists on supported model/provider combinations, but application-level semantic task-result caching is still required because it solves a different problem.
  - https://openrouter.ai/docs/guides/best-practices/prompt-caching

## Supabase / pgvector
- Supabase supports Postgres `pgvector` vector columns and similarity search.
  - https://supabase.com/docs/guides/ai/vector-columns
  - https://supabase.com/docs/guides/database/extensions/pgvector
- Supabase recommends HNSW generally when an ANN index becomes necessary; do not prematurely index tiny datasets without measuring.
  - https://supabase.com/docs/guides/ai/vector-indexes

## Gmail
- Gmail supports `history.list` for incremental mailbox change synchronization.
  - https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list
- Gmail also supports Pub/Sub push via `users.watch`, but watch must be renewed at least every 7 days and Google recommends daily renewal. This is unnecessary infrastructure for V1 personal polling.
  - https://developers.google.com/workspace/gmail/api/guides/push
  - https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/watch

## YouTube / yt-dlp
- YouTube Data API caption listing/downloading uses authenticated caption resources and is not the preferred path for arbitrary public-video transcript ingestion.
  - https://developers.google.com/youtube/v3/docs/captions/list
- yt-dlp supports normal and automatically generated subtitle extraction (`--write-subs`, `--write-auto-subs`) and should be the V1 transcript path.
  - https://github.com/yt-dlp/yt-dlp/blob/master/README.md

## RSS source examples
Do not make the application dependent on these exact feeds; use config.
- Ars Technica officially exposes multiple RSS feeds.
  - https://arstechnica.com/rss-feeds/
- TechCrunch exposes RSS for news-reader consumption subject to its feed terms.
  - https://techcrunch.com/subscribing/
  - https://techcrunch.com/rss-terms-of-use/
- The Verge states existing RSS feeds remain available, though subscriber content can be preview-only.
  - https://www.theverge.com/ (discover actual current feed URL during source setup)
- BBC provides established news/technology RSS feeds; verify exact feed URLs at setup time.

## Implementation note
External APIs, model IDs, pricing, and feed URLs can change. The code must make these configurable and fail visibly rather than relying on undocumented constants.
