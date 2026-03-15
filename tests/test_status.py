from fastapi.testclient import TestClient

from app.main import app


def test_status_endpoint_returns_bootstrap_configuration() -> None:
    client = TestClient(app)

    response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["app"] == "trading-bot"
    assert payload["paper_trading"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["database_status"] in {"available", "unavailable"}
