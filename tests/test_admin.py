from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import app.api.admin as admin
from app.config.onboarding import SchedulerPreference
from app.config.source_repository import (
    EnabledSourceDeleteBlocked,
    ManagedSourceCreate,
    ManagedSourceUpdate,
    SourceAlreadyExists,
    SourceNotFound,
    canonicalize_endpoint,
)
from app.jobs.scheduler import DailyScheduler
from app.knowledge.search import KnowledgeSearchError, SearchEvent
from app.main import create_app


def _source_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "source-1",
        "kind": "rss",
        "name": "Fixture Feed",
        "canonical_endpoint": "https://example.test/feed.xml",
        "stream": "tech",
        "enabled": False,
        "priority": 0,
        "category": None,
        "language": None,
        "freshness_hours": None,
        "health_status": "healthy",
        "last_attempt_at": None,
        "last_success_at": None,
        "consecutive_failures": 0,
        "last_error_category": None,
        "next_retry_at": None,
        "last_successful_strategy": None,
        "detected_language": None,
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


class FakeSourceRepository:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = {str(row["id"]): dict(row) for row in rows or []}
        self.created = 0

    async def list(self) -> list[dict[str, object]]:
        return list(self.rows.values())

    async def get(self, source_id: str) -> dict[str, object] | None:
        row = self.rows.get(source_id)
        return dict(row) if row is not None else None

    async def create(self, source: ManagedSourceCreate) -> dict[str, object]:
        if any(
            row["kind"] == source.kind and row["canonical_endpoint"] == source.endpoint
            for row in self.rows.values()
        ):
            raise SourceAlreadyExists
        self.created += 1
        row = _source_row(
            id=f"created-{self.created}",
            kind=source.kind,
            name=source.name,
            canonical_endpoint=source.endpoint,
            stream=source.stream.value,
            enabled=source.enabled,
            priority=source.priority,
            category=source.category,
            language=source.language,
            freshness_hours=source.freshness_hours,
        )
        self.rows[str(row["id"])] = row
        return dict(row)

    async def update(
        self, source_id: str, update: ManagedSourceUpdate
    ) -> dict[str, object]:
        row = self.rows.get(source_id)
        if row is None:
            raise SourceNotFound
        values: dict[str, Any] = update.model_dump(exclude_unset=True)
        if "endpoint" in values:
            endpoint = canonicalize_endpoint(row["kind"], values.pop("endpoint"))
            if any(
                other_id != source_id
                and other["kind"] == row["kind"]
                and other["canonical_endpoint"] == endpoint
                for other_id, other in self.rows.items()
            ):
                raise SourceAlreadyExists
            values["canonical_endpoint"] = endpoint
        if "stream" in values:
            values["stream"] = values["stream"].value
        if row["kind"] == "rss" and values.get("language") is not None:
            raise ValueError("language preference is supported only for YouTube sources")
        row.update(values)
        return dict(row)

    async def set_enabled(self, source_id: str, enabled: bool) -> bool:
        row = self.rows.get(source_id)
        if row is None:
            return False
        row["enabled"] = enabled
        return True

    async def delete(self, source_id: str) -> None:
        row = self.rows.get(source_id)
        if row is None:
            raise SourceNotFound
        if row["enabled"]:
            raise EnabledSourceDeleteBlocked
        del self.rows[source_id]


class FakeOnboardingRepository:
    def __init__(self) -> None:
        self.preference: SchedulerPreference | None = None

    async def scheduler_preference(self) -> SchedulerPreference | None:
        return self.preference

    async def save_scheduler_preference(self, preference: SchedulerPreference) -> None:
        self.preference = preference


def test_admin_run_callback():
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.run_callback = lambda: "completed"
    with TestClient(app) as client:
        assert client.post("/admin/run-now").json()["status"] == "completed"


def test_admin_awaits_runtime_callback_and_returns_its_counts():
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def runtime() -> dict[str, object]:
        return {"status": "completed", "counts": {"fetched": 1}, "message": "RSS run completed."}

    app.state.run_callback = runtime
    with TestClient(app) as client:
        response = client.post("/admin/run-now")
    assert response.json()["counts"] == {"fetched": 1}
    assert response.json()["message"] == "RSS run completed."


def test_search_endpoint_uses_injected_safe_callback() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def ask(filters):
        assert filters.question == "NVIDIA ne oldu?"
        return {
            "status": "ok",
            "answer_tr": "Bir kaynak bulundu.",
            "events": [],
            "emails": [],
            "model_inferences": [],
            "llm": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
        }

    app.state.ask_callback = ask
    with TestClient(app) as client:
        response = client.post("/admin/search", json={"question": "NVIDIA ne oldu?"})
    assert response.json()["answer_tr"] == "Bir kaynak bulundu."


def test_search_endpoint_returns_safe_migration_guidance_instead_of_500() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def unavailable(_filters):
        raise KnowledgeSearchError("search_migration_or_schema_error")

    app.state.ask_callback = unavailable
    with TestClient(app) as client:
        response = client.post("/admin/search", json={"question": "NVIDIA hakkında ne oldu?"})

    assert response.status_code == 200
    assert "migration ve veritabanı" in response.json()["answer_tr"]


def test_control_center_memory_search_reuses_retrieval_and_ask_callbacks() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def retrieve(filters):
        assert filters.question == "NVIDIA ne oldu?"
        return {
            "status": "ok",
            "answer_tr": "Kaynaklar aşağıda listelenmiştir.",
            "events": [],
            "emails": [],
            "model_inferences": [],
            "llm": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
        }

    async def ask(filters):
        assert filters.question == "NVIDIA ne oldu?"
        return {
            "status": "ok",
            "answer_tr": "Bir kaynak bulundu.",
            "events": [],
            "emails": [],
            "model_inferences": [],
            "llm": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
        }

    app.state.search_callback = retrieve
    app.state.ask_callback = ask
    with TestClient(app) as client:
        page = client.get("/admin/control-center/search")
        retrieved = client.post("/admin/search/retrieve", json={"question": "NVIDIA ne oldu?"})
        answered = client.post("/admin/search", json={"question": "NVIDIA ne oldu?"})
        invalid = client.post("/admin/search/retrieve", json={"question": ""})

    assert page.status_code == 200
    assert "/admin/search/retrieve" in page.text
    assert "/admin/search" in page.text
    assert "innerHTML" not in page.text
    assert "Timestamp unavailable" in page.text
    assert retrieved.json()["answer_tr"] == "Kaynaklar aşağıda listelenmiştir."
    assert answered.json()["answer_tr"] == "Bir kaynak bulundu."
    assert invalid.status_code == 422


def test_control_center_memory_detail_handles_result_missing_and_unavailable() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def detail(event_id):
        if event_id == "saved-event":
            return SearchEvent(
                event_id=event_id,
                title="Saved <script>alert(1)</script> event",
                occurred_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
                source_links=["https://example.test/source", "javascript:alert(1)"],
                verified_facts=["A source-backed fact."],
                stored_inferences=["A stored inference."],
            )
        return None

    app.state.search_event_detail_callback = detail
    with TestClient(app) as client:
        saved = client.get("/admin/control-center/search/saved-event")
        missing = client.get("/admin/control-center/search/missing-event")

    assert saved.status_code == 200
    assert "14.09.2026 15:00" in saved.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in saved.text
    assert "https://example.test/source" in saved.text
    assert "javascript:alert(1)" not in saved.text
    assert missing.status_code == 404

    async def unavailable(_event_id):
        raise KnowledgeSearchError("search_sql_error")

    app.state.search_event_detail_callback = unavailable
    with TestClient(app) as client:
        response = client.get("/admin/control-center/search/saved-event")
    assert response.status_code == 503
    assert "temporarily unavailable" in response.text


def test_control_center_memory_view_does_not_shift_naive_timestamp() -> None:
    aware = SearchEvent(
        event_id="aware",
        title="Aware",
        occurred_at=datetime(2026, 9, 14, 12, tzinfo=UTC),
    )
    naive = SearchEvent(event_id="naive", title="Naive", occurred_at=datetime(2026, 9, 14, 12))

    assert admin._control_center_search_event_view(aware)["occurred_at"] == "14.09.2026 15:00"
    assert admin._control_center_search_event_view(naive)["occurred_at"] is None


def test_briefing_template_uses_fixed_sections_and_safe_feedback_controls() -> None:
    template = (Path(__file__).parents[1] / "app/templates/briefing.html").read_text(
        encoding="utf-8"
    )
    assert "section_order" in template
    assert "sections[section]" in template
    assert "Model" in template
    assert "not_useful" in template
    assert "feedback" in template


def test_manual_run_reports_when_no_runtime_job_is_connected():
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    with TestClient(app) as client:
        assert client.post("/admin/run-now").json()["status"] == "completed_noop"
    assert "No ingestion job" in app.state.last_run_details["message"]


def test_source_endpoints_fail_deterministically_without_database_repository() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    with TestClient(app) as client:
        assert client.get("/admin/sources").status_code == 503
        assert client.post("/admin/sources/a/false").status_code == 503


def test_status_uses_metrics_provider():
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def metrics():
        return {"llm_calls": 2, "llm_cost_usd": 0.3, "recent_briefings": [{"id": "b"}]}

    app.state.metrics_provider = metrics
    with TestClient(app) as client:
        assert client.get("/admin/status").json()["llm_calls"] == 2
        assert client.get("/admin/briefings").json()["items"] == [{"id": "b"}]


def test_config_and_interest_override_use_configured_temp_paths(tmp_path: Path):
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("sources: []\n")
    models.write_text("roles: {}\n")
    interests.write_text("base: {}\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.sources_path, app.state.models_path, app.state.interests_path = (
        sources,
        models,
        interests,
    )
    app.state.source_repository = FakeSourceRepository()
    with TestClient(app) as client:
        config = client.get("/admin/config").json()
        assert config["sources"] == {"items": []}
        assert config["models"] == {"roles": {}}
        assert client.post("/admin/interests/amd/more").json()["delta"] == 1
        assert client.post("/admin/interests/not%20valid/more").status_code == 422
    assert "admin_overrides" in interests.read_text()


def test_control_center_dashboard_is_narrow_and_never_exposes_environment_values(
    tmp_path: Path, monkeypatch
) -> None:
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("rss: []\nyoutube: []\n")
    models.write_text("roles: {}\n")
    interests.write_text("profile: {}\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-must-not-render")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.engine = None
    app.state.sources_path = sources
    app.state.models_path = models
    app.state.interests_path = interests
    with TestClient(app) as client:
        response = client.get("/admin/control-center")
    assert response.status_code == 200
    assert "Control Center" in response.text
    assert "Dashboard" in response.text
    assert "Sources" in response.text
    assert "/admin/onboarding" in response.text
    assert "secret-must-not-render" not in response.text


def test_control_center_dashboard_reports_separate_polling_deployment() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.telegram_enabled = True
    app.state.telegram_mode = "polling"
    with TestClient(app) as client:
        response = client.get("/admin/control-center")
    assert response.status_code == 200
    assert "Telegram" in response.text
    assert "connected" in response.text


def test_control_center_dashboard_shows_safe_operational_summary(
    tmp_path: Path, monkeypatch
) -> None:
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("rss: []\nyoutube: []\n")
    models.write_text("roles: {}\n")
    interests.write_text("profile: {}\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.engine = None
    app.state.sources_path, app.state.models_path, app.state.interests_path = (
        sources,
        models,
        interests,
    )
    app.state.source_repository = FakeSourceRepository(
        [
            _source_row(enabled=True),
            _source_row(
                id="source-2",
                name="Cooling feed",
                health_status="degraded",
                last_error_category="rss_feed_access_error",
                last_attempt_at="2026-09-14T08:00:00+00:00",
                next_retry_at="2026-09-14T08:15:00+00:00",
            ),
        ]
    )
    app.state.last_run = "completed_with_errors"
    app.state.last_run_details = {
        "counts": {
            "gmail": {
                "fetched": 2,
                "muted": 1,
                "action_items": 1,
                "processed": 1,
                "duplicates": 0,
                "failed": 0,
            },
            "youtube": {
                "fetched": 1,
                "stale": 0,
                "duplicates": 0,
                "relevant": 1,
                "processed": 1,
                "captions_available": 1,
                "preferred_language_captions": 1,
                "skipped_no_captions": 0,
                "skipped_no_preferred_language_caption": 0,
                "failed": 0,
                "post_llm_blocked": 0,
                "failure_categories": {
                    "youtube_feed_access_error": 0,
                    "yt_dlp_caption_access_error": 0,
                    "gatekeeper_error": 0,
                    "extractor_error": 0,
                    "event_persistence_error": 0,
                    "briefing_item_error": 0,
                    "processing_error": 0,
                },
                "llm_calls": 2,
            },
        }
    }

    async def details(_request):
        return {
            "migration": "20260914_0026",
            "events": [],
            "interest_rows": [],
            "llm_recent": [],
            "briefings": [
                {"id": "briefing-1", "created_at": "2026-09-14", "rendered": "Safe summary"}
            ],
            "gmail_accounts": [],
            "blocked_youtube": [],
            "scheduled_runs": [],
            "error": None,
        }

    async def metrics():
        return {"llm_calls": 3, "llm_cost_usd": 0.12, "recent_briefings": []}

    monkeypatch.setattr(admin, "_database_details", details)
    app.state.metrics_provider = metrics
    with TestClient(app) as client:
        response = client.get("/admin/control-center")
        operations = client.get("/admin")
    assert "completed_with_errors" in response.text
    assert "Cooling feed" in response.text
    assert "rss_feed_access_error" in response.text
    assert "Safe summary" in response.text
    assert "Provider calls" in response.text
    assert "Gmail" in response.text
    assert "Last YouTube sync" not in response.text
    assert "Manual Run" not in response.text
    assert "Last Gmail sync" in operations.text
    assert "Last YouTube sync" in operations.text
    assert "Manual Run" in operations.text


def test_control_center_briefings_show_saved_and_incomplete_history(
    monkeypatch
) -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def history(_request):
        return {
            "items": [
                {
                    "id": "saved-briefing",
                    "created_at": "14.09.2026 15:00",
                    "rendered": "Saved briefing content. <script>alert(1)</script>",
                    "status": "Saved",
                    "summary": "Saved briefing content.",
                },
                {
                    "id": "incomplete-briefing",
                    "created_at": None,
                    "rendered": "",
                    "status": "Incomplete",
                    "summary": "Generated content is unavailable for this saved record.",
                },
            ],
            "error": None,
        }

    async def detail(_request, briefing_id):
        for item in (await history(None))["items"]:
            if item["id"] == briefing_id:
                return {"item": item, "error": None}
        return {"item": None, "error": None}

    monkeypatch.setattr(admin, "_control_center_briefing_history", history)
    monkeypatch.setattr(admin, "_control_center_briefing", detail)
    with TestClient(app) as client:
        response = client.get("/admin/control-center/briefings")
        detail_response = client.get("/admin/control-center/briefings/saved-briefing")
        missing_response = client.get("/admin/control-center/briefings/missing")

    assert response.status_code == 200
    assert "14.09.2026 15:00" in response.text
    assert "Timestamp unavailable" in response.text
    assert "Saved" in response.text
    assert "Incomplete" in response.text
    assert "/admin/control-center/briefings/saved-briefing" in response.text
    assert detail_response.status_code == 200
    assert "Saved briefing content." in detail_response.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail_response.text
    assert "<script>alert(1)</script>" not in detail_response.text
    assert missing_response.status_code == 404


def test_control_center_briefings_handle_empty_and_unavailable_history(monkeypatch) -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def empty_history(_request):
        return {"items": [], "error": None}

    monkeypatch.setattr(admin, "_control_center_briefing_history", empty_history)
    with TestClient(app) as client:
        empty = client.get("/admin/control-center/briefings")

    async def unavailable_history(_request):
        return {"items": [], "error": "unavailable"}

    monkeypatch.setattr(admin, "_control_center_briefing_history", unavailable_history)

    async def unavailable_detail(_request, _briefing_id):
        return {"item": None, "error": "unavailable"}

    monkeypatch.setattr(admin, "_control_center_briefing", unavailable_detail)
    with TestClient(app) as client:
        unavailable = client.get("/admin/control-center/briefings")
        unavailable_detail_response = client.get("/admin/control-center/briefings/saved")

    assert "No saved briefings yet." in empty.text
    assert unavailable.status_code == 503
    assert "Briefing history is temporarily unavailable." in unavailable.text
    assert unavailable_detail_response.status_code == 503


def test_control_center_briefing_view_converts_only_timezone_aware_timestamps() -> None:
    saved = admin._control_center_briefing_view(
        {
            "id": "saved",
            "created_at": datetime(2026, 9, 14, 12, tzinfo=UTC),
            "rendered": "Saved content.",
        }
    )
    naive = admin._control_center_briefing_view(
        {"id": "naive", "created_at": datetime(2026, 9, 14, 12), "rendered": "Saved."}
    )

    assert saved["created_at"] == "14.09.2026 15:00"
    assert naive["created_at"] is None


def test_onboarding_is_optional_and_reuses_safe_admin_entry_points(tmp_path: Path) -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.sources_path = tmp_path / "sources.yaml"
    app.state.models_path = tmp_path / "models.yaml"
    app.state.interests_path = tmp_path / "interests.yaml"
    app.state.interests_path.write_text("profile: {}\n")
    app.state.source_repository = FakeSourceRepository([_source_row(enabled=True)])
    app.state.onboarding_repository = FakeOnboardingRepository()
    app.state.gmail_configured = True
    app.state.gmail_encryption_ready = True
    app.state.scheduler = DailyScheduler(
        False, "08:00", "Europe/Istanbul", _unused_run, _unused_claim
    )

    with TestClient(app) as client:
        page = client.get("/admin/onboarding")
        assert page.status_code == 200
        assert "First-run setup" in page.text
        assert "/admin/sources/ui" in page.text
        assert "/admin/gmail/connect" in page.text
        assert "/admin/interests/" in page.text
        assert "/admin/onboarding/scheduler" in page.text
        assert client.post(
            "/admin/onboarding/scheduler", json={"enabled": True, "daily_time": "07:30"}
        ).json() == {"enabled": True, "daily_time": "07:30"}
        assert client.post(
            "/admin/onboarding/scheduler", json={"enabled": True, "daily_time": "bad"}
        ).status_code == 422
    assert app.state.onboarding_repository.preference == SchedulerPreference(
        enabled=True, daily_time="07:30"
    )


def test_control_center_scheduler_reuses_persisted_onboarding_preference() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    repository = FakeOnboardingRepository()
    repository.preference = SchedulerPreference(enabled=True, daily_time="07:30")
    scheduler = DailyScheduler(True, "07:30", "Europe/Istanbul", _unused_run, _unused_claim)
    scheduler.state.next_run = "2026-09-15T07:30:00+03:00"
    scheduler.state.last_run = "completed"
    scheduler.state.last_summary = "processed=2"
    app.state.onboarding_repository = repository
    app.state.scheduler = scheduler

    with TestClient(app) as client:
        page = client.get("/admin/control-center/scheduler")
        saved = client.post(
            "/admin/onboarding/scheduler", json={"enabled": False, "daily_time": "09:15"}
        )
        scheduler.state.running = True
        busy = client.post(
            "/admin/onboarding/scheduler", json={"enabled": True, "daily_time": "10:00"}
        )
        scheduler.state.running = False
        invalid = client.post(
            "/admin/onboarding/scheduler", json={"enabled": True, "daily_time": "09:15:30"}
        )

    assert page.status_code == 200
    assert "2026-09-15T07:30:00+03:00" in page.text
    assert "Persisted preference: enabled at 07:30." in page.text
    assert "/admin/onboarding/scheduler" in page.text
    assert "innerHTML" not in page.text
    assert saved.json() == {"enabled": False, "daily_time": "09:15"}
    assert busy.status_code == 409
    assert invalid.status_code == 422
    assert repository.preference == SchedulerPreference(enabled=False, daily_time="09:15")


def test_control_center_scheduler_handles_unavailable_configuration() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    with TestClient(app) as client:
        response = client.get("/admin/control-center/scheduler")

    assert response.status_code == 200
    assert "Schedule settings are temporarily unavailable." in response.text


async def _unused_run() -> dict[str, object]:
    raise AssertionError("onboarding must not run ingestion")


async def _unused_claim(_: object) -> bool:
    raise AssertionError("onboarding must not claim a scheduled day")


def test_control_center_dashboard_omits_model_and_budget_controls(tmp_path: Path) -> None:
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("rss: []\nyoutube: []\n")
    models.write_text("roles: {}\n")
    interests.write_text("profile: {}\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.engine = None
    app.state.sources_path, app.state.models_path, app.state.interests_path = (
        sources,
        models,
        interests,
    )
    app.state.last_run_details = {
        "counts": {
            "llm_calls": 0,
            "llm_cache_hits": 2,
            "llm_breakdown_by_flow": {
                "rss": {
                    "provider_calls": 0,
                    "cache_hits": 2,
                    "by_role": {"gatekeeper": {"provider_calls": 0, "cache_hits": 2}},
                },
                "gmail": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
                "youtube": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
                "briefing_editor": {"provider_calls": 0, "cache_hits": 0, "by_role": {}},
            },
        }
    }
    with TestClient(app) as client:
        response = client.get("/admin/control-center")
        operations = client.get("/admin")
    assert "Model Configuration" not in response.text
    assert "Provider LLM calls" not in response.text
    assert "briefing_editor" not in response.text
    assert "Model Configuration" in operations.text
    assert "Provider LLM calls for this run: 0" in operations.text


def test_sources_page_uses_admin_api_entry_points_and_escapes_source_content() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.source_repository = FakeSourceRepository(
        [_source_row(name="<script>alert(1)</script>", enabled=True)]
    )

    with TestClient(app) as client:
        response = client.get("/admin/sources/ui")

    assert response.status_code == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    assert "/admin/sources/" in response.text
    assert "/admin/source-packs/" in response.text
    assert "/admin/opml/" in response.text
    assert "/admin/csv/" in response.text
    assert '"bulk-urls"' not in response.text
    assert "textContent" in response.text


def test_admin_source_crud_uses_repository_and_never_mutates_yaml(tmp_path: Path) -> None:
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("bootstrap-only: unchanged\n")
    models.write_text("roles: {}\n")
    interests.write_text("profile: {}\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.engine = None
    app.state.sources_path = sources
    app.state.models_path = models
    app.state.interests_path = interests
    repository = FakeSourceRepository()
    app.state.source_repository = repository
    with TestClient(app) as client:
        rejected = client.post(
            "/admin/ui/sources",
            json={
                "kind": "rss",
                "name": "Credential-bearing Feed",
                "endpoint": "https://operator:secret@example.test/feed.xml",
                "stream": "tech",
            },
        )
        assert rejected.status_code == 422
        added = client.post(
            "/admin/sources",
            json={
                "kind": "rss",
                "name": "Test Feed",
                "endpoint": "HTTPS://Example.Test:443/feed.xml#ignored",
                "stream": "tech",
            },
        )
        assert added.status_code == 201
        source_id = added.json()["id"]
        assert added.json()["endpoint"] == "https://example.test/feed.xml"
        assert client.get("/admin/sources").json()["items"][0]["id"] == source_id
        assert client.get(f"/admin/sources/{source_id}").json()["name"] == "Test Feed"
        updated = client.patch(
            f"/admin/sources/{source_id}",
            json={"name": "Updated Feed", "priority": 20, "freshness_hours": 24},
        )
        assert updated.json()["name"] == "Updated Feed"
        assert updated.json()["priority"] == 20
        assert updated.json()["freshness_hours"] == 24
        assert client.post(f"/admin/sources/{source_id}/true").json()["enabled"] is True
        assert client.delete(f"/admin/sources/{source_id}").status_code == 409
        assert client.post(f"/admin/sources/{source_id}/false").json()["enabled"] is False
        assert client.delete(f"/admin/sources/{source_id}").json() == {"status": "deleted"}
        assert client.get(f"/admin/sources/{source_id}").status_code == 404
        assert client.post(
            "/admin/ui/models", json={"role": "gatekeeper", "model": "vendor/model"}
        ).json() == {"role": "gatekeeper", "model": "vendor/model"}
    assert "vendor/model" in models.read_text()
    assert sources.read_text() == "bootstrap-only: unchanged\n"


def test_admin_source_failures_map_to_deterministic_http_errors() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.source_repository = FakeSourceRepository()
    with TestClient(app) as client:
        first = client.post(
            "/admin/sources",
            json={
                "kind": "rss",
                "name": "First",
                "endpoint": "https://example.test/first.xml",
            },
        )
        first_id = first.json()["id"]
        duplicate = client.post(
            "/admin/sources",
            json={
                "kind": "rss",
                "name": "Duplicate",
                "endpoint": "https://EXAMPLE.test:443/first.xml#fragment",
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "source endpoint is already managed"

        assert client.post(
            "/admin/sources",
            json={"kind": "rss", "name": "Invalid", "endpoint": "not-a-feed-url"},
        ).status_code == 422
        invalid_update = client.patch(
            f"/admin/sources/{first_id}", json={"endpoint": "not-a-feed-url"}
        )
        assert invalid_update.status_code == 422
        assert "absolute HTTP(S) URL" in invalid_update.json()["detail"]
        assert client.patch(
            f"/admin/sources/{first_id}", json={"language": "en"}
        ).status_code == 422

        missing = "missing-source"
        assert client.get(f"/admin/sources/{missing}").status_code == 404
        assert client.patch(
            f"/admin/sources/{missing}", json={"name": "Missing"}
        ).status_code == 404
        assert client.post(f"/admin/sources/{missing}/true").status_code == 404
        assert client.delete(f"/admin/sources/{missing}").status_code == 404


def test_legacy_admin_source_actions_use_repository_without_yaml_writes(tmp_path: Path) -> None:
    sources, models, interests = (
        tmp_path / "sources.yaml",
        tmp_path / "models.yaml",
        tmp_path / "interests.yaml",
    )
    sources.write_text("bootstrap-only: unchanged\n")
    models.write_text("roles: {}\n")
    interests.write_text("profile: {}\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.engine = None
    app.state.sources_path, app.state.models_path, app.state.interests_path = (
        sources,
        models,
        interests,
    )
    app.state.source_repository = FakeSourceRepository()
    with TestClient(app) as client:
        added = client.post(
            "/admin/ui/sources",
            json={
                "kind": "youtube",
                "name": "Turkish Fixture Channel",
                "endpoint": "UCVBX2n_5egE9XuJL8NUS0Xg",
                "stream": "tech",
                "language": "tr",
            },
        )
        assert added.status_code == 200
        source_id = added.json()["source_id"]
        changed = client.post(f"/admin/ui/sources/{source_id}/language", json={"language": "en"})
        assert changed.json() == {"source_id": source_id, "language": "en"}
        assert (
            client.post(
                f"/admin/ui/sources/{source_id}/language", json={"language": "de"}
            ).status_code
            == 422
        )
        assert client.delete(f"/admin/ui/sources/{source_id}").json() == {"status": "deleted"}
    assert sources.read_text() == "bootstrap-only: unchanged\n"


def test_blocked_youtube_retry_endpoint_allows_only_one_claimed_attempt() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    attempts = 0

    async def retry(content_hash: str) -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        return {"status": "retry_completed" if attempts == 1 else "retry_not_available"}

    app.state.retry_blocked_youtube_callback = retry
    with TestClient(app) as client:
        first = client.post(f"/admin/youtube/blocked/{'a' * 64}/retry")
        second = client.post(f"/admin/youtube/blocked/{'a' * 64}/retry")

    assert first.json()["status"] == "retry_completed"
    assert second.status_code == 409


def test_briefing_template_marks_persisted_feedback_and_never_calls_llm() -> None:
    template = (Path(__file__).parents[1] / "app" / "templates" / "briefing.html").read_text(
        encoding="utf-8"
    )

    assert "data-action=\"more\"" in template
    assert "classList.toggle('selected'" in template
    assert "görüntülemek yeni LLM çağrısı yapmaz" in template
    assert "Kaynak/orijinal metin" in template


def test_blocked_rss_retry_endpoint_uses_the_same_safe_single_claim_contract() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    attempts = 0

    async def retry(content_hash: str) -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        return {"status": "retry_completed" if attempts == 1 else "retry_not_available"}

    app.state.retry_blocked_rss_callback = retry
    with TestClient(app) as client:
        first = client.post(f"/admin/rss/blocked/{'b' * 64}/retry")
        second = client.post(f"/admin/rss/blocked/{'b' * 64}/retry")

    assert first.json()["status"] == "retry_completed"
    assert second.status_code == 409
