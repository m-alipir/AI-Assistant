"""Safe, bounded Source Pack YAML preview and database import service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import yaml
from pydantic import ValidationError
from yaml.tokens import AliasToken

from app.config.source_repository import (
    ManagedSourceCreate,
    SourceAlreadyExists,
    SourceRepository,
)

MAX_SOURCE_PACK_BYTES = 256 * 1024
MAX_SOURCE_PACK_SOURCES = 500
MAX_SOURCE_PACK_TERMS = 200
_PACK_FIELDS = {"name", "sources", "interests", "exclude"}
_SOURCE_FIELDS = {
    "name",
    "type",
    "url",
    "category",
    "priority",
    "stream",
    "enabled",
    "language",
    "freshness_hours",
}
_TYPE_ALIASES = {"rss": "rss", "atom": "rss", "feed": "rss", "youtube": "youtube", "yt": "youtube"}
_PRIORITIES = {"low": -50, "normal": 0, "medium": 0, "high": 50}

PreviewStatus = Literal[
    "valid_new", "existing_duplicate", "duplicate_in_pack", "invalid_source"
]


class SourcePackError(ValueError):
    """Base class for safe pack-level input failures."""

    code = "invalid_source_pack"


class MalformedSourcePack(SourcePackError):
    code = "malformed_yaml"


class InvalidSourcePackStructure(SourcePackError):
    code = "invalid_pack_structure"


class SourcePackLimitExceeded(SourcePackError):
    code = "source_pack_limit_exceeded"


class SourcePackRepositoryUnavailable(RuntimeError):
    """The managed-source catalog could not be read or changed."""


@dataclass(frozen=True)
class ParsedSource:
    index: int
    source: ManagedSourceCreate | None
    error: str | None = None


@dataclass(frozen=True)
class ParsedSourcePack:
    name: str
    sources: tuple[ParsedSource, ...]
    interests: tuple[str, ...]
    exclude: tuple[str, ...]


def parse_source_pack(content: str) -> ParsedSourcePack:
    """Parse untrusted YAML into a bounded pack without constructing arbitrary objects."""
    if len(content.encode("utf-8")) > MAX_SOURCE_PACK_BYTES:
        raise SourcePackLimitExceeded(
            f"source pack exceeds the {MAX_SOURCE_PACK_BYTES}-byte limit"
        )
    try:
        if any(isinstance(token, AliasToken) for token in yaml.scan(content)):
            raise InvalidSourcePackStructure("YAML aliases are not supported")
        raw = yaml.safe_load(content)
    except SourcePackError:
        raise
    except yaml.YAMLError as error:
        raise MalformedSourcePack("source pack contains malformed YAML") from error
    if not isinstance(raw, dict):
        raise InvalidSourcePackStructure("source pack root must be a mapping")
    if any(not isinstance(key, str) for key in raw):
        raise InvalidSourcePackStructure("source pack keys must be strings")
    extra = set(raw) - _PACK_FIELDS
    if extra:
        raise InvalidSourcePackStructure("source pack contains unsupported fields")

    name = _required_text(raw.get("name"), "pack name", maximum=256)
    source_rows = raw.get("sources")
    if not isinstance(source_rows, list):
        raise InvalidSourcePackStructure("sources must be a list")
    if len(source_rows) > MAX_SOURCE_PACK_SOURCES:
        raise SourcePackLimitExceeded(
            f"source pack exceeds the {MAX_SOURCE_PACK_SOURCES}-source limit"
        )
    interests = _term_list(raw.get("interests", []), "interests")
    exclude = _term_list(raw.get("exclude", []), "exclude")
    return ParsedSourcePack(
        name=name,
        sources=tuple(parse_source_record(index, row) for index, row in enumerate(source_rows, 1)),
        interests=interests,
        exclude=exclude,
    )


class SourcePackService:
    """Analyze and import Source Packs through the managed-source repository only."""

    def __init__(self, repository: SourceRepository) -> None:
        self._repository = repository

    async def preview(self, content: str) -> dict[str, object]:
        return await self.preview_parsed(parse_source_pack(content))

    async def preview_parsed(self, pack: ParsedSourcePack) -> dict[str, object]:
        """Preview an already parsed source batch without mutating the repository."""
        items = await self._analyze(pack)
        return _result(pack, items, import_result=False)

    async def import_pack(self, content: str) -> dict[str, object]:
        return await self.import_parsed(parse_source_pack(content))

    async def import_parsed(self, pack: ParsedSourcePack) -> dict[str, object]:
        """Import an already parsed source batch through repository create operations."""
        items = await self._analyze(pack)
        candidates = {row.index: row.source for row in pack.sources if row.source is not None}
        for item in items:
            if item["status"] != "valid_new":
                continue
            source = candidates[int(item["index"])]
            if source is None:  # pragma: no cover - protected by the status invariant
                continue
            try:
                created = await self._repository.create(source)
            except SourceAlreadyExists:
                item["status"] = "existing_duplicate"
                continue
            except Exception as error:
                raise SourcePackRepositoryUnavailable(
                    "managed source repository is unavailable"
                ) from error
            item["status"] = "created"
            item["source_id"] = created.get("id")
        return _result(pack, items, import_result=True)

    async def _analyze(self, pack: ParsedSourcePack) -> list[dict[str, object]]:
        try:
            existing_rows = await self._repository.list()
            existing = {
                (str(row["kind"]), str(row["canonical_endpoint"])) for row in existing_rows
            }
        except Exception as error:
            raise SourcePackRepositoryUnavailable(
                "managed source repository is unavailable"
            ) from error

        seen: set[tuple[str, str]] = set()
        items: list[dict[str, object]] = []
        for row in pack.sources:
            if row.source is None:
                items.append(
                    {
                        "index": row.index,
                        "status": "invalid_source",
                        "error": row.error,
                    }
                )
                continue
            source = row.source
            key = (source.kind, source.endpoint)
            if key in seen:
                status: PreviewStatus = "duplicate_in_pack"
            elif key in existing:
                status = "existing_duplicate"
            else:
                status = "valid_new"
            seen.add(key)
            items.append(
                {
                    "index": row.index,
                    "status": status,
                    "source": _source_view(source),
                }
            )
        return items


def parse_source_record(index: int, raw: object) -> ParsedSource:
    """Normalize one external source mapping through the repository input model."""
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        return ParsedSource(index=index, source=None, error="source_must_be_a_mapping")
    if set(raw) - _SOURCE_FIELDS:
        return ParsedSource(index=index, source=None, error="unsupported_source_fields")
    if not {"name", "type", "url"}.issubset(raw):
        return ParsedSource(index=index, source=None, error="missing_required_fields")
    source_type = raw.get("type")
    if not isinstance(source_type, str) or source_type.strip().casefold() not in _TYPE_ALIASES:
        return ParsedSource(index=index, source=None, error="invalid_source_type")
    kind = _TYPE_ALIASES[source_type.strip().casefold()]
    try:
        priority = _priority(raw.get("priority", 0))
        source = ManagedSourceCreate(
            kind=kind,
            name=raw.get("name"),
            endpoint=raw.get("url"),
            category=raw.get("category"),
            priority=priority,
            stream=_normalized_optional_text(raw.get("stream", "tech")),
            enabled=raw.get("enabled", False),
            language=_normalized_optional_text(raw.get("language")),
            freshness_hours=raw.get("freshness_hours"),
        )
    except (ValidationError, ValueError, TypeError):
        return ParsedSource(index=index, source=None, error="source_validation_failed")
    return ParsedSource(index=index, source=source)


def _priority(value: object) -> object:
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in _PRIORITIES:
            return _PRIORITIES[normalized]
        try:
            return int(normalized)
        except ValueError as error:
            raise ValueError("invalid priority") from error
    if isinstance(value, bool):
        raise ValueError("invalid priority")
    return value


def _normalized_optional_text(value: object) -> object:
    return value.strip().casefold() if isinstance(value, str) else value


def _required_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise InvalidSourcePackStructure(f"{label} must be a non-empty bounded string")
    return value.strip()


def _term_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise InvalidSourcePackStructure(f"{label} must be a list")
    if len(value) > MAX_SOURCE_PACK_TERMS:
        raise SourcePackLimitExceeded(
            f"{label} exceeds the {MAX_SOURCE_PACK_TERMS}-item limit"
        )
    terms: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > 128:
            raise InvalidSourcePackStructure(
                f"{label} entries must be non-empty strings up to 128 characters"
            )
        terms.append(item.strip())
    return tuple(terms)


def _source_view(source: ManagedSourceCreate) -> dict[str, object]:
    return {
        "name": source.name,
        "type": source.kind,
        "url": source.endpoint,
        "category": source.category,
        "priority": source.priority,
        "stream": source.stream.value,
        "enabled": source.enabled,
        "language": source.language,
        "freshness_hours": source.freshness_hours,
    }


def _result(
    pack: ParsedSourcePack,
    items: list[dict[str, object]],
    *,
    import_result: bool,
) -> dict[str, object]:
    if import_result:
        counts = {
            "total_found": len(items),
            "created": sum(item["status"] == "created" for item in items),
            "existing_duplicates": sum(
                item["status"] == "existing_duplicate" for item in items
            ),
            "internal_duplicates": sum(
                item["status"] == "duplicate_in_pack" for item in items
            ),
            "invalid": sum(item["status"] == "invalid_source" for item in items),
        }
    else:
        counts = {
            "total_found": len(items),
            "valid_new": sum(item["status"] == "valid_new" for item in items),
            "existing_duplicates": sum(
                item["status"] == "existing_duplicate" for item in items
            ),
            "internal_duplicates": sum(
                item["status"] == "duplicate_in_pack" for item in items
            ),
            "invalid": sum(item["status"] == "invalid_source" for item in items),
        }
    return {
        "pack": {
            "name": pack.name,
            "interests": list(pack.interests),
            "exclude": list(pack.exclude),
        },
        "counts": counts,
        "sources": items,
    }
