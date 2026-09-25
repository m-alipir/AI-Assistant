from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.source_pack import (
    MAX_SOURCE_PACK_BYTES,
    InvalidSourcePackStructure,
    MalformedSourcePack,
    SourcePackLimitExceeded,
    SourcePackRepositoryUnavailable,
    SourcePackService,
    parse_source_pack,
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


class PackRepository:
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


VALID_PACK = """
name: Technology Pack
sources:
  - name: TechCrunch
    type: RSS
    url: HTTPS://TechCrunch.com:443/feed/#fragment
    category: technology
    priority: high
  - name: Fireship
    type: youtube
    url: UCVBX2n_5egE9XuJL8NUS0Xg
    category: programming
    priority: high
interests:
  - artificial intelligence
  - game development
exclude:
  - celebrity news
"""


@pytest.mark.asyncio
async def test_valid_pack_preview_is_normalized_and_does_not_mutate_repository() -> None:
    repository = PackRepository()
    result = await SourcePackService(repository).preview(VALID_PACK)

    assert result["pack"] == {
        "name": "Technology Pack",
        "interests": ["artificial intelligence", "game development"],
        "exclude": ["celebrity news"],
    }
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
        "category": "technology",
        "priority": 50,
        "stream": "tech",
        "enabled": False,
        "language": None,
        "freshness_hours": None,
    }
    assert sources[1]["source"]["type"] == "youtube"
    assert repository.rows == {}


@pytest.mark.parametrize(
    ("content", "error_type"),
    [
        ("name: [broken", MalformedSourcePack),
        ("- not\n- a\n- mapping", InvalidSourcePackStructure),
        ("name: Missing Sources", InvalidSourcePackStructure),
        ("name: Aliased\nsources: &items []\ninterests: *items", InvalidSourcePackStructure),
        ("x" * (MAX_SOURCE_PACK_BYTES + 1), SourcePackLimitExceeded),
    ],
    ids=["malformed", "root", "sources", "alias", "size"],
)
def test_pack_level_validation_rejects_malformed_structure_aliases_and_size(
    content: str, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        parse_source_pack(content)


def test_source_count_bound_is_enforced() -> None:
    row = "  - {name: x, type: rss, url: https://e.test/}\n"
    content = "name: Too Many\nsources:\n" + row * 501
    with pytest.raises(SourcePackLimitExceeded, match="500-source"):
        parse_source_pack(content)


@pytest.mark.asyncio
async def test_preview_reports_mixed_invalid_existing_and_internal_duplicates() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = PackRepository([existing])
    content = """
name: Mixed Pack
sources:
  - {name: Existing copy, type: feed, url: HTTPS://EXISTING.test:443/feed#x}
  - {name: New, type: rss, url: https://new.test/feed}
  - {name: New canonical copy, type: atom, url: HTTPS://NEW.TEST:443/feed#fragment}
  - {name: Bad URL, type: rss, url: not-a-url}
  - {name: Bad type, type: podcast, url: https://podcast.test/feed}
"""
    result = await SourcePackService(repository).preview(content)

    assert result["counts"] == {
        "total_found": 5,
        "valid_new": 1,
        "existing_duplicates": 1,
        "internal_duplicates": 1,
        "invalid": 2,
    }
    assert [item["status"] for item in result["sources"]] == [
        "existing_duplicate",
        "valid_new",
        "duplicate_in_pack",
        "invalid_source",
        "invalid_source",
    ]
    assert result["sources"][3]["error"] == "source_validation_failed"
    assert result["sources"][4]["error"] == "invalid_source_type"


@pytest.mark.asyncio
async def test_import_creates_only_new_valid_sources_and_retry_is_idempotent() -> None:
    existing = ManagedSourceCreate(
        kind="rss", name="Existing", endpoint="https://existing.test/feed"
    )
    repository = PackRepository([existing])
    content = """
name: Import Pack
sources:
  - {name: Existing copy, type: rss, url: https://existing.test/feed}
  - {name: New, type: rss, url: https://new.test/feed}
  - {name: New copy, type: rss, url: HTTPS://NEW.TEST:443/feed#fragment}
  - {name: Invalid, type: rss, url: relative}
"""
    service = SourcePackService(repository)
    first = await service.import_pack(content)
    second = await service.import_pack(content)

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
async def test_repository_unavailable_is_safe_for_preview_and_import() -> None:
    class UnavailableRepository:
        async def list(self) -> list[dict[str, object]]:
            raise RuntimeError("database credentials must not escape")

    service = SourcePackService(UnavailableRepository())  # type: ignore[arg-type]
    with pytest.raises(SourcePackRepositoryUnavailable, match="repository is unavailable"):
        await service.preview(VALID_PACK)
    with pytest.raises(SourcePackRepositoryUnavailable, match="repository is unavailable"):
        await service.import_pack(VALID_PACK)


def test_admin_source_pack_api_maps_pack_and_repository_errors() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    repository = PackRepository()
    app.state.source_repository = repository
    queued: list[str] = []

    async def queue_question(source_id: str) -> str:
        queued.append(source_id)
        return "delivered"

    app.state.queue_source_category_question = queue_question
    with TestClient(app) as client:
        preview = client.post("/admin/source-packs/preview", json={"yaml": VALID_PACK})
        imported = client.post("/admin/source-packs/import", json={"yaml": VALID_PACK})
        repeated = client.post("/admin/source-packs/import", json={"yaml": VALID_PACK})
        ambiguous = client.post(
            "/admin/source-packs/import",
            json={
                "yaml": "name: Unknown\nsources:\n"
                "  - name: Unknown\n    type: RSS\n"
                "    url: https://unknown-pack.test/feed\n"
            },
        )
        malformed = client.post(
            "/admin/source-packs/preview", json={"yaml": "name: [broken"}
        )
        invalid = client.post(
            "/admin/source-packs/preview", json={"yaml": "name: Invalid"}
        )
        oversized = client.post(
            "/admin/source-packs/preview",
            json={"yaml": "x" * (MAX_SOURCE_PACK_BYTES + 1)},
        )

    assert preview.status_code == 200
    assert imported.json()["counts"]["created"] == 2
    assert repeated.json()["counts"] == {
        "total_found": 2,
        "created": 0,
        "existing_duplicates": 2,
        "internal_duplicates": 0,
        "invalid": 0,
    }
    assert ambiguous.json()["counts"]["created"] == 1
    assert queued == ["created-3"]
    assert repository.rows["created-3"]["category"] is None
    assert malformed.status_code == 400
    assert malformed.json()["detail"]["code"] == "malformed_yaml"
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_pack_structure"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "source_pack_limit_exceeded"

    class UnavailableRepository:
        async def list(self) -> list[dict[str, Any]]:
            raise RuntimeError("private database detail")

    app.state.source_repository = UnavailableRepository()
    with TestClient(app) as client:
        unavailable = client.post("/admin/source-packs/import", json={"yaml": VALID_PACK})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "managed source repository is unavailable"
