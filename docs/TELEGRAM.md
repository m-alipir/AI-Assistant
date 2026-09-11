# Telegram bot interface

Telegram is an optional, disabled-by-default interface over existing persisted briefing, Search,
Ask, feedback, and notification services. It is not a second assistant, ingestion pipeline, task
system, browser, shell, or general-action surface.

## Commands

- `/ozet` returns the latest safe persisted briefing and short-lived feedback buttons.
- `/ara <sorgu>` uses deterministic bounded retrieval only; it makes no model request.
- `/sor <soru>` uses the existing bounded Ask route, including its configured provider budget,
  cache, source links, and fact/inference separation.
- `/durum` returns only a compact readiness and last-run state.
- `/start` provides a safe help message only after authorization; it never enrolls a user.

Only a configured exact `user_id:chat_id` pair may use any command. The default deployment should
use one private chat (`same user_id:chat_id`). Group chat use is an explicit additional pair, not a
cross-product of independent user and chat allow-lists.

## Production configuration

Keep these non-secret values only in the protected production environment file:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_WEBHOOK_URL=https://intelligence.example.com/integrations/telegram/webhook
TELEGRAM_ALLOWED_ACTOR_PAIRS=<numeric-user-id>:<numeric-chat-id>
# Optional; every listed chat must already occur in TELEGRAM_ALLOWED_ACTOR_PAIRS.
TELEGRAM_NOTIFICATION_CHAT_IDS=
TELEGRAM_MAX_REQUEST_BYTES=8192
TELEGRAM_RATE_LIMIT_PER_MINUTE=10
TELEGRAM_GLOBAL_RATE_LIMIT_PER_MINUTE=20
TELEGRAM_MAX_CONCURRENT_COMMANDS=1
```

The bot token and webhook secret must be separate regular files outside the repository, owned by
container UID `10001` and mode `0400`. The webhook secret is 32–256 URL-safe characters. Set the
host paths only for the deployment command, then start with the optional secret mount:

```text
docker compose --env-file /etc/personal-intelligence/app.env \
  -f compose.production.yaml -f compose.telegram.production.yaml up -d --build
docker compose --env-file /etc/personal-intelligence/app.env \
  -f compose.production.yaml -f compose.telegram.production.yaml exec app \
  python -m app.telegram.configure_webhook
```

The setup command reads the mounted files and prints only a success/failure category. It configures
only `message` and `callback_query` updates with two Telegram-to-app connections. It is never run
automatically at startup. Do not use polling in this deployment.

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

Never paste a bot token, webhook secret, Telegram message, database row, or raw proxy log into a
ticket or chat.
