from fastapi.testclient import TestClient

from app.main import create_app


async def ready() -> bool:
    return True


async def not_ready() -> bool:
    return False


def test_health_does_not_need_database() -> None:
    with TestClient(create_app(readiness_check=not_ready)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_available_database() -> None:
    with TestClient(create_app(readiness_check=ready)) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_service_unavailable_for_unreachable_database() -> None:
    with TestClient(create_app(readiness_check=not_ready)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
