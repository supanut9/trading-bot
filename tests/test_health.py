import pytest
from fastapi.testclient import TestClient

from app.application.services.runtime_startup_service import build_runtime_startup_context
from app.main import app, create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-ID" in response.headers


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


def test_api_allows_frontend_origin_for_browser_ui(monkeypatch) -> None:
    patched_settings = create_app.__globals__["settings"].model_copy(
        update={"frontend_origins": "http://127.0.0.1:3000"}
    )

    monkeypatch.setattr(
        "app.main.settings",
        patched_settings,
    )
    monkeypatch.setattr(
        "app.main.validate_runtime_startup",
        lambda _settings, _component: build_runtime_startup_context(
            patched_settings,
            "api",
        ),
    )

    with TestClient(create_app()) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
