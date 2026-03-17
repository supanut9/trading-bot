from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.audit_event import AuditEventRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session_factory_dependency,
)
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'console_api.db'}",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        NOTIFICATION_CHANNEL="none",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    shared_factory = create_session_factory(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session_factory_dependency] = lambda: shared_factory
    return TestClient(app), settings


def teardown_client() -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def seed_execution_data(settings: Settings) -> None:
    session = create_session_factory(settings)()
    try:
        service = PaperExecutionService(session)
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                quantity=Decimal("0.50000000"),
                price=Decimal("20000"),
                submitted_reason="entry signal",
            )
        )
        service.execute(
            PaperExecutionRequest(
                exchange="binance",
                symbol="BTC/USDT",
                side="sell",
                quantity=Decimal("0.20000000"),
                price=Decimal("21000"),
                submitted_reason="exit signal",
            )
        )
    finally:
        session.close()


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


def test_console_renders_operator_snapshot(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        seed_execution_data(settings)
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.get("/console")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Operator Console" in response.text
        assert "Paper Trading Actions" in response.text
        assert "Run Worker Cycle" in response.text
        assert "Run Backtest" in response.text
        assert "Sync Market Data" in response.text
        assert "Latest Price" in response.text
        assert "Open Positions" in response.text
        assert "Recent Trades" in response.text
        assert "Recent Audit Events" in response.text
        assert "BTC/USDT" in response.text
    finally:
        teardown_client()


def test_console_worker_cycle_action_renders_result_and_persists_trade(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.post("/console/actions/worker-cycle")

        assert response.status_code == 200
        assert "Last Action" in response.text
        assert "Worker Cycle" in response.text
        assert "signal executed in paper mode" in response.text
        assert "Client Order ID" in response.text

        session = create_session_factory(settings)()
        try:
            trade_count = session.scalar(select(func.count()).select_from(TradeRecord))
            audit_events = session.scalars(
                select(AuditEventRecord).order_by(AuditEventRecord.id.desc())
            ).all()
        finally:
            session.close()

        assert trade_count == 1
        assert audit_events[0].event_type == "worker_cycle"
        assert audit_events[0].source == "api.console"
    finally:
        teardown_client()


def test_console_backtest_action_renders_completed_summary(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.post("/console/actions/backtest")

        assert response.status_code == 200
        assert "Backtest" in response.text
        assert "backtest completed" in response.text
        assert "Candle Count" in response.text
        assert "Ending Equity" in response.text
        assert "10000.00000000" in response.text
    finally:
        teardown_client()


def test_console_market_sync_action_renders_summary(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        from app.application.services import operational_control_service as controls_module

        class SyncStub:
            def sync_recent_closed_candles(
                self,
                *,
                exchange: str,
                symbol: str,
                timeframe: str,
                limit: int,
            ):
                assert exchange == settings.exchange_name
                assert symbol == settings.default_symbol
                assert timeframe == settings.default_timeframe
                assert limit == settings.market_data_sync_limit
                store_closes(settings, [10, 11, 12])
                return MarketDataSyncResult(
                    fetched_count=3,
                    stored_count=3,
                    latest_open_time=datetime(2026, 1, 1, 2, tzinfo=UTC),
                )

        original = controls_module.MarketDataSyncService
        controls_module.MarketDataSyncService = lambda session, client: SyncStub()
        try:
            response = client.post("/console/actions/market-sync")
        finally:
            controls_module.MarketDataSyncService = original

        assert response.status_code == 200
        assert "Market Sync" in response.text
        assert "market data sync completed" in response.text
        assert "Fetched Count" in response.text
        assert "Stored Count" in response.text

        session = create_session_factory(settings)()
        try:
            audit_events = session.scalars(
                select(AuditEventRecord).order_by(AuditEventRecord.id.desc())
            ).all()
        finally:
            session.close()

        assert audit_events[0].event_type == "market_sync"
        assert audit_events[0].source == "api.console"
    finally:
        teardown_client()
