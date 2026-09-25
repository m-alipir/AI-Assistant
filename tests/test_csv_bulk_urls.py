from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.bulk_urls import (
    MAX_BULK_URL_BYTES,
    BulkUrlLimitExceeded,
    BulkUrlRepositoryUnavailable,
    BulkUrlService,
    InvalidBulkUrlStructure,
    parse_bulk_urls,
)
from app.config.csv_import import (
    MAX_CSV_BYTES,
    CsvImportService,
    CsvLimitExceeded,
    CsvRepositoryUnavailable,
    InvalidCsvStructure,
    MalformedCsv,
    parse_source_csv,
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


class ImportRepository:
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


VALID_CSV = """name,type,url,category,priority,stream,language,freshness_hours
Tech Feed,RSS,HTTPS://Example.test:443/feed#fragment,technology,high,tech,,24
Video Channel,youtube,UCVBX2n_5egE9XuJL8NUS0Xg,programming,10,personalized,en,72
"""


@pytest.mark.asyncio
async def test_csv_preview_normalizes_rows_and_never_writes() -> None:
    repository = ImportRepository()
    result = await CsvImportService(repository).preview(VALID_CSV)

    assert result["csv"] == {"rows": 2}
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
        "name": "Tech Feed",
        "type": "rss",
        "url": "https://example.test/feed",
        "category": "technology",
        "priority": 50,
        "stream": "tech",
        "enabled": False,
        "language": None,
        "freshness_hours": 24,
    }
    assert sources[1]["source"]["type"] == "youtube"
    assert sources[1]["source"]["enabled"] is False
    assert repository.rows == {}


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        ('url\n"https://example.test/feed', MalformedCsv),
        ("name,type\nFeed,rss\n", InvalidCsvStructure),
        ("url,unknown\nhttps://example.test/feed,x\n", InvalidCsvStructure),
        ("url,URL\nhttps://example.test/feed,x\n", InvalidCsvStructure),
        ("x" * (MAX_CSV_BYTES + 1), CsvLimitExceeded),
    ],
    ids=["malformed", "missing-url", "unknown-header", "duplicate-header", "size"],
)
def test_csv_rejects_malformed_structure_and_size(
    content: str, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        parse_source_csv(content)


def test_csv_source_count_bound_is_enforced() -> None:
    content = "url\n" + "https://example.test/feed\n" * 501
    with pytest.raises(CsvLimitExceeded, match="500-source"):
        parse_source_csv(content)


@pytest.mark.asyncio
async def test_csv_preview_reports_invalid_existing_and_internal_duplicates() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = ImportRepository([existing])
    content = """name,type,url
Existing,rss,HTTPS://EXISTING.test:443/feed#x
New,rss,https://new.test/feed
New copy,atom,HTTPS://NEW.TEST:443/feed#x
Bad URL,rss,relative
Bad type,podcast,https://pod.test/feed
Malformed,rss
"""
    result = await CsvImportService(repository).preview(content)

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
    assert result["sources"][-1]["error"] == "malformed_csv_row"


@pytest.mark.asyncio
async def test_csv_import_creates_only_new_rows_and_is_idempotent() -> None:
    repository = ImportRepository()
    content = """url
https://new.test/feed
HTTPS://NEW.TEST:443/feed#x
relative
"""
    service = CsvImportService(repository)
    first = await service.import_csv(content)
    second = await service.import_csv(content)

    assert first["counts"] == {
        "total_found": 3,
        "created": 1,
        "existing_duplicates": 0,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert second["counts"] == {
        "total_found": 3,
        "created": 0,
        "existing_duplicates": 1,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert next(iter(repository.rows.values()))["enabled"] is False


@pytest.mark.asyncio
async def test_bulk_url_preview_reports_all_states_without_writes() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = ImportRepository([existing])
    content = """
https://existing.test/feed
https://new.test/feed
HTTPS://NEW.TEST:443/feed#fragment
relative
"""
    result = await BulkUrlService(repository).preview(content)

    assert result["bulk_urls"] == {"lines": 4}
    assert result["counts"] == {
        "total_found": 4,
        "valid_new": 1,
        "existing_duplicates": 1,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert repository.created == 0


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        (" \n\t", InvalidBulkUrlStructure),
        ("x" * (MAX_BULK_URL_BYTES + 1), BulkUrlLimitExceeded),
        ("https://example.test/feed\n" * 501, BulkUrlLimitExceeded),
    ],
    ids=["empty", "size", "count"],
)
def test_bulk_url_bounds_are_enforced(content: str, error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        parse_bulk_urls(content)


@pytest.mark.asyncio
async def test_bulk_url_import_creates_only_new_rows_and_is_idempotent() -> None:
    repository = ImportRepository()
    content = "https://new.test/feed\nHTTPS://NEW.TEST:443/feed#fragment\nrelative"
    service = BulkUrlService(repository)
    first = await service.import_urls(content)
    second = await service.import_urls(content)

    assert first["counts"] == {
        "total_found": 3,
        "created": 1,
        "existing_duplicates": 0,
        "internal_duplicates": 1,
        "invalid": 1,
    }
    assert second["counts"]["created"] == 0
    assert second["counts"]["existing_duplicates"] == 1
    assert next(iter(repository.rows.values()))["enabled"] is False


@pytest.mark.asyncio
async def test_csv_and_bulk_url_repository_failures_hide_database_details() -> None:
    class UnavailableRepository:
        async def list(self) -> list[dict[str, object]]:
            raise RuntimeError("private database detail")

    repository = UnavailableRepository()
    with pytest.raises(CsvRepositoryUnavailable, match="repository is unavailable"):
        await CsvImportService(repository).preview(VALID_CSV)  # type: ignore[arg-type]
    with pytest.raises(BulkUrlRepositoryUnavailable, match="repository is unavailable"):
        await BulkUrlService(repository).preview(  # type: ignore[arg-type]
            "https://example.test/feed"
        )


def test_admin_csv_and_bulk_url_preview_import_and_error_mapping() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    repository = ImportRepository()
    app.state.source_repository = repository
    queued: list[str] = []

    async def queue_question(source_id: str) -> str:
        queued.append(source_id)
        return "delivered"

    app.state.queue_source_category_question = queue_question
    with TestClient(app) as client:
        csv_preview = client.post("/admin/csv/preview", json={"csv": VALID_CSV})
        csv_import = client.post("/admin/csv/import", json={"csv": VALID_CSV})
        csv_repeat = client.post("/admin/csv/import", json={"csv": VALID_CSV})
        csv_unknown = client.post(
            "/admin/csv/import", json={"csv": "url\nhttps://unknown-csv.test/feed"}
        )
        csv_malformed = client.post(
            "/admin/csv/preview", json={"csv": 'url\n"https://example.test/feed'}
        )
        bulk_preview = client.post(
            "/admin/bulk-urls/preview", json={"urls": "https://bulk.test/feed"}
        )
        bulk_import = client.post(
            "/admin/bulk-urls/import", json={"urls": "https://bulk.test/feed"}
        )
        bulk_repeat = client.post(
            "/admin/bulk-urls/import", json={"urls": "https://bulk.test/feed"}
        )
        bulk_empty = client.post("/admin/bulk-urls/preview", json={"urls": " "})

    assert csv_preview.status_code == 200
    assert csv_import.json()["counts"]["created"] == 2
    assert csv_repeat.json()["counts"]["created"] == 0
    assert csv_import.json()["sources"][0]["source"]["category"] == "technology"
    assert csv_import.json()["sources"][1]["source"]["category"] == "programming"
    assert csv_unknown.json()["counts"]["created"] == 1
    assert csv_malformed.status_code == 400
    assert csv_malformed.json()["detail"]["code"] == "malformed_csv"
    assert bulk_preview.status_code == 200
    assert bulk_import.json()["counts"]["created"] == 1
    assert bulk_repeat.json()["counts"]["created"] == 0
    assert bulk_empty.status_code == 422
    assert bulk_empty.json()["detail"]["code"] == "invalid_bulk_url_structure"
    assert queued == ["created-3", "created-4"]

    class UnavailableRepository:
        async def list(self) -> list[dict[str, Any]]:
            raise RuntimeError("private database detail")

    app.state.source_repository = UnavailableRepository()
    with TestClient(app) as client:
        unavailable = client.post("/admin/csv/import", json={"csv": VALID_CSV})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "managed source repository is unavailable"
