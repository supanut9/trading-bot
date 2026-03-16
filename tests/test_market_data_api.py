from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
)
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, object]:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'market_data_api.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session = create_session_factory(settings)()

    def override_get_session() -> object:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    return client, session


def teardown_client(session: object) -> None:
    app.dependency_overrides.clear()
    session.close()


def test_ingest_candles_persists_batch_with_default_market_config(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)

        response = client.post(
            "/market-data/candles",
            json={
                "candles": [
                    {
                        "open_time": start.isoformat(),
                        "close_time": (start + timedelta(hours=1)).isoformat(),
                        "open_price": "100000",
                        "high_price": "100100",
                        "low_price": "99900",
                        "close_price": "100050",
                        "volume": "12.5",
                    },
                    {
                        "open_time": (start + timedelta(hours=1)).isoformat(),
                        "close_time": (start + timedelta(hours=2)).isoformat(),
                        "open_price": "100050",
                        "high_price": "100300",
                        "low_price": "100000",
                        "close_price": "100250",
                        "volume": "9.3",
                    },
                ]
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["exchange"] == "binance"
        assert payload["symbol"] == "BTC/USDT"
        assert payload["timeframe"] == "1h"
        assert payload["stored_count"] == 2
        assert payload["latest_open_time"] == "2026-01-01T01:00:00Z"
    finally:
        teardown_client(session)


def test_ingest_candles_requires_at_least_one_candle(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        response = client.post("/market-data/candles", json={"candles": []})

        assert response.status_code == 422
    finally:
        teardown_client(session)


def test_ingest_candles_normalizes_naive_and_aware_timestamps(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        response = client.post(
            "/market-data/candles",
            json={
                "candles": [
                    {
                        "open_time": "2026-01-01T00:00:00",
                        "close_time": "2026-01-01T01:00:00",
                        "open_price": "100000",
                        "high_price": "100100",
                        "low_price": "99900",
                        "close_price": "100050",
                        "volume": "12.5",
                    },
                    {
                        "open_time": "2026-01-01T01:00:00Z",
                        "close_time": "2026-01-01T02:00:00Z",
                        "open_price": "100050",
                        "high_price": "100300",
                        "low_price": "100000",
                        "close_price": "100250",
                        "volume": "9.3",
                    },
                ]
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["stored_count"] == 2
        assert payload["latest_open_time"] == "2026-01-01T01:00:00Z"
    finally:
        teardown_client(session)
