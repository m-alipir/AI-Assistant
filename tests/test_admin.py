from pathlib import Path

from fastapi.testclient import TestClient

from app.knowledge.search import KnowledgeSearchError
from app.main import create_app


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


def test_search_endpoint_uses_injected_safe_callback_and_dashboard_renders_search() -> None:
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
        dashboard = client.get("/admin")
    assert response.json()["answer_tr"] == "Bir kaynak bulundu."
    assert "Search / Ask" in dashboard.text
    assert "Gmail gövdeleri kullanılmaz" in dashboard.text


def test_search_endpoint_returns_safe_migration_guidance_instead_of_500() -> None:
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))

    async def unavailable(_filters):
        raise KnowledgeSearchError("search_migration_or_schema_error")

    app.state.ask_callback = unavailable
    with TestClient(app) as client:
        response = client.post("/admin/search", json={"question": "NVIDIA hakkında ne oldu?"})

    assert response.status_code == 200
    assert "migration ve veritabanı" in response.json()["answer_tr"]


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


def test_source_toggle_persists(tmp_path: Path):
    path = tmp_path / "sources.yaml"
    path.write_text("sources: []\n")
    app = create_app(readiness_check=lambda: __import__("asyncio").sleep(0, result=True))
    app.state.sources_path = path
    with TestClient(app) as client:
        assert client.post("/admin/sources/a/false").json()["enabled"] is False
    assert "admin_enabled" in path.read_text()


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
    with TestClient(app) as client:
        assert client.get("/admin/config").json()["models"] == {"roles": {}}
        assert client.post("/admin/interests/amd/more").json()["delta"] == 1
        assert client.post("/admin/interests/not%20valid/more").status_code == 422
    assert "admin_overrides" in interests.read_text()


def test_dashboard_renders_setup_banner_without_exposing_key(tmp_path: Path, monkeypatch):
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
        response = client.get("/admin")
    assert response.status_code == 200
    assert "System ready for first real test" in response.text
    assert "OpenRouter: <b" in response.text
    assert "secret-must-not-render" not in response.text


def test_dashboard_renders_safe_last_gmail_counts(tmp_path: Path) -> None:
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
    with TestClient(app) as client:
        response = client.get("/admin")
    assert "Last Gmail sync" in response.text
    assert "fetched: 2" in response.text
    assert "Last YouTube sync" in response.text
    assert "captions: 1" in response.text
    assert "preferred-language captions: 1" in response.text
    assert "yt-dlp caption access: 0" in response.text
    assert "event persistence: 0" in response.text


def test_dashboard_explains_per_run_llm_provider_and_cache_breakdown(tmp_path: Path) -> None:
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
        response = client.get("/admin")
    assert (
        "Provider LLM calls for this run: 0; cache hits (no provider request): 2." in response.text
    )
    assert "briefing_editor" in response.text
    assert "completed_noop means this deployment" not in response.text


def test_dashboard_source_and_model_actions_persist(tmp_path: Path):
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
    app.state.sources_path = sources
    app.state.models_path = models
    app.state.interests_path = interests
    with TestClient(app) as client:
        added = client.post(
            "/admin/ui/sources",
            json={
                "kind": "rss",
                "name": "Test Feed",
                "endpoint": "https://example.test/feed.xml",
                "stream": "tech",
            },
        )
        assert added.status_code == 200
        source_id = added.json()["source_id"]
        assert client.post(f"/admin/sources/{source_id}/true").json()["enabled"] is True
        assert client.post(
            "/admin/ui/models", json={"role": "gatekeeper", "model": "vendor/model"}
        ).json() == {"role": "gatekeeper", "model": "vendor/model"}
        assert client.delete(f"/admin/ui/sources/{source_id}").json() == {"status": "deleted"}
    assert "vendor/model" in models.read_text()
    assert "Test Feed" not in sources.read_text()


def test_youtube_language_add_and_edit_persist_to_yaml(tmp_path: Path) -> None:
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
    with TestClient(app) as client:
        added = client.post(
            "/admin/ui/sources",
            json={
                "kind": "youtube",
                "name": "Turkish Fixture Channel",
                "endpoint": "UCfixture",
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
    assert "language: en" in sources.read_text()


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
