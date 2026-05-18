from __future__ import annotations

import app.api.v1.health as health_module


def test_health_reports_service_metadata(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "content-factory"
    assert "artifact_root" in payload


def test_readiness_reports_ready_when_database_is_available(client) -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "content-factory",
        "database": "ok",
    }


def test_readiness_returns_503_when_database_is_unavailable(client, monkeypatch) -> None:
    class _BrokenConnection:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, exc_type, exc, tb):
            return None

    class _BrokenEngine:
        def connect(self):
            return _BrokenConnection()

    monkeypatch.setattr(health_module, "get_engine", lambda: _BrokenEngine())

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Service not ready"
