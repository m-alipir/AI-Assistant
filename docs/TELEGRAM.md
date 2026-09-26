# Telegram bot interface

Telegram is an optional, disabled-by-default interface over existing persisted briefing, Search,
Ask, feedback, and notification services. It is not a second assistant, ingestion pipeline, task
system, browser, shell, or general-action surface.

`TELEGRAM_MODE=webhook` is the existing default. `TELEGRAM_MODE=polling` runs an outbound-only
long-poll worker and requires no domain, reverse proxy, TLS certificate, or inbound HTTP port.

## Commands

- `/ozet` returns the latest safe persisted briefing and short-lived feedback buttons.
- `/ara <sorgu>` uses deterministic bounded retrieval only; it makes no model request.
- `/sor <soru>` uses the existing bounded Ask route, including its configured provider budget,
  cache, source links, and fact/inference separation.
- `/durum` returns compact readiness, recent scheduled/manual run, briefing, and source counts.
- `/gecmis [sayı]` lists up to ten persisted briefings; `/ozet` still opens the latest one.
- `/kaynaklar` lists at most 30 persisted RSS/YouTube sources with enabled and health state.
- `/kaynak <id>` shows one source's endpoint, enabled state, health, and safe last-error category.
- `/kaynak_ekle [rss|youtube] <endpoint> [name]` validates and adds one source disabled by default.
- `/kaynak_ac <id>` and `/kaynak_kapat <id>` enable or disable one source.
- `/kaynak_sil <id>` deletes only an already-disabled source.
- `/kaynak_kategori <id> <category>` answers a pending category question in the authorized chat
  (up to 128 characters); it changes only that source's category.
- `/ilgiler`, `/ilgi_ekle <konu>`, and `/ilgi_sil <konu>` use the existing stable interest profile.
- `/yardim` and `/start` show help only after authorization; they never enroll a user.

Source commands are intentionally chat-first and reuse the same database repository as Admin and
ingestion. Telegram has no YAML source read/write path. Duplicate, invalid, missing, unsafe-delete,
and repository/database failures are returned as concise Turkish messages without database or
provider details.

Only a configured exact `user_id:chat_id` pair may use any command. The default deployment should
use one private chat (`same user_id:chat_id`). Group chat use is an explicit additional pair, not a
cross-product of independent user and chat allow-lists.

Source changes are atomically persisted in the database-managed source repository. They survive
restarts and are picked up by the next scheduled run; no Telegram input
can request an arbitrary fetch, alter private-network protections, or bypass normal freshness,
deduplication, caption, retry, and budget boundaries. Gmail stays read-only and is connected once
through the protected browser OAuth flow; scheduled runs then use its existing durable checkpoint.

Clear known RSS publisher domains receive a deterministic category during source creation; this
does not change the source's `tech`/`world` stream. An unknown category is left empty and queues one
plain-text question containing only the source ID, never its endpoint or feed content. At most three
pending sources are asked per scan; this is an application batch limit, not a Telegram per-minute
limit. Questions go
to `TELEGRAM_SOURCE_OPERATOR_CHAT_ID`, which must be an exact allow-listed chat. A bounded database
scan retries uncategorized sources after restart or Telegram configuration changes, in webhook and
polling deployments. `/kaynak_kategori <id> <category>` is accepted only in a chat with a persisted
delivered question receipt, and an existing category is never overwritten. The question uses the
existing channel-scoped notification receipt, so repeat processing cannot send another successfully
recorded question to that chat.

This is the **current** fallback: unknown sources may produce several UUID-only category messages
as the bounded pending queue drains. The planned M22.4 flow asks for a category while adding a
single source, shows built-in and previously created choices, accepts a new category, and identifies
the source by name. OPML will carry or collect category choices during import. Until M22.4 is
implemented, the command and pending-question behavior above remain the actual interface.

## Production configuration

Keep these non-secret values only in the protected production environment file:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://intelligence.example.com/integrations/telegram/webhook
TELEGRAM_ALLOWED_ACTOR_PAIRS=<numeric-user-id>:<numeric-chat-id>
# Exact allow-listed chat for Admin-created ambiguous-source questions.
TELEGRAM_SOURCE_OPERATOR_CHAT_ID=<numeric-chat-id>
# Proactive daily briefings; every listed chat must already occur in TELEGRAM_ALLOWED_ACTOR_PAIRS.
TELEGRAM_NOTIFICATION_CHAT_IDS=<numeric-chat-id>
TELEGRAM_MAX_REQUEST_BYTES=8192
TELEGRAM_RATE_LIMIT_PER_MINUTE=10
TELEGRAM_GLOBAL_RATE_LIMIT_PER_MINUTE=20
TELEGRAM_MAX_CONCURRENT_COMMANDS=1
```

The bot token and webhook secret must be separate regular files outside the repository, owned by
container UID `10001` and mode `0400`. The webhook secret is 32–256 URL-safe characters. Set the
host paths only for the deployment command, then start with the optional secret mount:

```text
docker compose --env-file .env.production \
  -f compose.production.yaml -f compose.telegram.production.yaml up -d --build
docker compose --env-file .env.production \
  -f compose.production.yaml -f compose.telegram.production.yaml exec app \
  python -m app.telegram.configure_webhook
```

The setup command reads the mounted files and prints only a success/failure category. It configures
only `message` and `callback_query` updates with two Telegram-to-app connections. It is never run
automatically at startup. Do not use polling in this deployment.

When scheduling is enabled, preparation starts 15 minutes before the effective configured local
delivery time (including any saved Control Center preference). A newly persisted briefing is held
until that time, or sent when ready with a delay note if processing finishes late. Empty runs do not
send a message. The first 14 successfully delivered briefing days may include up to three
metadata-derived interest questions; their one-use buttons update the existing adaptive profile
in small increments and then stop automatically.

## Outbound-only polling deployment

Use polling only with one `telegram-poller` replica. Its protected environment needs no
`TELEGRAM_WEBHOOK_URL` or webhook-secret setting:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_MODE=polling
TELEGRAM_ALLOWED_ACTOR_PAIRS=<numeric-user-id>:<numeric-chat-id>
TELEGRAM_POLLING_TIMEOUT_SECONDS=30
TELEGRAM_POLLING_BATCH_LIMIT=25
TELEGRAM_POLLING_MAX_BACKOFF_SECONDS=30
```

Mount only the existing bot-token and runtime database secret files, then use the polling overlay:

```text
docker compose --env-file .env.production \
  -f compose.production.yaml -f compose.telegram.polling.production.yaml up -d --build
```

The overlay removes app host-port publication and adds an outbound-only `telegram-poller` with
`restart: unless-stopped`. On every start it calls `deleteWebhook` with pending updates preserved,
then uses `getUpdates` for `message` and `callback_query` only. The cursor stores only the next
numeric offset; the existing durable update receipt remains the duplicate-work barrier.

## Security and privacy

- The public endpoint accepts only a bounded JSON `POST` and uses Telegram's secret-token header
  in constant time. Wrong secret and unauthorized identities receive no data and create no audit
  entry.
- Telegram `update_id` is claimed durably before a command. A duplicate cannot repeat a model call
  or feedback mutation. Read-only claims can be reclaimed only after their bounded processing lease;
  existing model cache/budget rules remain the cost boundary.
- The database retains only `update_id`, hashes of actor/chat identifiers, kind, timestamps, and a
  safe outcome category. It never retains command text, reply text, provider bodies, or Telegram
  response bodies. Feedback button tokens are actor-bound, random, one-use, and expire after 24h.
- Every accepted feedback callback makes a bounded `answerCallbackQuery` request with a fixed short
  success or invalid-button message, so Telegram's loading indicator closes without exposing a
  token, identity, database detail, or provider response. Its timeout/retry/error policy is the
  same bounded Bot API boundary as ordinary delivery.
- Polling retains the same exact identity pairs, command/model limits, feedback rules, update
  deduplication, source-link filtering, and safe failure categories as webhook delivery.
- Outgoing messages are literal plain text with previews disabled and protected-content requested.
  There is no Telegram Markdown/HTML parser surface. Existing HTTPS-only provenance links are the
  only links rendered.
- The reverse proxy must limit this path to a small request body, short request timeout, and a
  conservative request rate; it must never log request bodies or the secret header.

## VDS smoke test

With no scheduler or unapproved source/provider run enabled, verify:

1. `getWebhookInfo` shows the expected HTTPS URL and no persistent delivery error.
2. A valid allow-listed `/durum` responds; an unallow-listed user gets no bot response and causes no
   query, feedback, model, or database-audit work.
3. Replay one captured safe fixture update ID: the second delivery creates no model call or feedback
   event. Restart the app during a read-only command and verify only the expired claim can recover.
4. Exercise `/ozet`, `/ara`, `/sor`, `/durum`, and one feedback button with fixture data; inspect
   only safe categories and confirm that tokens, IDs, command text, and reply text are absent.
5. Temporarily block Telegram egress and verify ingestion, Admin, health, and readiness remain
   available; restore egress and confirm a new user command works.

For `TELEGRAM_MODE=polling`, instead verify that no host port is published, the poller removes an
old webhook without dropping pending updates, and `/ozet`, `/ara`, `/sor`, `/durum`, feedback,
unauthorized identities, duplicate updates, restart recovery, and temporary outbound failure retain
the same safe behavior. Do not run the webhook configuration command in polling mode.

Never paste a bot token, webhook secret, Telegram message, database row, or raw proxy log into a
ticket or chat.
