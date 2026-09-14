from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.config.settings import Settings
from app.config.sources import SourceCatalog


class _Engine:
    async def dispose(self) -> None:
        return None


def test_startup_reads_yaml_only_for_an_explicit_pending_bootstrap(
    monkeypatch, tmp_path: Path
) -> None:
    needs: Iterator[bool] = iter((True, False))
    bootstraps: list[SourceCatalog] = []

    class Repository:
        def __init__(self, sessions: object) -> None:
            pass

        async def needs_yaml_bootstrap(self) -> bool:
            return next(needs)

        async def bootstrap_yaml(self, seed: SourceCatalog) -> bool:
            bootstraps.append(seed)
            return True

    class OnboardingRepository:
        def __init__(self, sessions: object) -> None:
            pass

        async def scheduler_preference(self) -> None:
            return None

    monkeypatch.setattr(main, "create_engine", lambda settings: _Engine())
    monkeypatch.setattr(main, "create_session_factory", lambda engine: object())
    monkeypatch.setattr(main, "SourceRepository", Repository)
    monkeypatch.setattr(main, "OnboardingRepository", OnboardingRepository)
    fixture = tmp_path / "sources.yaml"
    fixture.write_text("rss: []\nyoutube: []\n", encoding="utf-8")
    first = Settings(managed_sources_bootstrap=True, admin_sources_path=fixture)
    with TestClient(main.create_app(first)):
        pass
    assert len(bootstraps) == 1

    completed = Settings(
        managed_sources_bootstrap=True, admin_sources_path=tmp_path / "missing.yaml"
    )
    with TestClient(main.create_app(completed)):
        pass

    normal_runtime = Settings(admin_sources_path=tmp_path / "also-missing.yaml")
    with TestClient(main.create_app(normal_runtime)):
        pass
    assert len(bootstraps) == 1
