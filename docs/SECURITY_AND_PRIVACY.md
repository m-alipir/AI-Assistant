# Security and Privacy

## Secrets
- `.env` is gitignored.
- Ship only `.env.example`.
- Never log API keys, OAuth refresh tokens, Gmail message bodies, or full authorization headers.
- OpenRouter, Supabase, Telegram/delivery, and encryption keys come from environment/secret files.
- Production secrets may be supplied via `*_FILE` settings mounted at `/run/secrets/...`; a file
  takes precedence over its paired environment variable. Do not put secret values in Compose YAML,
  source configuration, fixture data, shell history, or support screenshots.
- `APP_ENCRYPTION_KEY`, `OPENROUTER_API_KEY`, `GMAIL_CLIENT_SECRET`, `ADMIN_PASSWORD`, and
  `DATABASE_URL` have file-backed variants. Secret files must be regular files, readable only by
  the runtime user, and remain outside the repository. Docker daemon/root administrators can still
  inspect a running container's environment: treat Docker-host administration as privileged.

## Threat model and trust boundaries

| Asset / boundary | Primary threat | Implemented control | Residual risk |
| --- | --- | --- | --- |
| Internet-facing Admin | guessed credentials, CSRF, UI embedding | production fail-closed Basic auth, constant-time comparison, same-origin checks for mutations, `no-store`, CSP/frame/referrer headers | Basic auth has no per-user audit/MFA/rate limit; put it behind VPN or an identity-aware proxy for multi-user use |
| OAuth callback | state replay, redirect/client misconfiguration | random single-use 10-minute state, bounded in-memory state count, exact configured redirect, safe error categories | state is process-local; a multi-replica deployment needs shared session/state storage |
| Gmail refresh tokens | database/backup theft or accidental logs | Fernet authenticated encryption, read-only scope, no token/body logging, legacy XOR values force reauthorization | encryption key and encrypted DB backup must be protected independently |
| PostgreSQL | public network access, credential theft, accidental deletion | private Compose network/no DB port, non-root app, backups/restore runbook | at-rest DB encryption and managed-DB RLS are operator responsibilities |
| RSS/YouTube URLs | SSRF, redirect to private address, hostile payload | production HTTPS-only public-IP validation on every redirect, timeout/size bounds, no general web crawl | DNS rebinding after resolution and compromised public sources remain possible |
| LLM prompts/Search | prompt injection, over-sharing Gmail/history | source text is data, bounded candidate retrieval, Gmail classification-only Search data, model outputs separated from source facts | a configured third-party model receives the selected public/compact data; review provider policy |
| Read-only Agent API | orchestration layer becomes a path to operational secrets, private email, or host control | disabled-by-default distinct bearer token, bounded projection/pagination/request-response sizes, rate limit, metadata-only audit, no-store response | process-local rate limit; multi-replica use needs shared limiting and any future write scope needs independent authorization design |

## Admin and browser access
- Development defaults keep `ADMIN_AUTH_ENABLED=false` for `localhost` only. Do not expose this
  mode beyond the developer machine.
- `APP_ENV=production` refuses to boot unless `ADMIN_AUTH_ENABLED=true`, a non-empty username,
  a 16+ character password (or password file), explicit `ALLOWED_HOSTS`, HTTPS
  `ADMIN_PUBLIC_ORIGIN`, and production source restrictions are set.
- State-changing Admin requests require the configured `Origin`; this is intentional CSRF
  protection. The Google callback is a `GET` and relies on the single-use OAuth state instead.
- API documentation/OpenAPI are disabled in production. `/health` and `/ready` remain unauthenticated
  for the local reverse-proxy/container health check only.
- Secure headers include CSP, `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, and `no-store`
  for Admin pages. Set `FORCE_HTTPS=true` only behind a trusted TLS proxy which sets
  `X-Forwarded-Proto: https`.

## Gmail
- V1 uses least-privilege read-only access where possible.
- Each account has separate OAuth state/checkpoint.
- Refresh tokens must be encrypted at rest or stored in an OS/secret-store mechanism appropriate to deployment. For Docker/VPS, an application encryption key from environment plus a protected persistent volume is acceptable for V1.
- The application uses `cryptography.fernet.Fernet` for authenticated encryption of refresh tokens.
  `APP_ENCRYPTION_KEY` must be one URL-safe base64 Fernet key generated with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  Keep it in the deployment secret store and stable for the lifetime of connected accounts; a
  replacement key cannot decrypt existing tokens.
- Legacy test-stage XOR token values are deliberately not migrated or decrypted. Their database
  rows are marked `legacy_xor` and require reconnecting the Gmail account, which writes a new
  `fernet-v1` value. Do not attempt to recover or log the old token values.
- A missing or invalid encryption key blocks OAuth token storage with a generic admin error. The
  callback never renders or logs authorization codes, access tokens, refresh tokens, or bodies.
- OAuth failures log only one safe category: `oauth_state_invalid_or_expired`,
  `token_exchange_invalid_client`, `token_exchange_redirect_mismatch`,
  `token_exchange_upstream_http_error`, `refresh_token_missing`, or `token_storage_error`.
  Google response bodies and `error_description` values are intentionally neither logged nor
  rendered. The local callback shows a safe Turkish remediation message and its category code.
- Gmail runtime sync uses the existing `gmail.readonly` grant only. It requests metadata headers
  (`From`, `Subject`, `Date`) and INBOX labels, not message bodies. Refresh/access tokens remain
  in memory only for the request; only deterministic classification/action metadata and a bounded
  briefing title are retained. Per-account failures report a count without logging provider bodies.
- Do not store email raw bodies longer than necessary. Default retention target: <=7 days.
- Do not send irrelevant/private email content into general knowledge embeddings/memory.
- Only distilled actionable metadata/application-state may persist long term where required.
- Revoke a compromised account in Google Account permissions, delete/reconnect its application
  record, rotate the affected OAuth client secret, and rotate the Fernet key only through a planned
  token reauthorization window. A Fernet-key rotation without reauthorization makes existing
  accounts intentionally unusable.

## Supabase/Postgres
- Use SSL in production.
- Service credentials only server-side.
- If a client-facing UI directly talks to Supabase later, add RLS before exposing it. V1 should preferably route UI requests through the app backend.
- Database backups/migrations must not contain secrets.
- Encrypt backups, restrict restore access, test a restore at least quarterly, and keep the Fernet
  key in a separate secret store. There is no destructive retention migration in this milestone;
  before adding automatic deletion, record a backup/restore and legal-retention plan.

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
- Production feed fetches reject plaintext HTTP and private, loopback, link-local, multicast,
  reserved, or unspecified DNS results before each request and redirect. Local development can
  explicitly retain private/HTTP fixture sources.

## Future agent and coding-worker boundary

Hermes is not a replacement runtime for this application. It is a future, separate orchestration
and user-facing agent layer. It must not have direct database connectivity, Gmail OAuth tokens,
OpenRouter secrets, or shell access through the AI Assistant deployment.

If an integration API is added, use versioned domain namespaces such as
`/api/v1/briefings/...`, `/api/v1/knowledge/...`, `/api/v1/preferences/...`, and
`/api/v1/system/...`; do not couple its shape or credentials to Hermes. Authentication,
authorization, rate limits, audit logging, and response-level data minimization are prerequisites
to exposing it outside the existing Admin trust boundary.

Future coding automation is a separate trust zone. A Hermes-controlled coding worker or Codex CLI
environment requires independent authorization and filesystem/shell isolation and must not inherit
the AI Assistant's database, Gmail, or provider-secret access.

M18 implements the first read-only endpoints under `/api/v1/briefings/...` and
`/api/v1/knowledge/search`. They use a token distinct from Admin Basic auth and are disabled unless
explicitly enabled with a valid environment/secret-file token. They return only the documented
bounded projections and record metadata-only audit fields. See `docs/AGENT_API.md`; any future
write endpoint requires a separate threat model and authorization decision.
