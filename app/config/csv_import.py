"""Safe CSV source parsing backed by the shared managed-source batch service."""

from __future__ import annotations

import csv
from io import StringIO

from app.config.source_pack import (
    ParsedSource,
    ParsedSourcePack,
    SourcePackRepositoryUnavailable,
    SourcePackService,
    parse_source_record,
)
from app.config.source_repository import SourceRepository

MAX_CSV_BYTES = 256 * 1024
MAX_CSV_SOURCES = 500
_CSV_FIELDS = {
    "name",
    "type",
    "url",
    "category",
    "priority",
    "stream",
    "language",
    "freshness_hours",
}


class CsvImportError(ValueError):
    """Base class for safe CSV-level failures."""

    code = "invalid_csv"


class MalformedCsv(CsvImportError):
    code = "malformed_csv"


class InvalidCsvStructure(CsvImportError):
    code = "invalid_csv_structure"


class CsvLimitExceeded(CsvImportError):
    code = "csv_limit_exceeded"


CsvRepositoryUnavailable = SourcePackRepositoryUnavailable


def parse_source_csv(content: str) -> ParsedSourcePack:
    """Parse bounded CSV rows into the shared source representation."""
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise CsvLimitExceeded(f"CSV exceeds the {MAX_CSV_BYTES}-byte limit")
    try:
        reader = csv.DictReader(StringIO(content, newline=""), strict=True)
        raw_fields = reader.fieldnames
        if raw_fields is None:
            raise InvalidCsvStructure("CSV header row is required")
        fields = [field.lstrip("\ufeff").strip().casefold() for field in raw_fields]
        if any(not field for field in fields) or len(set(fields)) != len(fields):
            raise InvalidCsvStructure("CSV headers must be unique non-empty names")
        if "url" not in fields:
            raise InvalidCsvStructure("CSV url header is required")
        if set(fields) - _CSV_FIELDS:
            raise InvalidCsvStructure("CSV contains unsupported headers")
        reader.fieldnames = fields

        parsed: list[ParsedSource] = []
        for row in reader:
            if len(parsed) >= MAX_CSV_SOURCES:
                raise CsvLimitExceeded(f"CSV exceeds the {MAX_CSV_SOURCES}-source limit")
            index = len(parsed) + 1
            if None in row or any(
                value is not None and not isinstance(value, str) for value in row.values()
            ):
                parsed.append(ParsedSource(index, None, "malformed_csv_row"))
                continue
            if all(value is None or not value.strip() for value in row.values()):
                continue
            if any(value is None for value in row.values()):
                parsed.append(ParsedSource(index, None, "malformed_csv_row"))
                continue
            normalized = {
                key: value.strip()
                for key, value in row.items()
                if key is not None and value is not None and value.strip()
            }
            url = normalized.get("url", "")
            normalized.setdefault("name", url)
            normalized.setdefault("type", "rss")
            normalized["enabled"] = False
            parsed.append(parse_source_record(index, normalized))
    except CsvImportError:
        raise
    except csv.Error as error:
        raise MalformedCsv("CSV content is malformed") from error

    return ParsedSourcePack(
        name="CSV Import",
        sources=tuple(parsed),
        interests=(),
        exclude=(),
    )


class CsvImportService:
    """Preview and import CSV rows through the shared source-batch workflow."""

    def __init__(self, repository: SourceRepository) -> None:
        self._source_packs = SourcePackService(repository)

    async def preview(self, content: str) -> dict[str, object]:
        return _csv_result(await self._source_packs.preview_parsed(parse_source_csv(content)))

    async def import_csv(self, content: str) -> dict[str, object]:
        return _csv_result(await self._source_packs.import_parsed(parse_source_csv(content)))


def _csv_result(result: dict[str, object]) -> dict[str, object]:
    sources = result["sources"]
    assert isinstance(sources, list)
    return {"csv": {"rows": len(sources)}, "counts": result["counts"], "sources": sources}
