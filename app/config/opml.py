"""Safe OPML feed parsing backed by the shared managed-source batch service."""

from __future__ import annotations

from xml.etree import ElementTree

from pydantic import ValidationError

from app.config.source_pack import (
    ParsedSource,
    ParsedSourcePack,
    SourcePackRepositoryUnavailable,
    SourcePackService,
)
from app.config.source_repository import ManagedSourceCreate, SourceRepository

MAX_OPML_BYTES = 256 * 1024
MAX_OPML_SOURCES = 500
MAX_OPML_OUTLINES = 2_000
MAX_OPML_DEPTH = 20
_FEED_TYPES = {"", "rss", "atom", "feed"}


class OpmlError(ValueError):
    """Base class for safe OPML-level failures."""

    code = "invalid_opml"


class MalformedOpml(OpmlError):
    code = "malformed_xml"


class InvalidOpmlStructure(OpmlError):
    code = "invalid_opml_structure"


class OpmlLimitExceeded(OpmlError):
    code = "opml_limit_exceeded"


OpmlRepositoryUnavailable = SourcePackRepositoryUnavailable


def parse_opml(content: str) -> ParsedSourcePack:
    """Parse bounded OPML without resolving DTDs or entities."""
    if len(content.encode("utf-8")) > MAX_OPML_BYTES:
        raise OpmlLimitExceeded(f"OPML exceeds the {MAX_OPML_BYTES}-byte limit")
    lowered = content.casefold()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise InvalidOpmlStructure("OPML DTD and entity declarations are not supported")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise MalformedOpml("OPML contains malformed XML") from error
    if _local_name(root.tag) != "opml":
        raise InvalidOpmlStructure("OPML root element must be opml")

    body = next((child for child in root if _local_name(child.tag) == "body"), None)
    if body is None:
        raise InvalidOpmlStructure("OPML body element is required")
    title = _opml_title(root)

    parsed: list[ParsedSource] = []
    outlines_seen = 0
    stack = [(child, 1) for child in reversed(list(body))]
    while stack:
        element, depth = stack.pop()
        if _local_name(element.tag) != "outline":
            continue
        outlines_seen += 1
        if outlines_seen > MAX_OPML_OUTLINES:
            raise OpmlLimitExceeded(
                f"OPML exceeds the {MAX_OPML_OUTLINES}-outline limit"
            )
        if depth > MAX_OPML_DEPTH:
            raise OpmlLimitExceeded(f"OPML exceeds the {MAX_OPML_DEPTH}-level depth limit")
        stack.extend((child, depth + 1) for child in reversed(list(element)))

        attributes = {key.casefold(): value for key, value in element.attrib.items()}
        feed_type = attributes.get("type", "").strip().casefold()
        url = attributes.get("xmlurl")
        if url is None and feed_type not in {"rss", "atom", "feed"}:
            continue
        index = len(parsed) + 1
        if len(parsed) >= MAX_OPML_SOURCES:
            raise OpmlLimitExceeded(f"OPML exceeds the {MAX_OPML_SOURCES}-source limit")
        if feed_type not in _FEED_TYPES:
            parsed.append(ParsedSource(index, None, "unsupported_opml_type"))
            continue
        if url is None:
            parsed.append(ParsedSource(index, None, "missing_xml_url"))
            continue
        name = attributes.get("title") or attributes.get("text") or url
        try:
            source = ManagedSourceCreate(
                kind="rss",
                name=name,
                endpoint=url,
                enabled=False,
            )
        except (ValidationError, ValueError, TypeError):
            parsed.append(ParsedSource(index, None, "source_validation_failed"))
            continue
        parsed.append(ParsedSource(index, source))

    return ParsedSourcePack(
        name=title,
        sources=tuple(parsed),
        interests=(),
        exclude=(),
    )


class OpmlService:
    """Preview and import OPML feeds through the shared source-batch workflow."""

    def __init__(self, repository: SourceRepository) -> None:
        self._source_packs = SourcePackService(repository)

    async def preview(self, content: str) -> dict[str, object]:
        result = await self._source_packs.preview_parsed(parse_opml(content))
        return _opml_result(result)

    async def import_opml(self, content: str) -> dict[str, object]:
        result = await self._source_packs.import_parsed(parse_opml(content))
        return _opml_result(result)


def _opml_result(result: dict[str, object]) -> dict[str, object]:
    pack = result["pack"]
    assert isinstance(pack, dict)
    return {
        "opml": {"title": pack["name"]},
        "counts": result["counts"],
        "sources": result["sources"],
    }


def _opml_title(root: ElementTree.Element) -> str:
    head = next((child for child in root if _local_name(child.tag) == "head"), None)
    if head is None:
        return "OPML Import"
    title = next((child for child in head if _local_name(child.tag) == "title"), None)
    if title is None or title.text is None or not title.text.strip():
        return "OPML Import"
    value = title.text.strip()
    if len(value) > 256:
        raise InvalidOpmlStructure("OPML title exceeds 256 characters")
    return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()
