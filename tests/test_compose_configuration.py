from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def test_compose_uses_a_configurable_non_default_postgres_host_port() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert '"${POSTGRES_HOST_PORT:-5433}:5432"' in compose
    assert "POSTGRES_HOST_PORT=5433" in env_example
    assert "localhost:5433/intelligence" in env_example
