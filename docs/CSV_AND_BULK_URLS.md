# CSV and Bulk URL Import

CSV and pasted URL preview/import are bounded adapters over the same managed-source batch workflow
used by Source Pack and OPML. Preview never writes. Import persists only valid new sources through
`SourceRepository`, creates them disabled, and is safe to retry.

## CSV

CSV requires a header row and a `url` column. Supported columns are:

```csv
name,type,url,category,priority,stream,language,freshness_hours
Tech Feed,rss,https://example.com/feed,technology,high,tech,,24
Video Channel,youtube,UCVBX2n_5egE9XuJL8NUS0Xg,programming,10,personalized,en,72
```

`name` defaults to the URL and `type` defaults to `rss`. Type, priority, metadata, and endpoints use
the Source Pack normalizer and existing `ManagedSourceCreate` validation. Unknown or duplicate
headers are rejected at the CSV level; malformed or invalid data rows are reported individually.
The format is limited to 256 KiB and 500 non-empty source rows.

Admin endpoints accept JSON shaped as `{"csv": "<CSV text>"}`:

- `POST /admin/csv/preview`
- `POST /admin/csv/import`
- `GET /admin/csv/export`

## Bulk URLs

Bulk URL input contains one RSS/feed URL per line. Blank lines are ignored. Each source name starts
as the supplied URL, and all entries are validated/canonicalized by the repository input model.
The format is limited to 256 KiB and 500 non-empty lines.

Admin endpoints accept JSON shaped as `{"urls": "<one URL per line>"}`:

- `POST /admin/bulk-urls/preview`
- `POST /admin/bulk-urls/import`

Both formats return `valid_new`, `existing_duplicate`, `duplicate_in_pack`, and `invalid_source`
during preview. Import changes successfully persisted `valid_new` entries to `created`. Malformed
CSV returns HTTP 400, invalid input structure returns 422, bounds violations return 413, and an
unavailable repository returns 503. Input bodies are neither logged nor written to disk.

CSV export is a deterministic read-only snapshot of all managed RSS and YouTube sources, including
disabled ones. It preserves canonical endpoint, name, kind, category, priority, stream, language,
and freshness metadata. CSV import intentionally disables every row, so enabled state and
operational health/timestamps are not round-tripped; use Source Pack YAML when enabled state matters.
