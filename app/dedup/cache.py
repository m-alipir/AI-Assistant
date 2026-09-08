"""Idempotent in-process identity cache for the deterministic ingestion stage."""

from app.ingestion.schemas import SourceItem


class InMemoryDedupCache:
    """Reserve external-ID, canonical-URL, and content-hash identities in priority order."""

    def __init__(self) -> None:
        self._external_ids: set[tuple[str, str]] = set()
        self._urls: set[str] = set()
        self._content_hashes: set[str] = set()

    def reserve(self, item: SourceItem) -> bool:
        """Return true once for a unique item and false for subsequent equivalent items."""
        external_key = (item.source_name, item.external_id) if item.external_id else None
        if external_key and external_key in self._external_ids:
            return False
        if item.canonical_url and item.canonical_url in self._urls:
            return False
        if item.content_hash in self._content_hashes:
            return False
        if external_key:
            self._external_ids.add(external_key)
        if item.canonical_url:
            self._urls.add(item.canonical_url)
        self._content_hashes.add(item.content_hash)
        return True
