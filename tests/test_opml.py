from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.opml import (
    MAX_OPML_BYTES,
    InvalidOpmlStructure,
    MalformedOpml,
    OpmlLimitExceeded,
    OpmlRepositoryUnavailable,
    OpmlService,
    parse_opml,
)
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


class OpmlRepository:
    def __init__(self, sources: list[ManagedSourceCreate] | None = None) -> None:
        self.rows = {
            f"existing-{index}": _row(f"existing-{index}", source)
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


VALID_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Technology Feeds</title></head>
  <body>
    <outline text="Technology">
      <outline text="TechCrunch" type="rss"
               xmlUrl="HTTPS://TechCrunch.com:443/feed/#fragment"
               htmlUrl="https://techcrunch.com/" />
      <outline title="Example Atom" type="atom"
               xmlUrl="https://example.test/atom.xml" />
    </outline>
  </body>
</opml>
"""


@pytest.mark.asyncio
async def test_valid_opml_preview_extracts_normalized_feeds_without_writes() -> None:
    repository = OpmlRepository()
    result = await OpmlService(repository).preview(VALID_OPML)

    assert result["opml"] == {"title": "Technology Feeds"}
    assert result["counts"] == {
        "total_found": 2,
        "valid_new": 2,
        "existing_duplicates": 0,
        "internal_duplicates": 0,
        "invalid": 0,
    }
    sources = result["sources"]
    assert isinstance(sources, list)
    assert sources[0]["source"] == {
        "name": "TechCrunch",
        "type": "rss",
        "url": "https://techcrunch.com/feed/",
        "category": None,
        "priority": 0,
        "stream": "tech",
        "enabled": False,
        "language": None,
        "freshness_hours": None,
    }
    assert sources[1]["source"]["name"] == "Example Atom"
    assert repository.rows == {}


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        ("<opml><body>", MalformedOpml),
        ("<feeds />", InvalidOpmlStructure),
        ("<opml />", InvalidOpmlStructure),
        (
            '<!DOCTYPE opml [<!ENTITY x "unsafe">]><opml><body /></opml>',
            InvalidOpmlStructure,
        ),
        ("x" * (MAX_OPML_BYTES + 1), OpmlLimitExceeded),
    ],
    ids=["malformed", "root", "body", "entity", "size"],
)
def test_opml_level_validation_rejects_unsafe_or_invalid_xml(
    content: str, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        parse_opml(content)


def test_opml_source_count_and_depth_bounds_are_enforced() -> None:
    row = '<outline text="feed" type="rss" xmlUrl="https://example.test/feed" />'
    too_many = f"<opml><body>{row * 501}</body></opml>"
    with pytest.raises(OpmlLimitExceeded, match="500-source"):
        parse_opml(too_many)

    nested = '<outline text="folder">' * 21 + row + "</outline>" * 21
    with pytest.raises(OpmlLimitExceeded, match="20-level"):
        parse_opml(f"<opml><body>{nested}</body></opml>")


@pytest.mark.asyncio
async def test_preview_reports_invalid_existing_and_canonical_internal_duplicates() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = OpmlRepository([existing])
    content = """<opml><body>
      <outline text="Existing" type="rss" xmlUrl="HTTPS://EXISTING.test:443/feed#x" />
      <outline text="New" type="rss" xmlUrl="https://new.test/feed" />
      <outline text="New copy" type="feed" xmlUrl="HTTPS://NEW.TEST:443/feed#x" />
      <outline text="Bad URL" type="rss" xmlUrl="relative" />
      <outline text="Missing URL" type="rss" />
      <outline text="Podcast" type="podcast" xmlUrl="https://pod.test/feed" />
    </body></opml>"""
    result = await OpmlService(repository).preview(content)

    assert result["counts"] == {
        "total_found": 6,
        "valid_new": 1,
        "existing_duplicates": 1,
        "internal_duplicates": 1,
        "invalid": 3,
    }
    assert [item["status"] for item in result["sources"]] == [
        "existing_duplicate",
        "valid_new",
        "duplicate_in_pack",
        "invalid_source",
        "invalid_source",
        "invalid_source",
    ]
    assert [item.get("error") for item in result["sources"][3:]] == [
        "source_validation_failed",
        "missing_xml_url",
        "unsupported_opml_type",
    ]


@pytest.mark.asyncio
async def test_opml_import_creates_only_new_sources_and_reimport_is_idempotent() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = OpmlRepository([existing])
    content = """<opml><body>
      <outline text="Existing" type="rss" xmlUrl="https://existing.test/feed" />
      <outline text="New" type="rss" xmlUrl="https://new.test/feed" />
      <outline text="New copy" type="atom" xmlUrl="HTTPS://NEW.TEST:443/feed#x" />
      <outline text="Invalid" type="rss" xmlUrl="relative" />
    </body></opml>"""
    service = OpmlService(repository)
    first = await service.import_opml(content)
    second = await service.import_opml(content)

    assert first["counts"] == {
        "total_found": 4,
        "created": 1,
        "existing_duplicates": 1,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert second["counts"] == {
        "total_found": 4,
        "created": 0,
        "existing_duplicates": 2,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert len(repository.rows) == 2


@pytest.mark.asyncio
async def test_opml_repository_unavailable_is_reported_without_database_details() -> None:
    class UnavailableRepository:
        async def list(self) -> list[dict[str, object]]:
            raise RuntimeError("private database detail")

    service = OpmlService(UnavailableRepository())  # type: ignore[arg-type]
    with pytest.raises(OpmlRepositoryUnavailable, match="repository is unavailable"):
        await service.preview(VALID_OPML)
    with pytest.raises(OpmlRepositoryUnavailable, match="repository is unavailable"):
        await service.import_opml(VALID_OPML)


def test_admin_opml_preview_import_and_safe_error_mapping() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.source_repository = OpmlRepository()
    with TestClient(app) as client:
        preview = client.post("/admin/opml/preview", json={"opml": VALID_OPML})
        imported = client.post("/admin/opml/import", json={"opml": VALID_OPML})
        repeated = client.post("/admin/opml/import", json={"opml": VALID_OPML})
        malformed = client.post("/admin/opml/preview", json={"opml": "<opml>"})
        invalid = client.post("/admin/opml/preview", json={"opml": "<feeds />"})
        oversized = client.post(
            "/admin/opml/preview", json={"opml": "x" * (MAX_OPML_BYTES + 1)}
        )

    assert preview.status_code == 200
    assert imported.json()["counts"]["created"] == 2
    assert repeated.json()["counts"]["created"] == 0
    assert malformed.status_code == 400
    assert malformed.json()["detail"]["code"] == "malformed_xml"
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_opml_structure"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "opml_limit_exceeded"

    class UnavailableRepository:
        async def list(self) -> list[dict[str, Any]]:
            raise RuntimeError("private database detail")

    app.state.source_repository = UnavailableRepository()
    with TestClient(app) as client:
        unavailable = client.post("/admin/opml/import", json={"opml": VALID_OPML})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "managed source repository is unavailable"
