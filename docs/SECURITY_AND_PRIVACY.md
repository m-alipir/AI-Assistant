# Security and Privacy

## Secrets
- `.env` is gitignored.
- Ship only `.env.example`.
- Never log API keys, OAuth refresh tokens, Gmail message bodies, or full authorization headers.
- OpenRouter, Supabase, Telegram/delivery, and encryption keys come from environment/secret files.

## Gmail
- V1 uses least-privilege read-only access where possible.
- Each account has separate OAuth state/checkpoint.
- Refresh tokens must be encrypted at rest or stored in an OS/secret-store mechanism appropriate to deployment. For Docker/VPS, an application encryption key from environment plus a protected persistent volume is acceptable for V1.
- Do not store email raw bodies longer than necessary. Default retention target: <=7 days.
- Do not send irrelevant/private email content into general knowledge embeddings/memory.
- Only distilled actionable metadata/application-state may persist long term where required.

## Supabase/Postgres
- Use SSL in production.
- Service credentials only server-side.
- If a client-facing UI directly talks to Supabase later, add RLS before exposing it. V1 should preferably route UI requests through the app backend.
- Database backups/migrations must not contain secrets.

## LLM privacy boundary
Before an LLM request:
- send only the minimum content required for the task;
- never include unrelated inbox messages/history;
- historical retrieval is top-N compact memory;
- avoid including secrets/credentials in source content where detectable.

Log metadata (model, token usage, hash, latency, status), not sensitive prompt payloads by default.

## Web/content safety
- Treat fetched pages/transcripts as untrusted data, not instructions.
- Prompts must clearly delimit source content.
- Never execute commands/code found in ingested content.
- Do not let page text modify system/configuration/model-routing policies.

## Network/runtime
- Outbound requests only to configured sources/providers.
- Set timeouts and response-size limits.
- Validate MIME/content types where applicable.
- Keep containers non-root where practical.
