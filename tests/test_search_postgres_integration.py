"""Opt-in PostgreSQL integration regression for Search / Ask and Telegram migrations.

Set SEARCH_INTEGRATION_DATABASE_URL to a dedicated disposable database only. This test never
contacts Gmail, YouTube, RSS, or an LLM provider.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ingestion.schemas import SourceItem, SourceKind, SourceStream, TimestampConfidence
from app.jobs.rss_runtime import database_persistence
from app.knowledge.search import SearchFilters, fetch_sql_candidates, fetch_sql_event
from app.llm.core import ExtractedClaim, ExtractorResult, GatekeeperResult

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
            assert revision == "20260927_0032"
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
                text(
                    "INSERT INTO claims (id, event_id, source_item_id, statement) "
                    "VALUES (:id, :event_id, :source_item_id, :statement)"
                ),
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
        detail = await fetch_sql_event(engine, event_id)
        assert detail is not None
        assert detail.title == "NVIDIA RSS integration event"
        assert detail.verified_facts == ["NVIDIA source-backed integration fact."]
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


@pytest.mark.asyncio
async def test_telegram_migration_creates_replay_tables_and_channel_key() -> None:
    """Validate the M22.1 schema against a real dedicated PostgreSQL database."""
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = set(
                (
                    await connection.scalars(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_name IN "
                            "('telegram_updates', 'telegram_feedback_tokens', "
                            "'telegram_polling_state')"
                        )
                    )
                ).all()
            )
            key_columns = (
                await connection.scalars(
                    text(
                        "SELECT attribute.attname FROM pg_constraint AS constraint_row "
                        "JOIN unnest(constraint_row.conkey) WITH ORDINALITY AS "
                        "key_column(attnum, position) ON true "
                        "JOIN pg_attribute AS attribute ON attribute.attrelid = "
                        "constraint_row.conrelid AND attribute.attnum = key_column.attnum "
                        "WHERE constraint_row.conrelid = 'notification_deliveries'::regclass "
                        "AND constraint_row.contype = 'p' ORDER BY key_column.position"
                    )
                )
            ).all()
        assert revision == "20260927_0032"
        assert tables == {
            "telegram_updates",
            "telegram_feedback_tokens",
            "telegram_polling_state",
        }
        assert key_columns == ["channel", "idempotency_key"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_event_persistence_clusters_sources_and_keeps_runtime_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify M19 persistence against pgvector without a provider or user data."""
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix, now = uuid.uuid4().hex, datetime.now(UTC)
    gate = GatekeeperResult(
        relevant=True, global_importance=6, personal_relevance=5, importance=8,
        needs_full_extraction=False,
        category_paths=["technology.ai"], entities=["NVIDIA"], topics=["ai"],
    )
    extracted = ExtractorResult(
        compact_summary="NVIDIA announced an AI platform update.", what_changed="Platform update.",
        claims=[ExtractedClaim(statement="NVIDIA announced the platform update.")],
        entities=["NVIDIA"], topics=["ai"], uncertainty_markers=[],
    )
    extracted._embedding_model_id, extracted._embedding_dimensions = "fixture-embed", 2
    extracted._event_embedding, extracted._claim_embeddings = [0.1, 0.2], [[0.2, 0.1]]
    persist_event, persist_briefing, *_ = database_persistence(sessions)

    def item(name: str, digest: str) -> SourceItem:
        return SourceItem(
            source_name=name,
            source_kind=SourceKind.RSS,
            stream=SourceStream.TECH,
            canonical_url=f"https://example.test/{digest}",
            title="NVIDIA announces AI platform update",
            snippet="Fixture only",
            source_published_at=now,
            discovered_at=now,
            fetched_at=now,
            timestamp_confidence=TimestampConfidence.SOURCE,
            source_freshness_hours=48,
            content_hash=digest,
        )

    event_id = await persist_event(item("Fixture A", f"a-{suffix}"), gate, extracted)
    same_event_id = await persist_event(item("Fixture B", f"b-{suffix}"), gate, extracted)
    assert same_event_id == event_id
    await persist_briefing([])
    async with engine.connect() as connection:
        briefing_id = await connection.scalar(
            text("SELECT briefing_id FROM briefing_items WHERE event_id = :id LIMIT 1"),
            {"id": event_id},
        )

    import app.config.settings as settings_module

    safe_settings = settings_module.Settings.model_construct(database_url=DATABASE_URL)
    monkeypatch.setattr(settings_module, "get_settings", lambda: safe_settings)
    from app.main import create_app

    application = create_app(settings=safe_settings)
    try:
        detail = await application.state.agent_api_latest_briefing()
        item_projection = next(
            item for item in detail["items"] if item["event_id"] == event_id
        )
        from app.telegram.service import _render_daily_briefing

        rendered, _ = _render_daily_briefing(None, [item_projection], None)
        async with engine.connect() as connection:
            row = (await connection.execute(text(
                "SELECT embedding_model_id, embedding_dimensions, "
                "(SELECT count(*) FROM event_sources WHERE event_id = :id) AS sources, "
                "(SELECT count(*) FROM event_sources WHERE event_id = :id "
                "AND source_name IS NOT NULL AND freshness_hours = 48) AS provenance "
                "FROM events WHERE id = :id"), {"id": event_id})).mappings().one()
        assert row["embedding_model_id"] == "fixture-embed"
        assert row["embedding_dimensions"] == 2
        assert row["sources"] == 2
        assert row["provenance"] == 2
        assert item_projection["source_names"] == ["Fixture A", "Fixture B"]
        assert rendered.endswith("(Fixture A · Fixture B)")
    finally:
        await application.state.engine.dispose()
        async with engine.begin() as connection:
            if briefing_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM briefing_item_content WHERE briefing_id = :briefing_id "
                        "AND event_id = :event_id"
                    ),
                    {"briefing_id": briefing_id, "event_id": event_id},
                )
                await connection.execute(
                    text(
                        "DELETE FROM briefing_items WHERE briefing_id = :briefing_id "
                        "AND event_id = :event_id"
                    ),
                    {"briefing_id": briefing_id, "event_id": event_id},
                )
                await connection.execute(
                    text(
                        "DELETE FROM briefings WHERE id = :id AND NOT EXISTS "
                        "(SELECT 1 FROM briefing_items WHERE briefing_id = briefings.id)"
                    ),
                    {"id": briefing_id},
                )
            for table in ("briefing_outbox", "event_search_metadata", "event_sources", "claims"):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE event_id = :id"), {"id": event_id}
                )
            await connection.execute(text("DELETE FROM events WHERE id = :id"), {"id": event_id})
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_briefing_filters_snapshotted_stale_rows_and_keeps_legacy_nulls() -> None:
    """Apply saved event freshness during retries without excluding legacy NULL policy."""
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    suffix, now = uuid.uuid4().hex, datetime.now(UTC)
    gate = GatekeeperResult(
        relevant=True, global_importance=5, personal_relevance=5, importance=6,
        needs_full_extraction=False, category_paths=[], entities=[], topics=[],
    )
    extracted = ExtractorResult(
        compact_summary="Gelişme kısa ve Türkçe biçimde özetlendi.",
        what_changed="Yeni gelişme doğrulandı.", claims=[], entities=[], topics=[],
        uncertainty_markers=[],
    )
    persist_event, persist_briefing, *_rest, has_pending, _correlate = database_persistence(
        sessions
    )

    def item(
        name: str, digest: str, published_at: datetime, freshness_hours: int | None
    ) -> SourceItem:
        return SourceItem(
            source_name=name,
            source_kind=SourceKind.RSS,
            stream=SourceStream.TECH,
            canonical_url=f"https://example.test/{digest}",
            title=f"{digest} adlı özgün gelişme",
            snippet="Fixture only",
            source_published_at=published_at,
            discovered_at=published_at,
            fetched_at=now,
            timestamp_confidence=TimestampConfidence.SOURCE,
            source_freshness_hours=freshness_hours,
            content_hash=digest,
        )

    pending_before = await has_pending()
    stale_id = await persist_event(
        item("Fixture stale", f"stale-{suffix}", now - timedelta(days=2), 1), gate, extracted
    )
    assert await has_pending() is pending_before

    legacy_id = await persist_event(
        item("Fixture legacy", f"legacy-{suffix}", now - timedelta(days=2), None), gate, extracted
    )
    assert await has_pending() is True
    briefing_id: str | None = None
    try:
        await persist_briefing([])
        async with engine.connect() as connection:
            briefing_id = await connection.scalar(
                text("SELECT briefing_id FROM briefing_items WHERE event_id = :id LIMIT 1"),
                {"id": legacy_id},
            )
            pending_ids = set((await connection.scalars(
                text("SELECT event_id FROM briefing_outbox WHERE event_id IN (:stale, :legacy)"),
                {"stale": stale_id, "legacy": legacy_id},
            )).all())
            saved_ids = set((await connection.scalars(
                text("SELECT event_id FROM briefing_items WHERE event_id IN (:stale, :legacy)"),
                {"stale": stale_id, "legacy": legacy_id},
            )).all())
        assert pending_ids == {stale_id}
        assert saved_ids == {legacy_id}
    finally:
        async with engine.begin() as connection:
            if briefing_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM briefing_item_content WHERE briefing_id = :briefing_id "
                        "AND event_id IN (:stale, :legacy)"
                    ),
                    {"briefing_id": briefing_id, "stale": stale_id, "legacy": legacy_id},
                )
                await connection.execute(
                    text(
                        "DELETE FROM briefing_items WHERE briefing_id = :briefing_id "
                        "AND event_id IN (:stale, :legacy)"
                    ),
                    {"briefing_id": briefing_id, "stale": stale_id, "legacy": legacy_id},
                )
                await connection.execute(
                    text(
                        "DELETE FROM briefings WHERE id = :id AND NOT EXISTS "
                        "(SELECT 1 FROM briefing_items WHERE briefing_id = briefings.id)"
                    ),
                    {"id": briefing_id},
                )
            await connection.execute(
                text("DELETE FROM briefing_item_content WHERE event_id IN (:stale, :legacy)"),
                {"stale": stale_id, "legacy": legacy_id},
            )
            await connection.execute(
                text("DELETE FROM briefing_items WHERE event_id IN (:stale, :legacy)"),
                {"stale": stale_id, "legacy": legacy_id},
            )
            for table in ("briefing_outbox", "event_search_metadata", "event_sources", "claims"):
                await connection.execute(
                    text(f"DELETE FROM {table} WHERE event_id IN (:stale, :legacy)"),
                    {"stale": stale_id, "legacy": legacy_id},
                )
            await connection.execute(
                text("DELETE FROM events WHERE id IN (:stale, :legacy)"),
                {"stale": stale_id, "legacy": legacy_id},
            )
        await engine.dispose()
