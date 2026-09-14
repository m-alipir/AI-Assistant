"""Bounded pasted-URL parsing backed by the shared managed-source batch service."""

from __future__ import annotations

from app.config.source_pack import (
    ParsedSourcePack,
    SourcePackRepositoryUnavailable,
    SourcePackService,
    parse_source_record,
)
from app.config.source_repository import SourceRepository

MAX_BULK_URL_BYTES = 256 * 1024
MAX_BULK_URL_SOURCES = 500


class BulkUrlError(ValueError):
    """Base class for safe pasted-URL input failures."""

    code = "invalid_bulk_urls"


class InvalidBulkUrlStructure(BulkUrlError):
    code = "invalid_bulk_url_structure"


class BulkUrlLimitExceeded(BulkUrlError):
    code = "bulk_url_limit_exceeded"


BulkUrlRepositoryUnavailable = SourcePackRepositoryUnavailable


def parse_bulk_urls(content: str) -> ParsedSourcePack:
    """Parse one RSS/feed URL per non-empty line into the shared source representation."""
    if len(content.encode("utf-8")) > MAX_BULK_URL_BYTES:
        raise BulkUrlLimitExceeded(
            f"bulk URL input exceeds the {MAX_BULK_URL_BYTES}-byte limit"
        )
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise InvalidBulkUrlStructure("bulk URL input must contain at least one URL")
    if len(lines) > MAX_BULK_URL_SOURCES:
        raise BulkUrlLimitExceeded(
            f"bulk URL input exceeds the {MAX_BULK_URL_SOURCES}-source limit"
        )
    return ParsedSourcePack(
        name="Bulk URL Import",
        sources=tuple(
            parse_source_record(
                index,
                {"name": url, "type": "rss", "url": url, "enabled": False},
            )
            for index, url in enumerate(lines, 1)
        ),
        interests=(),
        exclude=(),
    )


class BulkUrlService:
    """Preview and import pasted feed URLs through the shared source-batch workflow."""

    def __init__(self, repository: SourceRepository) -> None:
        self._source_packs = SourcePackService(repository)

    async def preview(self, content: str) -> dict[str, object]:
        return _bulk_result(await self._source_packs.preview_parsed(parse_bulk_urls(content)))

    async def import_urls(self, content: str) -> dict[str, object]:
        return _bulk_result(await self._source_packs.import_parsed(parse_bulk_urls(content)))


def _bulk_result(result: dict[str, object]) -> dict[str, object]:
    sources = result["sources"]
    assert isinstance(sources, list)
    return {
        "bulk_urls": {"lines": len(sources)},
        "counts": result["counts"],
        "sources": sources,
    }
