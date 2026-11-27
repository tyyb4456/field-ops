from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes import health as health_module


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]


def test_readiness_endpoint_when_database_is_available(
    client: TestClient,
    monkeypatch,
) -> None:
    async def database_ready() -> bool:
        return True

    monkeypatch.setattr(
        health_module,
        "verify_database_connection",
        database_ready,
    )

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok"},
    }


def test_readiness_endpoint_when_database_is_unavailable(
    client: TestClient,
    monkeypatch,
) -> None:
    async def database_unavailable() -> bool:
        return False

    monkeypatch.setattr(
        health_module,
        "verify_database_connection",
        database_unavailable,
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable"},
    }
