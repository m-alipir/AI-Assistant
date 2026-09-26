# OPML Feed Import

OPML preview/import is a bounded adapter over the same managed-source batch workflow used by
Source Packs. It extracts RSS/Atom feed outlines, validates and canonicalizes every URL through
`ManagedSourceCreate`, and persists only through `SourceRepository`.

## Admin API

- `POST /admin/opml/preview`
- `POST /admin/opml/import`
- `GET /admin/opml/export`

Both accept JSON shaped as `{"opml": "<OPML XML>"}`. Preview never changes the database. Its
source statuses are `valid_new`, `existing_duplicate`, `duplicate_in_pack`, and `invalid_source`.
Import changes `valid_new` to `created`, skips all other rows, and is safe to retry.

Feed outlines may use `type="rss"`, `type="atom"`, `type="feed"`, or omit `type` when `xmlUrl` is
present. The source name comes from `title`, then `text`, then the feed URL. Folder outlines and
unrelated link outlines are ignored. Imported feeds default to the `tech` stream and remain
disabled until explicitly enabled.

Current import does not ask for a category during preview/import; uncategorized sources can enter
the existing Telegram operator question queue. Planned M22.4 import will use a category supplied
for each feed in the OPML file or collect a choice during import. Built-in and user-created
categories should be available, with free-form entry for a new category. Keep the `tech`/`world`
editorial stream separate from the source category. This planned interaction is not yet implemented.

Malformed XML returns HTTP 400, invalid OPML structure returns 422, bounds violations return 413,
and an unavailable repository returns 503. Individual malformed feed outlines remain in the
normal 200 response as `invalid_source` rows.

Input is limited to 256 KiB, 2,000 outlines, 500 feed rows, and 20 outline levels. DTD and entity
declarations are rejected before XML parsing. OPML content is neither logged nor written to disk.

The export is a deterministic read-only snapshot of all managed RSS sources, including disabled
ones. Standard OPML can retain each canonical feed URL and name only, so YouTube sources, enabled
state, and managed-source metadata are intentionally not represented. Use Source Pack YAML for a
full-fidelity backup.
