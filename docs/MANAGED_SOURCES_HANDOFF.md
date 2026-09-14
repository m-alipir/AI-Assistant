# Managed Sources Handoff

## Goal

Make the database the runtime source-of-truth.

## Resume Here

- Worktree: `C:\Users\Mali\Documents\ChatGPT\AI-Personal-Assistant-db-managed-sources`
- Branch: `feature/db-managed-sources`
- Stage 8 implementation commit: `44afab6 feat: add managed sources control center`
- The worktree was clean when this handoff was updated on 2026-09-14.
- Read this file and `docs/PROGRESS.md` before starting. Keep each next slice narrow and create
  one focused commit only after its targeted/full tests, Ruff, and `git diff --check` pass.

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
- Telegram source commands now use the same `SourceRepository` for list/detail, validated add,
  enable/disable, and safe delete. Source list/detail includes compact enabled and health state.
- Telegram no longer has a source YAML mutation/read path. Repository failures are translated to
  concise Turkish messages without exposing database or provider details.
- Source Pack YAML is now the canonical bounded bulk-source format. A reusable service safely
  parses and normalizes packs, previews valid/duplicate/invalid rows without writes, and imports
  only valid new rows through `SourceRepository`.
- Admin exposes `/admin/source-packs/preview` and `/admin/source-packs/import`. Imports default
  sources to disabled, retain deterministic input order/counts, and are safe to retry.
- Source Pack `interests` and `exclude` lists are represented in results only; they do not mutate
  the existing interest profile.
- OPML RSS/Atom preview/import now uses the same parsed-source batch workflow as Source Pack.
  It rejects DTD/entities, applies bounded XML traversal, reports invalid/internal/existing
  duplicates deterministically, and persists only valid new feeds through `SourceRepository`.
- Admin exposes `/admin/opml/preview` and `/admin/opml/import`; imported OPML feeds default to
  disabled and repeated imports are idempotent.
- CSV and pasted bulk URL preview/import now use the same Source Pack row normalizer and shared
  batch workflow. They report invalid/internal/existing duplicates deterministically, create only
  valid new sources as disabled, and remain idempotent on retry.
- Admin exposes `/admin/csv/preview`, `/admin/csv/import`, `/admin/bulk-urls/preview`, and
  `/admin/bulk-urls/import` without writing uploaded content to disk.
- Database-managed sources can be exported deterministically through Admin as Source Pack YAML,
  OPML, or CSV. Every export reads the repository only and includes disabled rows; Source Pack
  retains all import-supported source metadata, while OPML and CSV retain only their documented
  format-supported fields.
- The focused Control Center now has a shared shell, a small source-status dashboard, and a
  Sources page. Its source list/create/enable-disable/safe-delete and Source Pack/OPML/CSV
  preview/import/export entry points call the existing Admin API; no validation,
  canonicalization, or persistence rules are duplicated in browser code.
- The focused Control Center starts at `/admin/control-center`; `/admin/sources/ui` is its Sources
  page. The pre-existing broad operational page remains available at `/admin`. Do not remove or
  silently change those existing operations while implementing later Control Center slices.

## Not Finished

- Onboarding is not implemented.
- YAML is still read as a bootstrap seed on every ingestion/retry runtime path; its lifecycle is
  not yet explicit example/bootstrap-only behavior.

## Important Files

- `migrations/versions/20260913_0024_managed_sources.py`
- `app/config/source_repository.py`
- `app/config/source_pack.py`
- `app/config/opml.py`
- `app/config/csv_import.py`
- `app/config/bulk_urls.py`
- `app/config/source_export.py`
- `app/main.py`
- `app/api/admin.py`
- `app/templates/admin_shell.html`, `app/templates/admin_control_center.html`,
  `app/templates/admin_sources.html`, `app/templates/admin_dashboard.html`
- `app/telegram/service.py`
- `app/jobs/rss_runtime.py`
- `app/jobs/youtube_runtime.py`
- `app/config/sources.py`
- `tests/test_admin.py`, `tests/test_source_pack.py`, `tests/test_rss_runtime.py`,
  `tests/test_opml.py`, `tests/test_csv_bulk_urls.py`, `tests/test_source_export.py`,
  `tests/test_telegram.py`
- `docs/SOURCE_PACKS.md`, `docs/OPML.md`, `docs/CSV_AND_BULK_URLS.md`

## Database Schema

`managed_sources` stores canonical endpoint identity, kind, name, stream, enabled, priority,
category, language, freshness, health/cooldown fields, safe failure metadata, strategy/language,
and timestamps. It has a unique `(kind, canonical_endpoint)` constraint.

## Runtime Flow

Scheduler/ingestion and retry paths read the DB catalog after attempting an empty-DB YAML seed.
Admin, Telegram, scheduler/ingestion, and retry source reads or mutations use the database
repository. YAML remains only in the existing empty-database bootstrap call, but that bootstrap is
still attempted on every ingestion/retry catalog load and needs an explicit lifecycle boundary.

## Next Recommended Step

Implement the explicit YAML bootstrap lifecycle as the next isolated slice.

- Make YAML an explicit one-time bootstrap/development-fixture path instead of attempting it on
  every ingestion and retry catalog load.
- Keep `SourceRepository` and the database as the only runtime source-of-truth after bootstrap.
- Preserve current Admin, Telegram, Control Center, source import/export, canonicalization,
  health/cooldown, and resilient ingestion behavior.
- Define deterministic behavior for an empty database, an already-seeded database, a missing or
  invalid bootstrap fixture, and repository/database unavailability.
- Add focused repository/runtime/bootstrap tests, then run the full offline suite, Ruff,
  `git diff --check`, and the opt-in disposable PostgreSQL acceptance test when Docker is available.
- Update this handoff and `docs/PROGRESS.md`, and create one focused commit if clean.

Do not start onboarding or production deployment without a new explicit request. Do not infer
that local or disposable-PostgreSQL success means production migration/deployment acceptance.

## Working Notes For The Next Agent

- Use the project interpreter at
  `C:\Users\Mali\Documents\ChatGPT\AI Personal Assistant\.venv\Scripts\python.exe`.
- On this machine, pytest cache/temp paths inside the isolated worktree may be unreliable. Use
  `-p no:cacheprovider` and a unique writable `--basetemp` directory.
- Run Ruff with `--no-cache`.
- PostgreSQL acceptance must use a uniquely named disposable pgvector container/database. Migrate
  it to Alembic head, run only the opt-in managed-source test against it, and remove that exact
  container and its anonymous volume afterward.
- Source creation/import defaults to disabled. An enabled source must be disabled before safe
  deletion. Keep these rules in the repository/service layer, not in handlers or browser code.
- Source Pack interests/exclude are preview metadata only; do not create an interest subsystem as
  part of source work.
- Never write uploaded import content to arbitrary filesystem paths, render untrusted UI content
  with `innerHTML`, expose secrets/provider bodies, or mutate the main dirty worktree.

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

### Stage 3 Telegram verification

- Focused Telegram/repository suite: 30 passed, 1 opt-in PostgreSQL test skipped.
- Full offline suite: 235 passed, 4 opt-in PostgreSQL tests skipped.
- Full Ruff and `git diff --check` passed.
- Docker daemon remained unavailable; the disposable PostgreSQL test was not run.
- Telegram tests cover canonicalized add, list/detail health output, enable/disable, safe delete,
  invalid/duplicate/not-found/unsafe-delete errors, and repository/database unavailability.
- No source YAML operation, provider request, live Telegram call, deployment, or main-worktree
  mutation occurred.

### Stage 4 Source Pack verification

- Focused Source Pack suite: 11 passed.
- Source Pack plus relevant repository/Admin suite: 37 passed, 1 opt-in PostgreSQL test skipped.
- Full offline suite: 246 passed, 4 opt-in PostgreSQL tests skipped.
- Disposable PostgreSQL managed-source acceptance: 1 passed after migration to
  `20260913_0024`; the uniquely named container and anonymous volume were removed.
- Full Ruff and `git diff --check` passed.
- Tests cover malformed YAML, invalid pack structure, aliases and size/count bounds, mixed rows,
  database and canonical in-pack duplicates, preview non-mutation, import filtering, repeated
  import idempotency, Admin HTTP errors, and repository unavailability.
- No OPML/CSV/bulk URL, interest mutation, Control Center, onboarding, production deployment, live
  provider, ingestion behavior, or main-worktree change occurred.

### Stage 5 OPML verification

- Focused OPML suite: 11 passed.
- OPML plus Source Pack and relevant repository/Admin suite: 48 passed, 1 opt-in PostgreSQL test
  skipped.
- Full offline suite: 257 passed, 4 opt-in PostgreSQL tests skipped.
- Disposable PostgreSQL managed-source acceptance: 1 passed after migration to
  `20260913_0024`; the uniquely named container and anonymous volume were removed.
- Full Ruff and `git diff --check` passed.
- Tests cover malformed XML, invalid root/body, DTD/entity rejection, size/source/depth bounds,
  nested RSS/Atom extraction, canonical in-file and database duplicates, invalid rows, preview
  non-mutation, filtered/idempotent import, Admin HTTP errors, and repository unavailability.
- No CSV/bulk URL, Control Center, onboarding, production deployment, live provider, ingestion
  behavior, or main-worktree change occurred.

### Stage 6 CSV and bulk URL verification

- Focused CSV/bulk URL suite: 16 passed.
- CSV/bulk URL plus Source Pack, OPML, and relevant repository/Admin suite: 64 passed, 1 opt-in
  PostgreSQL test skipped.
- Full offline suite: 273 passed, 4 opt-in PostgreSQL tests skipped.
- Disposable PostgreSQL managed-source acceptance: 1 passed after migration to
  `20260913_0024`; the uniquely named container and anonymous volume were removed.
- Full Ruff and `git diff --check` passed.
- Tests cover strict CSV parsing and headers, numeric/named priority normalization, size/count
  bounds, one-URL-per-line parsing, invalid rows, canonical input/DB duplicates, preview
  non-mutation, disabled creation, filtered/idempotent import, Admin HTTP errors, and repository
  unavailability.
- No Control Center, onboarding, source export, production deployment, live provider, ingestion
  behavior, or main-worktree change occurred.

### Stage 7 Source export verification

- Focused export suite: 4 passed.
- Export plus Source Pack, OPML, CSV, Admin, and repository suite: 68 passed, 1 opt-in PostgreSQL
  test skipped.
- Full offline suite: 277 passed, 4 opt-in PostgreSQL tests skipped.
- Disposable PostgreSQL managed-source acceptance: 1 passed after migration to
  `20260913_0024`; the uniquely named container and anonymous volume were removed.
- Full Ruff and `git diff --check` passed.
- Tests cover deterministic canonical Source Pack/OPML/CSV output, disabled-source inclusion,
  Source Pack state round-trip, documented OPML/CSV format limits, Admin attachment responses, and
  repository-unavailable handling.
- No Control Center, onboarding, production deployment, live provider, ingestion behavior, or
  main-worktree change occurred.

### Stage 8 Control Center verification

- Focused Control Center/import/export suite: 61 passed.
- Full offline suite: 278 passed, 4 opt-in PostgreSQL tests skipped; full Ruff and
  `git diff --check` passed.
- A uniquely named disposable pgvector container was migrated to `20260913_0024`, passed the
  managed-source PostgreSQL acceptance test (1 test), and was removed with its anonymous volume.
- The UI renders untrusted source fields through Jinja escaping and dynamic result/error text only
  through DOM `textContent`; it does not write uploaded content to disk.
- No provider, live source, production database, deployment, onboarding, or main-worktree mutation
  occurred.

### Latest clean baseline

- Branch head: `44afab6 feat: add managed sources control center`.
- Focused Admin/Control Center test file: 19 passed after preserving the existing `/admin`
  operations page and keeping the focused UI at `/admin/control-center`.
- Full offline suite: 278 passed, 4 opt-in PostgreSQL tests skipped.
- Disposable PostgreSQL managed-source acceptance: 1 passed; its uniquely named container and
  anonymous volume were removed.
- Full Ruff with `--no-cache` and `git diff --check` passed; no separate frontend package/checker
  exists.
