# Managed Sources Handoff

## Goal

Make the database the runtime source-of-truth.

## Resume Here

- Worktree: `C:\Users\Mali\Documents\ChatGPT\AI-Personal-Assistant-db-managed-sources`
- Branch: `feature/db-managed-sources`
- Stage 14 implementation: complete
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
- Migration `20260914_0025_managed_source_bootstrap` records one completed bootstrap lifecycle.
  `MANAGED_SOURCES_BOOTSTRAP=true` is an explicit startup-only development fixture path: it seeds
  only a pristine database, marks an existing database complete without changing its rows, and
  never rereads YAML after completion. It persists validated source freshness defaults with an
  empty-DB seed; pre-existing databases use built-in defaults. Scheduler, ingestion, and both
  retry paths load only the database catalog.
- The optional Control Center onboarding starts at `/admin/onboarding`. It reuses the existing
  Gmail OAuth, source, and interest endpoints, keeps browser-only skip progress resumable, and
  persists only the non-secret daily scheduler preference in `control_center_settings`.
- The Control Center dashboard at `/admin/control-center` is an operational read-only view over
  existing Admin/runtime data: health, latest run and briefing, scheduler state, source health,
  connection readiness, and available provider usage. It adds no source-management rules or API.
- The Control Center Briefings page at `/admin/control-center/briefings` and its detail route read
  existing persisted briefing rows only. It bounds history to 50 rows, escapes full generated
  content, distinguishes saved from incomplete rows, and converts only timezone-aware timestamps
  to Istanbul time; naive legacy timestamps remain unavailable rather than receiving an assumed
  offset.
- The Control Center Search / Memory page at `/admin/control-center/search` reuses the existing
  deterministic bounded retrieval callback and shows compact retained event/Gmail results. Its
  optional Ask action reuses the existing bounded synthesis callback; neither path mutates stored
  knowledge. Result details read one compact persisted event, retain source-backed facts separate
  from stored inferences, and render only timezone-aware timestamps in Istanbul time.
- The Control Center Scheduler page at `/admin/control-center/scheduler` reads the existing daily
  scheduler state, persisted `control_center_settings` preference, and bounded scheduled-run
  history. Its form reuses `/admin/onboarding/scheduler`, so validation, idle-run protection,
  database persistence, and scheduler reconfiguration remain in the existing backend path.

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
  `app/templates/admin_sources.html`, `app/templates/admin_briefings.html`,
  `app/templates/admin_briefing_detail.html`, `app/templates/admin_search.html`,
  `app/templates/admin_search_detail.html`, `app/templates/admin_scheduler.html`,
  `app/templates/admin_dashboard.html`
- `app/telegram/service.py`
- `app/jobs/rss_runtime.py`
- `app/jobs/youtube_runtime.py`
- `app/config/sources.py`
- `app/config/onboarding.py`
- `tests/test_admin.py`, `tests/test_source_pack.py`, `tests/test_rss_runtime.py`,
  `tests/test_opml.py`, `tests/test_csv_bulk_urls.py`, `tests/test_source_export.py`,
  `tests/test_telegram.py`
- `docs/SOURCE_PACKS.md`, `docs/OPML.md`, `docs/CSV_AND_BULK_URLS.md`

## Database Schema

`managed_sources` stores canonical endpoint identity, kind, name, stream, enabled, priority,
category, language, freshness, health/cooldown fields, safe failure metadata, strategy/language,
and timestamps. It has a unique `(kind, canonical_endpoint)` constraint.

## Runtime Flow

Admin, Telegram, scheduler/ingestion, and retry source reads or mutations use the database
repository. YAML is loaded only by the opt-in startup bootstrap while its lifecycle is pending;
after it completes, runtime catalog loads are database-only.

## Next Recommended Step

No follow-on slice is authorized. Do not start Gmail management, AI settings, Scheduler expansion,
Search/Memory expansion, or production deployment automation without a new explicit request.
Local or disposable-PostgreSQL success is not production migration/deployment acceptance.

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

### Stage 9 one-time YAML bootstrap verification

- Focused bootstrap/repository/runtime suite: 30 passed, 2 opt-in PostgreSQL tests skipped.
- Full offline suite: 279 passed, 5 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL container migrated to `20260914_0025`; the
  complete managed-source repository suite passed 10 tests and the container/anonymous volume were
  removed.
- Coverage includes empty-DB seeding, repeat idempotency, canonical seed duplicates, existing-row
  preservation, non-default seed defaults, startup fixture loading only while explicitly pending,
  and DB-only normal runtime.
- Full Ruff with `--no-cache` and `git diff --check` passed after documentation changes.

### Stage 10 onboarding verification

- Focused Admin and scheduler suite passed 26 tests.
- Full offline suite passed 281 tests with 6 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL container migrated to `20260914_0026`; focused
  onboarding/source-repository persistence acceptance passed 11 tests and the container was
  removed.
- The wizard does not render or store Telegram/Gmail/provider secrets. Telegram configuration
  remains an external protected-runtime prerequisite; Gmail remains explicitly optional.

### Stage 11 operational dashboard verification

- Focused Admin dashboard coverage passed 20 tests.
- Full offline suite passed 281 tests with 6 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL container migrated to `20260914_0026`; focused
  onboarding/source-repository persistence acceptance passed 11 tests and the container was
  removed with its anonymous volume.
- Full Ruff with `--no-cache` and `git diff --check` passed.
- The dashboard uses the existing Admin/runtime services only; no new endpoint, schema, provider,
  live source, production database, deployment, or source-management behavior was added.

### Stage 12 Briefings history verification

- Focused Admin/briefing coverage passed 30 tests.
- Full offline suite passed 284 tests with 6 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL container migrated to `20260914_0026`; direct
  briefing history/detail read acceptance verified persisted content and timezone-aware Istanbul
  rendering, then the container and anonymous volume were removed.
- Full Ruff with `--no-cache` and `git diff --check` passed.
- No schema, provider, live source, production database, deployment, or briefing mutation was
  added.

### Stage 13 Search / Memory verification

- Focused Admin/Search coverage passed 34 tests.
- Full offline suite passed 287 tests with 6 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL database migrated to `20260914_0026`; the
  real Search integration suite passed 3 tests, including the compact event detail query, then
  its container and anonymous volume were removed.
- Full Ruff with `--no-cache` and `git diff --check` passed. The local browser-server smoke could
  not start because the configured PostgreSQL endpoint refused the connection; TestClient page and
  endpoint coverage passed without contacting a provider.
- No schema, provider, live source, production database, deployment, or knowledge mutation was
  added.

### Stage 14 Scheduler UI verification

- Focused Admin/scheduler coverage passed 34 tests with 1 opt-in PostgreSQL test skipped.
- Full offline suite passed 289 tests with 6 opt-in PostgreSQL tests skipped.
- A uniquely named disposable pgvector PostgreSQL database migrated to `20260914_0026`; the
  persisted scheduler-preference acceptance test passed, then its container and anonymous volume
  were removed.
- Full Ruff with `--no-cache` and `git diff --check` passed. No separate frontend package/checker
  exists; server-rendered page and endpoint coverage exercise the UI contract.
- No schema, provider, live source, production database, deployment, or scheduler run was added.
