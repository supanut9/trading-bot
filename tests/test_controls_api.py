from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import create_engine_from_settings, create_session_factory
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'controls_api.db'}",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        NOTIFICATION_CHANNEL="none",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), settings


def teardown_client() -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def store_closes(settings: Settings, closes: list[int]) -> None:
    session = create_session_factory(settings)()
    try:
        service = MarketDataService(session)
        start = datetime(2026, 1, 1, tzinfo=UTC)
        candles = []
        for index, close in enumerate(closes):
            open_time = start + timedelta(hours=index)
            candles.append(
                CandleInput(
                    open_time=open_time,
                    close_time=open_time + timedelta(hours=1),
                    open_price=Decimal(close),
                    high_price=Decimal(close),
                    low_price=Decimal(close),
                    close_price=Decimal(close),
                    volume=Decimal("1"),
                )
            )

        service.store_candles(
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            timeframe=settings.default_timeframe,
            candles=candles,
        )
    finally:
        session.close()


def test_worker_cycle_control_executes_and_persists_trade(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "executed"
        assert payload["signal_action"] == "buy"
        assert payload["notified"] is False

        session = create_session_factory(settings)()
        try:
            trade_count = session.scalar(select(func.count()).select_from(TradeRecord))
        finally:
            session.close()

        assert trade_count == 1
    finally:
        teardown_client()


def test_backtest_control_returns_skipped_when_no_candles_exist(tmp_path: Path) -> None:
    client, _settings = build_client(tmp_path)
    try:
        response = client.post("/controls/backtest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "skipped"
        assert payload["detail"] == "no_candles"
        assert payload["candle_count"] == 0
        assert payload["required_candles"] == 6
    finally:
        teardown_client()


def test_backtest_control_returns_summary_for_completed_run(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.post("/controls/backtest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "backtest completed"
        assert payload["candle_count"] == 9
        assert payload["required_candles"] == 6
        assert payload["total_trades"] == 2
        assert payload["ending_equity"] == "10000.00000000"
    finally:
        teardown_client()
