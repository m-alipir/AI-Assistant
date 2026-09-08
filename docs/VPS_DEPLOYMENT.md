# Production VPS deployment

This deployment is intentionally different from local development. Local `compose.yaml` exposes
the application and a development PostgreSQL port for convenience. Production
`compose.production.yaml` binds the app only to `127.0.0.1`, keeps PostgreSQL on an internal
network, and requires authenticated HTTPS Admin access.

## Before starting

1. Create a dedicated non-login deploy user; protect the Docker socket because Docker daemon
   access is equivalent to access to running container secrets.
2. Put a root-owned production environment file outside the repository, for example
   `/etc/personal-intelligence/app.env` (`chmod 600`). Do not copy a real file into Git.
3. Set at least the following values. Replace the domain and values; do not reuse these examples.

```dotenv
POSTGRES_DB=intelligence
POSTGRES_USER=appdb
POSTGRES_PASSWORD=<long-unique-database-password>
DATABASE_URL=postgresql+asyncpg://appdb:<url-encoded-password>@db:5432/intelligence
APP_ENV=production
APP_TIMEZONE=Europe/Istanbul
ADMIN_AUTH_ENABLED=true
ADMIN_USERNAME=<unique-operator-name>
ADMIN_PASSWORD=<at-least-16-character-unique-password>
ADMIN_PUBLIC_ORIGIN=https://intelligence.example.com
# Keep 127.0.0.1 for the container health check; it is not publicly published.
ALLOWED_HOSTS=intelligence.example.com,127.0.0.1
FORCE_HTTPS=true
ALLOW_PRIVATE_SOURCE_URLS=false
ALLOW_INSECURE_SOURCE_URLS=false
SCHEDULER_ENABLED=false
GMAIL_ENABLED=false
AGENT_API_ENABLED=false
```

Use `OPENROUTER_API_KEY_FILE`, `GMAIL_CLIENT_SECRET_FILE`, `APP_ENCRYPTION_KEY_FILE`,
`ADMIN_PASSWORD_FILE`, and `AGENT_API_TOKEN_FILE` when an orchestrator can mount Docker secrets at
`/run/secrets/...`.
Otherwise keep the values only in the protected environment file. `APP_ENCRYPTION_KEY` must be a
stable Fernet key; changing it requires Gmail reauthorization. When Gmail is enabled, set
`GMAIL_OAUTH_REDIRECT_URI=https://intelligence.example.com/admin/gmail/callback` exactly in both
this file and Google Cloud Console.

4. Configure a TLS reverse proxy for `https://intelligence.example.com` to
   `http://127.0.0.1:8000`, preserve `Host`, and set `X-Forwarded-Proto: https`. Firewall the VPS:
   expose only SSH (restricted) and HTTPS; never publish PostgreSQL or port 8000 publicly. Prefer
   VPN or an identity-aware proxy in front of Basic auth for a shared/admin deployment.

## Start and verify

Run Compose with the same file used for interpolation and the app environment:

```powershell
docker compose --env-file /etc/personal-intelligence/app.env `
  -f compose.production.yaml up -d --build
```

Check `docker compose -f compose.production.yaml ps`, request `/health` through the proxy, and
sign in to `/admin`. Production startup intentionally fails if admin authentication, HTTPS origin,
host allow-list, or public/HTTPS source restrictions are missing. API docs are disabled in this
mode. Keep `SCHEDULER_ENABLED=false` until a manual ingestion test succeeds.

## M17 production verification checklist

Perform these checks in a staging VPS first, then repeat them during a planned production change
window. They do not require an RSS, YouTube, Gmail, or OpenRouter call.

1. Take an encrypted database backup and restore it to an isolated database. Confirm the restore
   can be migrated and queried there; keep the backup separate from the Fernet key and never copy
   the environment file into it.
2. Review the effective production Compose configuration locally on the VPS. Do not paste its
   output into tickets or chat because environment interpolation may reveal sensitive values.
   Confirm app port `8000` binds only to loopback and PostgreSQL has no published port.
3. Build and start with the protected environment file. Confirm the `app` and `db` health checks
   pass, then confirm the applied Alembic revision includes `20260908_0015` before relying on the
   M16 reader snapshot fields.
4. Through the TLS proxy, verify `/health`, `/ready`, a rejected unauthenticated `/admin` request,
   an authenticated Admin request, HTTPS forwarding, host allow-list behavior, no-store/security
   headers, and that API docs are unavailable. Inspect only safe operational logs.
5. Open an existing briefing and confirm its labelled legacy fallback works without a provider
   call. A newly generated Turkish snapshot requires an explicitly approved, controlled ingestion
   run; do not enable a source or scheduler merely for this checklist.
6. Leave `SCHEDULER_ENABLED=false`, `GMAIL_ENABLED=false`, and all live source/provider tests off
   until their separate, explicit operational approvals. Record only aggregate results and safe
   failure categories in the deployment log.

If enabling the M18 read-only Agent API after this checklist, keep `AGENT_API_ENABLED=false` until
its distinct token is mounted from the secret store and migration `20260908_0016` is applied. Then
run the synthetic token/limit/audit checks in `docs/AGENT_API.md`; do not give the external agent
the Admin password, Docker socket, environment file, database URL, Gmail material, or shell.

## Operations and recovery

- The app uses a non-root user, read-only root filesystem, dropped Linux capabilities, a bounded
  temporary filesystem, `no-new-privileges`, restart policy, health checks, and an internal DB
  network. The mounted `config` directory remains writable because Admin safely persists source,
  model, and interest configuration; restrict that host directory to the deploy user and make it
  writable by container UID/GID `10001` (for example, `chown -R 10001:10001 /path/to/config` on
  Linux).
- Back up the Postgres volume with encryption and access control; test restoring to an isolated
  host. Store the backup and Fernet key separately. Do not include environment files in backups.
- Run migrations as part of the image startup. Before an upgrade, make a tested backup; do not run
  destructive SQL manually. Roll back application images only after confirming migration
  compatibility.
- On suspected credential exposure, rotate the relevant secret, revoke Google access if relevant,
  inspect access logs, and reauthorize Gmail after a Fernet-key rotation. Do not paste logs or
  database exports containing sensitive metadata into issue trackers.
