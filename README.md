# Personal Intelligence System

Self-hosted, code-first daily intelligence briefing service. The project is being delivered
milestone by milestone; see [progress](docs/PROGRESS.md) for the current implementation state.

## Local development

Requires Python 3.12+ and Docker Desktop for the full development stack.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Start Postgres/pgvector and the API:

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

The database is exposed on `localhost:5433` by default so an existing PostgreSQL service on
`5432` is not interrupted. To use another free host port, set `POSTGRES_HOST_PORT` in `.env`
before running Compose; the application container always connects to `db:5432` over the internal
Compose network. This setting does not affect the API port (`8000`).

`/health` reports process liveness. `/ready` checks database connectivity and returns HTTP 503
until Postgres is reachable. The application runs `alembic upgrade head` before starting Uvicorn,
so `docker compose up` applies the current schema automatically. Neither endpoint requires an
external API key.

Stop the stack with `docker compose down`; named database data is retained. To intentionally
remove local database data as well, use `docker compose down --volumes`.

## Local admin dashboard

Open `http://localhost:8000/admin` after the stack is running. The dashboard is a lightweight
local/VPS operations screen: it shows readiness and migration state, lets you add/enable/delete
RSS or YouTube sources, edit role-based model IDs, set explicit interest overrides, run the
connected job, inspect recent briefings/events, and view the metadata-only LLM ledger.

For a first RSS → LLM → briefing test, set `OPENROUTER_API_KEY` in `.env`, configure valid model
IDs in `config/models.example.yaml`, then add and enable a valid RSS source. The RSS runtime job is
bound at application startup and reloads source/model settings for each manual run. It applies
freshness and deduplication before OpenRouter gatekeeper/extractor calls, then writes events,
claims, LLM metadata, and a local briefing preview. Gmail needs its separate OAuth runtime setup
and is not needed for an RSS-only first test.

## Daily RSS schedule

The scheduler is off by default. To opt in, set `SCHEDULER_ENABLED=true` and set a strict local
time such as `SCHEDULER_DAILY_TIME=08:00` in `.env`, then rebuild/restart the app. The configured
timezone is `APP_TIMEZONE` (`Europe/Istanbul` by default). A durable daily claim prevents scheduler
restarts from creating a second scheduled briefing for the same local date. If a manual run and the
scheduled time overlap, the second operation safely reports an active-run skip rather than queueing
another provider request. The Admin Scheduler section shows the next run and durable, safe result
history. For the first check, choose a time a few minutes ahead, restart, verify the single claimed
row, then restore the desired daily time.

The Diagnostics table labels costs as provider-reported, configured estimates, or unavailable.
An unavailable value is not a claim that the provider call was free.

## Search / Ask

The Admin **Search / Ask** section accepts Turkish questions and optional date, entity, category,
topic, and source-type filters. It first narrows retained event metadata and ranks the bounded set;
only the top compact candidates can be sent to the configured `reasoner` model. Results show event
dates, source URLs, source-backed claims, stored inferences, and new model inferences separately.
No result returns `Yeterli kaynak bulunamadı.` without an LLM call. Gmail results use only the
existing classification/action summary/deadline/company records—never message bodies, subjects,
senders, or tokens. Events created before the Search metadata migration can lack original source
URLs or metadata filters, but stay title/claim/date searchable.

## Gmail status

Gmail is disabled by default: set `GMAIL_ENABLED=true`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`,
`APP_ENCRYPTION_KEY`, and `GMAIL_OAUTH_REDIRECT_URI` only after creating a read-only Google OAuth
client. Generate the encryption key once with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, put
the resulting URL-safe base64 value in the deployment secret store, and do not change it while an
account is connected. The panel never displays tokens or email bodies. Use the panel's **Connect
Gmail account** link to authorize a mailbox. The authorization callback stores only an
authenticated-encrypted refresh token. Any old test-stage XOR token requires reconnecting the
account; it is never decrypted or migrated.

An enabled, connected account is included in both manual and scheduled runs. Its first sync checks
only INBOX mail from the recent bounded window (`GMAIL_INITIAL_LOOKBACK_HOURS=48`) and processes at
most `GMAIL_INITIAL_MAX_MESSAGES=25` messages; later runs use the account's Gmail `historyId`.
These defaults need no extra `.env` values. The collector requests message metadata only (`From`,
`Subject`, `Date`), never persists bodies, and sends deterministic LinkedIn/newsletter noise to the
muted count before any optional LLM boundary. Gmail failures are counted but do not stop RSS.

## YouTube channels

The Admin **Sources** form accepts a public YouTube channel ID (normally beginning with `UC`), not
a channel page URL. Choose **YouTube channel**, enter a name and channel ID, add it disabled, then
enable it. The daily/manual job discovers uploads only through YouTube's public Atom channel feed.
It applies the configured 72-hour freshness boundary and persistent video identity deduplication
before fetching captions. `yt-dlp` is used for VTT captions only—no video or audio download is
requested. Captionless videos are safely reported as skipped, and YouTube failure does not stop
RSS or Gmail. The briefing's **Worth Watching** section includes the video URL, publication time,
and compact extractor-derived reason to watch.

Optionally select `tr` or `en` in the source form. The job then requests only that language family
(including common regional variants), and prefers human subtitles over automatic captions within
that family. It never falls back to an unrelated-language subtitle: such a video is counted as
`skipped_no_preferred_language_caption` before any LLM call. Existing sources with no language
selection retain the prior caption behavior. Admin separates no-caption, preferred-language-missing,
YouTube-feed access, and yt-dlp caption-access outcomes.

### Retrying a blocked YouTube item

The **Blocked YouTube items** table shows only title, channel, publication time, safe failure
category, and block time. Normal/manual scheduled ingestion continues to skip these videos. Use
**Retry once** only when you intentionally want another model attempt. The database atomically
claims the retry, so double clicks and concurrent requests cannot create a second attempt. A
successful retry removes the block and creates a `Worth Watching` briefing entry; another failure
updates the safe category and re-blocks the video. Old blocks from before this metadata feature are
shown with unavailable metadata; their explicit retry makes a bounded current channel-feed lookup
to recover the item before attempting captions/LLM work.

## CI

CI runs unit tests and Ruff. It deliberately does not call external providers or require
credentials. Database migrations are exercised by `docker compose` during local integration
verification.
