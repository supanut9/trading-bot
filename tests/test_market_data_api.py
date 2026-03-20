from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.domain.strategies.base import Candle
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.candle import CandleRecord
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


def load_strategy_signal(
    session: object,
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
) -> str | None:
    records = session.scalars(
        select(CandleRecord)
        .where(
            CandleRecord.exchange == exchange,
            CandleRecord.symbol == symbol,
            CandleRecord.timeframe == timeframe,
        )
        .order_by(CandleRecord.open_time.asc())
    ).all()
    candles = [
        Candle(
            open_time=record.open_time,
            close_time=record.close_time,
            open_price=Decimal(record.open_price),
            high_price=Decimal(record.high_price),
            low_price=Decimal(record.low_price),
            close_price=Decimal(record.close_price),
            volume=Decimal(record.volume),
        )
        for record in records
    ]
    signal = EmaCrossoverStrategy(fast_period=3, slow_period=5).evaluate(candles)
    return signal.action if signal is not None else None


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


@pytest.mark.parametrize(
    ("scenario_name", "expected_action"),
    [
        ("buy-crossover", "buy"),
        ("sell-crossover", "sell"),
        ("no-action", None),
    ],
)
def test_load_demo_scenario_persists_expected_strategy_shape(
    tmp_path: Path,
    scenario_name: str,
    expected_action: str | None,
) -> None:
    client, session = build_client(tmp_path)
    try:
        response = client.post(f"/market-data/demo-scenarios/{scenario_name}")

        assert response.status_code == 201
        payload = response.json()
        assert payload["scenario"] == scenario_name
        assert payload["exchange"] == "binance"
        assert payload["symbol"] == "BTC/USDT"
        assert payload["timeframe"] == "1h"
        assert payload["candle_count"] == 9
        assert payload["stored_count"] == 9
        assert payload["latest_open_time"] == "2026-01-01T08:00:00Z"
        assert payload["expected_signal_action"] == expected_action

        assert (
            load_strategy_signal(
                session,
                exchange="binance",
                symbol="BTC/USDT",
                timeframe="1h",
            )
            == expected_action
        )
    finally:
        teardown_client(session)


def test_load_demo_scenario_returns_not_found_for_unknown_name(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        response = client.post("/market-data/demo-scenarios/not-a-real-scenario")

        assert response.status_code == 404
        assert "unknown demo scenario" in response.json()["detail"]
    finally:
        teardown_client(session)


def test_loading_same_demo_scenario_is_idempotent_for_candle_count(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        first = client.post("/market-data/demo-scenarios/buy-crossover")
        second = client.post("/market-data/demo-scenarios/buy-crossover")

        assert first.status_code == 201
        assert second.status_code == 201
        rows = session.scalar(select(func.count()).select_from(CandleRecord))
        assert rows == 9
    finally:
        teardown_client(session)


def test_market_data_coverage_reports_insufficient_history(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        session.add_all(
            [
                CandleRecord(
                    exchange="binance",
                    symbol="BTC/USDT",
                    timeframe="1h",
                    open_time=start + timedelta(hours=index),
                    close_time=start + timedelta(hours=index + 1),
                    open_price=Decimal("100000"),
                    high_price=Decimal("100100"),
                    low_price=Decimal("99900"),
                    close_price=Decimal("100050"),
                    volume=Decimal("12.5"),
                )
                for index in range(3)
            ]
        )
        session.commit()

        response = client.get(
            "/market-data/coverage",
            params={
                "strategy_name": "ema_crossover",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "fast_period": 3,
                "slow_period": 5,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["candle_count"] == 3
        assert payload["required_candles"] == 6
        assert payload["additional_candles_needed"] == 3
        assert payload["satisfies_required_candles"] is False
        assert payload["readiness_status"] == "not_ready"
        assert payload["first_open_time"] == "2026-01-01T00:00:00Z"
        assert payload["latest_close_time"] == "2026-01-01T03:00:00Z"
    finally:
        teardown_client(session)


def test_market_data_coverage_accepts_rule_builder_rules_json(tmp_path: Path) -> None:
    client, session = build_client(tmp_path)
    try:
        rules_json = (
            '{"shared_filters":{"logic":"all","conditions":[]},'
            '"buy_rules":{"logic":"all","conditions":[{"indicator":"ema_cross",'
            '"operator":"bullish","fast_period":12,"slow_period":26}]},'
            '"sell_rules":{"logic":"all","conditions":[{"indicator":"ema_cross",'
            '"operator":"bearish","fast_period":12,"slow_period":26}]}}'
        )
        response = client.get(
            "/market-data/coverage",
            params={
                "strategy_name": "rule_builder",
                "rules_json": rules_json,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["required_candles"] == 27
        assert payload["readiness_status"] == "not_ready"
        assert payload["freshness_status"] == "empty"
    finally:
        teardown_client(session)
