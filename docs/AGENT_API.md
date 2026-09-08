# Read-only Agent API

## Purpose and trust boundary

This is a generic, versioned integration surface for an external orchestration agent such as
Hermes. It is not a Hermes SDK and does not grant that agent database, shell, Admin, Gmail OAuth,
OpenRouter, or source-management access. The API contains no mutation endpoint: feedback, source
management, scheduler control, Gmail connection, and blocked-item retries remain Admin-only.

The API is disabled by default. It returns only bounded projections of persisted briefings and the
existing bounded Search/Ask result: compact summaries, source links/dates, source-backed facts,
explicitly named stored/model inferences, and safe Gmail action classification/summary/deadline
metadata. It never selects or returns Gmail sender, subject, body, OAuth material, provider
credentials, raw RSS/transcript content, Admin configuration, SQL, filesystem paths, or internal
error detail.

## Configuration

Set these values only in the protected deployment environment or secret store; do not put a real
token in the repository. `AGENT_API_TOKEN_FILE` takes precedence over `AGENT_API_TOKEN`.

```dotenv
AGENT_API_ENABLED=true
AGENT_API_TOKEN_FILE=/run/secrets/agent_api_token
AGENT_API_RATE_LIMIT_PER_MINUTE=30
AGENT_API_MAX_REQUEST_BYTES=2048
AGENT_API_MAX_RESPONSE_BYTES=65536
```

The token must be distinct from the Admin password and contain at least 24 characters. A missing
or short token makes an enabled configuration fail at startup. Store it in a regular, runtime-user
readable secret file outside the repository. The application redacts its configured value from
logs. Keep the API behind the same TLS proxy, host allow-list, and network policy as the app;
`FORCE_HTTPS=true` also covers `/api/v1/...` routes.

## Authentication and limits

Send the token only in `Authorization: Bearer <agent-api-token>`. Missing/wrong tokens return 401;
disabled API routes return 404. Responses use `Cache-Control: no-store` and `Vary: Authorization`.

- Rate limiting is a small process-local rolling one-minute limit. It stores no caller identity,
  request text, or token. A future multi-replica deployment needs a shared limiter before using
  more than one application process.
- Briefing list pages allow 1–20 rows. `before` is an ISO-8601 timestamp cursor.
- Search requests and every JSON response are size-bounded. An over-limit request/response returns
  413 with a generic error.
- Each endpoint writes only `occurred_at`, endpoint category, outcome, and response byte count to
  `agent_api_audit_log`. The audit log deliberately excludes token, caller identity/IP, question,
  filters, source text, result content, and provider metadata.

## HTTP contract

All successful outputs are JSON. The fields `verified_facts`, `stored_inferences`, and
`model_inferences` must remain separate: facts are source-backed; inference fields are not facts.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/briefings/latest` | Latest persisted briefing and bounded items. |
| `GET` | `/api/v1/briefings?limit=10&before=<ISO-8601>` | Cursor-style briefing metadata page. |
| `GET` | `/api/v1/briefings/{briefing_id}` | One persisted briefing projection. |
| `POST` | `/api/v1/knowledge/search` | Existing bounded Search/Ask pipeline, with a safe result projection. |

`POST /api/v1/knowledge/search` accepts the existing bounded filter shape:

```json
{
  "question": "NVIDIA hakkında bu hafta ne oldu?",
  "since": "2026-09-01T00:00:00Z",
  "entity": "NVIDIA",
  "source_type": "rss",
  "limit": 5
}
```

The search request remains on the existing deterministic narrowing path. If candidates exist, its
optional reasoner call still uses the configured model role, normal budget rules, cache, and shared
provider-work coordination. A no-result response is `status: "insufficient_sources"` and makes no
model request. The Agent API intentionally omits LLM call/cost/provider fields from its response.

## Hermes HTTP-tool example

Configure an HTTP tool with base URL `https://intelligence.example.com`, a secret header
`Authorization: Bearer ${PERSONAL_INTELLIGENCE_AGENT_API_TOKEN}`, and no additional credentials.
For example:

```text
GET  /api/v1/briefings/latest
POST /api/v1/knowledge/search
     {"question":"Bugünkü kritik gelişmeler neler?","limit":5}
```

Treat returned facts and inference arrays differently in Hermes prompts/UI. Hermes must not infer
that it can call Admin routes, write preferences, connect Gmail, or access the host/coding worker
because this read-only HTTP tool exists.

## Pre-connection security check

1. Keep `AGENT_API_ENABLED=false` until TLS, production host allow-list, and Admin hardening are
   verified in staging.
2. Generate a unique high-entropy Agent API token, put it in the secret store/file, and confirm it
   differs from Admin, Gmail, OpenRouter, and database secrets.
3. Apply Alembic revision `20260908_0016` after an encrypted backup/isolated restore check.
4. Verify disabled, missing-token, wrong-token, rate-limit, request/response-size, and no-store
   behavior using synthetic/staging data only. Inspect the audit table only for metadata fields.
5. Give Hermes only this token and these HTTPS routes. Do not mount the app environment file, Docker
   socket, database credentials, OAuth token store, or any shell/filesystem capability into Hermes.
