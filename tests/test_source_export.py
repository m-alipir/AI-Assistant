"""Read-only managed-source export coverage."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.csv_import import parse_source_csv
from app.config.opml import parse_opml
from app.config.source_export import SourceExportRepositoryUnavailable, SourceExportService
from app.config.source_pack import SourcePackService, parse_source_pack
from app.config.source_repository import ManagedSourceCreate, SourceAlreadyExists
from app.main import create_app


def _row(source_id: str, source: ManagedSourceCreate) -> dict[str, object]:
    return {
        "id": source_id,
        "kind": source.kind,
        "name": source.name,
        "canonical_endpoint": source.endpoint,
        "stream": source.stream.value,
        "enabled": source.enabled,
        "priority": source.priority,
        "category": source.category,
        "language": source.language,
        "freshness_hours": source.freshness_hours,
    }


class ExportRepository:
    def __init__(self, sources: list[ManagedSourceCreate] | None = None) -> None:
        self.rows = {
            f"source-{index}": _row(f"source-{index}", source)
            for index, source in enumerate(sources or [], 1)
        }
        self.created = 0

    async def list(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.rows.values()]

    async def create(self, source: ManagedSourceCreate) -> dict[str, object]:
        if any(
            row["kind"] == source.kind and row["canonical_endpoint"] == source.endpoint
            for row in self.rows.values()
        ):
            raise SourceAlreadyExists
        self.created += 1
        source_id = f"created-{self.created}"
        row = _row(source_id, source)
        self.rows[source_id] = row
        return dict(row)


def _sources() -> list[ManagedSourceCreate]:
    return [
        ManagedSourceCreate(
            kind="rss",
            name="Enabled Feed",
            endpoint="HTTPS://Example.test:443/feed#fragment",
            enabled=True,
            priority=50,
            category="technology",
            freshness_hours=24,
        ),
        ManagedSourceCreate(
            kind="youtube",
            name="Disabled Channel",
            endpoint="UCVBX2n_5egE9XuJL8NUS0Xg",
            enabled=False,
            priority=-50,
            category="programming",
            stream="personalized",
            language="en",
            freshness_hours=72,
        ),
    ]


@pytest.mark.asyncio
async def test_source_pack_export_is_deterministic_and_round_trips_supported_metadata() -> None:
    exported = await SourceExportService(ExportRepository(_sources())).source_pack_yaml()

    parsed = parse_source_pack(exported)
    assert parsed.name == "Managed Sources Export"
    assert [item.source.endpoint for item in parsed.sources if item.source] == [
        "https://example.test/feed",
        "UCVBX2n_5egE9XuJL8NUS0Xg",
    ]
    assert parsed.sources[0].source is not None
    assert parsed.sources[0].source.enabled is True
    assert parsed.sources[1].source is not None
    assert parsed.sources[1].source.language == "en"

    destination = ExportRepository()
    result = await SourcePackService(destination).import_pack(exported)
    assert result["counts"]["created"] == 2
    assert [row["enabled"] for row in destination.rows.values()] == [True, False]


@pytest.mark.asyncio
async def test_opml_and_csv_exports_include_disabled_rows_with_format_limits() -> None:
    service = SourceExportService(ExportRepository(_sources()))

    opml = await service.opml()
    parsed_opml = parse_opml(opml)
    assert len(parsed_opml.sources) == 1
    assert parsed_opml.sources[0].source is not None
    assert parsed_opml.sources[0].source.endpoint == "https://example.test/feed"
    assert parsed_opml.sources[0].source.enabled is False

    csv = await service.csv()
    parsed_csv = parse_source_csv(csv)
    assert [item.source.endpoint for item in parsed_csv.sources if item.source] == [
        "https://example.test/feed",
        "UCVBX2n_5egE9XuJL8NUS0Xg",
    ]
    assert all(item.source is not None and not item.source.enabled for item in parsed_csv.sources)
    assert parsed_csv.sources[1].source is not None
    assert parsed_csv.sources[1].source.language == "en"


@pytest.mark.asyncio
async def test_export_hides_repository_details() -> None:
    class UnavailableRepository:
        async def list(self) -> list[dict[str, object]]:
            raise RuntimeError("private database detail")

    with pytest.raises(SourceExportRepositoryUnavailable, match="repository is unavailable"):
        await SourceExportService(UnavailableRepository()).csv()  # type: ignore[arg-type]


def test_admin_export_endpoints_and_repository_failure() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.source_repository = ExportRepository(_sources())
    with TestClient(app) as client:
        source_pack = client.get("/admin/source-packs/export")
        opml = client.get("/admin/opml/export")
        csv = client.get("/admin/csv/export")

    assert source_pack.status_code == 200
    assert source_pack.headers["content-disposition"] == (
        'attachment; filename="managed-sources.yaml"'
    )
    assert "enabled: true" in source_pack.text
    assert opml.status_code == 200
    assert "https://example.test/feed" in opml.text
    assert "UCVBX2n_5egE9XuJL8NUS0Xg" not in opml.text
    assert csv.status_code == 200
    assert "Disabled Channel" in csv.text

    class UnavailableRepository:
        async def list(self) -> list[dict[str, Any]]:
            raise RuntimeError("private database detail")

    app.state.source_repository = UnavailableRepository()
    with TestClient(app) as client:
        unavailable = client.get("/admin/source-packs/export")
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "managed source repository is unavailable"
