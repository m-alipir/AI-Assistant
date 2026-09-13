# Managed Sources Handoff

## Goal

Make the database the runtime source-of-truth.

## Current State

- Migration `20260913_0024_managed_sources` creates the initial managed-source table.
- `SourceRepository.bootstrap_yaml()` seeds an empty DB from the YAML catalog and avoids duplicate
  canonical `(kind, endpoint)` rows.
- Main scheduler/ingestion and both retry paths bootstrap then load their catalog through
  `SourceRepository.load_catalog()`.
- Repository now has validated `create`, `get`, `list`, patch-style `update`, `set_enabled`, and
  safe `delete` operations. Enabled sources must be disabled before deletion.
- RSS URLs and YouTube channel identities are canonicalized before create/update and the database
  uniqueness constraint maps duplicate endpoints to a safe repository conflict.
- Runtime catalog records carry their database ID. Normal RSS and YouTube discovery persist
  success/failure health state, bounded cooldown, safe failure category, and successful strategy.
- Admin dashboard/config source reads and the source list/get/create/update/enable-disable/delete
  API operations now use `SourceRepository` exclusively. Existing `/admin/ui/sources...` actions
  remain compatibility wrappers over the same repository and no longer read or write YAML.
- Admin maps invalid input to 422, canonical duplicate endpoints and unsafe enabled-source deletes
  to 409, missing rows to 404, and an unavailable repository to 503.

## Not Finished

- Telegram still mutates/reads YAML at runtime.
- Source Pack, OPML, CSV/bulk import/export, Control Center updates, and onboarding are not
  implemented.
- YAML is still read as a bootstrap seed on every runtime path; it is not yet example/bootstrap-only.
- The opt-in real PostgreSQL managed-source test has not run because
  `MANAGED_SOURCE_INTEGRATION_DATABASE_URL` was not supplied.

## Important Files

- `migrations/versions/20260913_0024_managed_sources.py`
- `app/config/source_repository.py`
- `app/main.py`
- `app/api/admin.py`
- `app/telegram/service.py`
- `app/jobs/rss_runtime.py`
- `app/jobs/youtube_runtime.py`
- `app/config/sources.py`
- `tests/test_admin.py`, `tests/test_rss_runtime.py`, `tests/test_telegram.py`

## Database Schema

`managed_sources` stores canonical endpoint identity, kind, name, stream, enabled, priority,
category, language, freshness, health/cooldown fields, safe failure metadata, strategy/language,
and timestamps. It has a unique `(kind, canonical_endpoint)` constraint.

## Runtime Flow

Scheduler/ingestion and retry paths read the DB catalog after attempting an empty-DB YAML seed.
Admin source management uses the database repository. Telegram source management still uses YAML,
so YAML remains a runtime dependency until the Telegram cutover and bootstrap lifecycle are
finished.

## Next Recommended Step

Telegram source management yollarını aynı `SourceRepository` CRUD katmanına geçir; YAML dosyasını
yalnızca açık bootstrap/example yaşam döngüsünde bırak ve iki source-of-truth oluşmasını engelleyen
regresyon testlerini ekle. Source Pack/OPML/CSV, Control Center ve onboarding bu adıma dahil değil.

## Do Not Break

- Ana worktree’ye dokunma.
- Production’a deploy etme.
- İki source-of-truth bırakma.
- Mevcut ingestion davranışını bozma.
- Production source kaybına yol açma.

## Verification

- Full Ruff passed.
- Full offline suite: 232 passed, 4 opt-in PostgreSQL tests skipped.
- Managed-source targeted suite: 29 passed, 1 opt-in PostgreSQL test skipped.
- Alembic static SQL passed for `20260911_0021:20260913_0024`.
- `git diff --check` passed.
- Docker daemon was unavailable, so the disposable PostgreSQL acceptance test could not be run.
- No provider, live source, production database, deployment, or main-worktree mutation occurred.

### Stage 2 Admin verification

- Focused Admin/repository suite: 26 passed, 1 opt-in PostgreSQL test skipped.
- Full offline suite: 233 passed, 4 opt-in PostgreSQL tests skipped.
- Full Ruff and `git diff --check` passed.
- Docker daemon remained unavailable; the disposable PostgreSQL test was not run.
- Admin source tests cover CRUD, canonical endpoint output, duplicate/invalid/not-found/unsafe-delete
  errors, repository-unavailable behavior, compatibility routes, and unchanged YAML fixtures.
