from pathlib import Path

import yaml

from app.config.sources import load_source_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_rsshub_pilot_is_separate_and_contains_only_approved_routes() -> None:
    catalog = load_source_catalog(PROJECT_ROOT / "config" / "sources.rsshub-pilot.yaml")
    assert len(catalog.rss) == 15
    assert all(
        source.enabled and source.url.startswith("http://rsshub:1200/")
        for source in catalog.rss
    )
    assert all(
        "reddit" not in source.url and "github/trending" not in source.url
        for source in catalog.rss
    )
    world = [source for source in catalog.rss if source.stream.value == "world"]
    assert [source.name for source in world] == ["RSSHub AP Top News"]


def test_rsshub_compose_override_is_disabled_by_default_and_minimal() -> None:
    compose_path = PROJECT_ROOT / "compose.rsshub-pilot.yaml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    rsshub = compose["services"]["rsshub"]
    assert rsshub["profiles"] == ["rsshub-pilot"]
    assert rsshub["environment"] == {"NODE_ENV": "production", "CACHE_TYPE": "memory"}
    assert "ports" not in rsshub
    assert compose["services"]["app"]["profiles"] == ["full-app"]
    runner = compose["services"]["rsshub-pilot-runner"]
    assert runner["profiles"] == ["rsshub-pilot"]
    assert runner["environment"]["SCHEDULER_ENABLED"] == "false"
    assert runner["environment"]["OPENROUTER_API_KEY"] == ""
    assert "redis" not in str(compose).casefold()
    assert "puppeteer" not in str(compose).casefold()
