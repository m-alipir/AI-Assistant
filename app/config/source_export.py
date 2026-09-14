"""Deterministic read-only exports of database-managed sources."""

from __future__ import annotations

import csv
from io import StringIO
from xml.etree import ElementTree

import yaml

from app.config.source_repository import SourceRepository

_CSV_FIELDS = (
    "name",
    "type",
    "url",
    "category",
    "priority",
    "stream",
    "language",
    "freshness_hours",
)


class SourceExportRepositoryUnavailable(RuntimeError):
    """The managed-source catalog could not be read for an export."""


class SourceExportService:
    """Render repository rows without modifying their persisted state."""

    def __init__(self, repository: SourceRepository) -> None:
        self._repository = repository

    async def source_pack_yaml(self) -> str:
        rows = await self._rows()
        return yaml.safe_dump(
            {"name": "Managed Sources Export", "sources": [_source_pack_row(row) for row in rows]},
            allow_unicode=True,
            sort_keys=False,
        )

    async def opml(self) -> str:
        rows = await self._rows()
        root = ElementTree.Element("opml", {"version": "2.0"})
        head = ElementTree.SubElement(root, "head")
        ElementTree.SubElement(head, "title").text = "Managed RSS Sources Export"
        body = ElementTree.SubElement(root, "body")
        for row in rows:
            if row["kind"] != "rss":
                continue
            endpoint = str(row["canonical_endpoint"])
            name = str(row["name"])
            ElementTree.SubElement(
                body,
                "outline",
                {"text": name, "title": name, "type": "rss", "xmlUrl": endpoint},
            )
        return ElementTree.tostring(root, encoding="unicode", xml_declaration=True) + "\n"

    async def csv(self) -> str:
        rows = await self._rows()
        output = StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row(row))
        return output.getvalue()

    async def _rows(self) -> list[dict[str, object]]:
        try:
            return await self._repository.list()
        except Exception as error:
            raise SourceExportRepositoryUnavailable(
                "managed source repository is unavailable"
            ) from error


def _source_pack_row(row: dict[str, object]) -> dict[str, object]:
    """Use canonical endpoint and every Source Pack-supported persisted field."""
    return {
        "name": row["name"],
        "type": row["kind"],
        "url": row["canonical_endpoint"],
        "category": row["category"],
        "priority": row["priority"],
        "stream": row["stream"],
        "enabled": row["enabled"],
        "language": row["language"],
        "freshness_hours": row["freshness_hours"],
    }


def _csv_row(row: dict[str, object]) -> dict[str, object]:
    """Keep only CSV-import-supported metadata; CSV imports always disable sources."""
    return {
        "name": row["name"],
        "type": row["kind"],
        "url": row["canonical_endpoint"],
        "category": row["category"] or "",
        "priority": row["priority"],
        "stream": row["stream"],
        "language": row["language"] or "",
        "freshness_hours": row["freshness_hours"] or "",
    }
