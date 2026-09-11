from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parents[1]


def test_compose_uses_a_configurable_non_default_postgres_host_port() -> None:
    compose = (PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8")
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert '"${POSTGRES_HOST_PORT:-5433}:5432"' in compose
    assert "POSTGRES_HOST_PORT=5433" in env_example
    assert "localhost:5433/intelligence" in env_example


def test_runtime_build_and_service_images_are_immutable_and_lock_driven() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    development = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(
        (PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8")
    )
    pilot = yaml.safe_load(
        (PROJECT_ROOT / "compose.rsshub-pilot.yaml").read_text(encoding="utf-8")
    )

    assert "python:3.12.11-slim-bookworm@sha256:" in dockerfile
    assert "COPY pyproject.toml uv.lock README.md" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "alembic upgrade head" not in dockerfile
    assert "@sha256:" in development["services"]["db"]["image"]
    assert "@sha256:" in production["services"]["db"]["image"]
    assert "latest" not in pilot["services"]["rsshub"]["image"]
    assert "@sha256:" in pilot["services"]["rsshub"]["image"]


def test_docker_build_context_excludes_secret_and_workspace_material() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert dockerignore.startswith("**\n")
    assert "!uv.lock" in dockerignore
    assert "config/.env*" in dockerignore
    assert "config/**/*secret*" in dockerignore
    assert ".git" not in dockerignore  # deny-by-default already excludes it


def test_rsshub_is_not_in_production_and_cannot_reach_the_database_network() -> None:
    development = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    production = yaml.safe_load(
        (PROJECT_ROOT / "compose.production.yaml").read_text(encoding="utf-8")
    )
    pilot = yaml.safe_load(
        (PROJECT_ROOT / "compose.rsshub-pilot.yaml").read_text(encoding="utf-8")
    )

    assert "rsshub" not in production["services"]
    assert development["networks"]["backend"]["internal"] is True
    assert pilot["services"]["rsshub"]["networks"] == ["rsshub_egress"]
    assert "backend" not in pilot["services"]["rsshub"]["networks"]
    assert set(pilot["services"]["rsshub-pilot-runner"]["networks"]) == {
        "backend",
        "rsshub_egress",
    }


def test_telegram_production_override_mounts_only_read_only_secret_files() -> None:
    telegram = yaml.safe_load(
        (PROJECT_ROOT / "compose.telegram.production.yaml").read_text(encoding="utf-8")
    )
    app = telegram["services"]["app"]

    assert app["environment"] == {
        "TELEGRAM_BOT_TOKEN_FILE": "/run/secrets/telegram_bot_token",
        "TELEGRAM_WEBHOOK_SECRET_FILE": "/run/secrets/telegram_webhook_secret",
    }
    assert all(volume.endswith(":ro") for volume in app["volumes"])
    assert "TELEGRAM_BOT_TOKEN=" not in str(telegram)
    assert "TELEGRAM_WEBHOOK_SECRET=" not in str(telegram)


def test_backup_and_restore_scripts_encrypt_verify_and_require_isolation() -> None:
    backup = (PROJECT_ROOT / "ops/backup-postgres.sh").read_text(encoding="utf-8")
    restore = (PROJECT_ROOT / "ops/restore-postgres.sh").read_text(encoding="utf-8")

    assert "pg_dump" in backup and "--format=custom" in backup
    assert "age --encrypt" in backup
    assert "sha256sum" in backup
    assert "trap cleanup" in backup and "rm -f -- \"$plain\"" in backup
    assert 'test "$RESTORE_CONFIRM_ISOLATED" = "yes"' in restore
    assert "sha256sum --check" in restore
    assert "age --decrypt" in restore
    assert "pg_restore" in restore and "--exit-on-error" in restore
    assert "--clean" not in restore
