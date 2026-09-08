"""Opt-in PostgreSQL integration regression for Search / Ask migrations 0013 and 0014.

Set SEARCH_INTEGRATION_DATABASE_URL to a dedicated disposable database only. This test never
contacts Gmail, YouTube, RSS, or an LLM provider.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.knowledge.search import SearchFilters, fetch_sql_candidates

DATABASE_URL = os.environ.get("SEARCH_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="set SEARCH_INTEGRATION_DATABASE_URL to run against a dedicated migrated PostgreSQL DB",
)


@pytest.mark.asyncio
async def test_search_sql_supports_current_metadata_and_legacy_rows() -> None:
    """Validate the real PostgreSQL aggregate query and safe Gmail aliasing after migrations."""
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    suffix = uuid.uuid4().hex
    event_id = f"n{suffix}"
    legacy_event_id = f"l{suffix}"
    email_id = f"email-{suffix}"
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "20260908_0014"
            await connection.execute(
                text(
                    "INSERT INTO events (id, canonical_title, occurred_at, embedding_dimensions) "
                    "VALUES (:id, :title, :occurred_at, 1)"
                ),
                {"id": event_id, "title": "NVIDIA RSS integration event", "occurred_at": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO events (id, canonical_title, occurred_at, embedding_dimensions) "
                    "VALUES (:id, :title, :occurred_at, 1)"
                ),
                {
                    "id": legacy_event_id,
                    "title": "NVIDIA legacy event without metadata",
                    "occurred_at": now,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO event_sources "
                    "(event_id, source_item_id, canonical_url, source_kind) "
                    "VALUES (:event_id, :source_item_id, :url, 'rss')"
                ),
                {
                    "event_id": event_id,
                    "source_item_id": f"source-{suffix}",
                    "url": "https://example.test/nvidia",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO event_search_metadata "
                    "(event_id, category_paths_json, entities_json, topics_json) "
                    "VALUES (:event_id, '[\"technology.ai\"]', '[\"NVIDIA\"]', '[\"ai\"]')"
                ),
                {"event_id": event_id},
            )
            await connection.execute(
                text("INSERT INTO claims (id, event_id, source_item_id, statement) "
                     "VALUES (:id, :event_id, :source_item_id, :statement)"),
                {
                    "id": f"c{suffix}",
                    "event_id": event_id,
                    "source_item_id": f"source-{suffix}",
                    "statement": "NVIDIA source-backed integration fact.",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO email_classifications "
                    "(source_item_id, classification, action_summary, created_at) "
                    "VALUES (:id, 'security', :summary, :created_at)"
                ),
                {
                    "id": email_id,
                    "summary": "Review the account security alert.",
                    "created_at": now,
                },
            )

        events, _ = await fetch_sql_candidates(
            engine,
            SearchFilters(
                question="NVIDIA hakkında ne oldu?",
                since=now - timedelta(days=1),
                until=now + timedelta(days=1),
            ),
        )
        _, emails = await fetch_sql_candidates(
            engine,
            SearchFilters(
                question="Son önemli e-postalarım neler?",
                source_type="gmail",
                since=now - timedelta(days=1),
                until=now + timedelta(days=1),
            ),
        )

        assert {event.event_id for event in events} == {event_id, legacy_event_id}
        nvidia = next(event for event in events if event.event_id == event_id)
        assert nvidia.source_links == ["https://example.test/nvidia"]
        assert emails[0].classification == "security"
        assert emails[0].recorded_at is not None
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM email_classifications WHERE source_item_id = :id"),
                {"id": email_id},
            )
            for table in ("event_search_metadata", "event_sources", "claims", "inferences"):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE event_id IN (:event_id, :legacy_event_id)"),
                    {"event_id": event_id, "legacy_event_id": legacy_event_id},
                )
            await connection.execute(
                text("DELETE FROM events WHERE id IN (:event_id, :legacy_event_id)"),
                {"event_id": event_id, "legacy_event_id": legacy_event_id},
            )
        await engine.dispose()
