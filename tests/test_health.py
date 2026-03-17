import pytest
from fastapi.testclient import TestClient

from app.main import app, create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_startup_validation_failure_prevents_app_start(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.validate_runtime_startup",
        lambda _settings, _component: (_ for _ in ()).throw(
            RuntimeError("database connectivity check failed")
        ),
    )

    with pytest.raises(RuntimeError, match="database connectivity check failed"):
        with TestClient(create_app()):
            pass
