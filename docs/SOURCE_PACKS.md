# Source Packs

Source Pack is the canonical YAML format for reviewing and importing several managed sources in
one operation. Preview never writes to the database. Import persists only valid new sources through
`SourceRepository`; invalid and duplicate rows are reported and skipped.

## Schema

```yaml
name: Technology Pack

sources:
  - name: TechCrunch
    type: rss
    url: https://techcrunch.com/feed/
    category: technology
    priority: high

  - name: Example Channel
    type: youtube
    url: UCVBX2n_5egE9XuJL8NUS0Xg
    category: programming
    priority: high

interests:
  - artificial intelligence
  - game development

exclude:
  - celebrity news
```

`name` and `sources` are required. Each source requires `name`, `type`, and `url`. Supported type
values are `rss`/`atom`/`feed` and `youtube`/`yt`; output always uses `rss` or `youtube`. Named
priorities map to `low=-50`, `normal/medium=0`, and `high=50`; an integer from -100 through 100 is
also accepted. Optional source fields are `category`, `stream`, `enabled`, `language`, and
`freshness_hours`. Sources default to disabled so a bulk import cannot immediately alter live
ingestion. Existing repository validation still applies: YouTube input must be a channel ID or an
official YouTube Atom feed URL. A public handle URL alone cannot be resolved safely offline.

`interests` and `exclude` are bounded string lists returned in the preview/import metadata. This
slice does not mutate the interest profile.

## Admin API

- `POST /admin/source-packs/preview`
- `POST /admin/source-packs/import`

Both accept JSON shaped as `{"yaml": "<Source Pack YAML>"}`. Preview source statuses are
`valid_new`, `existing_duplicate`, `duplicate_in_pack`, and `invalid_source`. Import replaces
`valid_new` with `created` when persistence succeeds. Results retain input order and include
aggregate counts.

Malformed YAML returns HTTP 400, invalid pack-level structure returns 422, bounds violations return
413, and an unavailable managed-source repository returns 503. Per-source validation failures stay
inside the normal 200 preview/import response.

Input is limited to 256 KiB, 500 sources, and 200 entries in each interest/exclude list. YAML uses
safe loading, aliases are rejected, and uploaded content is neither logged nor written to disk.
