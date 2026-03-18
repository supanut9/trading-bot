from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.audit_event import AuditEventRecord
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session_factory_dependency,
)
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
    shared_factory = create_session_factory(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session_factory_dependency] = lambda: shared_factory
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
            audit_count = session.scalar(select(func.count()).select_from(AuditEventRecord))
        finally:
            session.close()

        assert trade_count == 1
        assert audit_count == 1
    finally:
        teardown_client()


def test_backtest_control_returns_skipped_when_no_candles_exist(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        response = client.post("/controls/backtest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "skipped"
        assert payload["detail"] == "no_candles"
        assert payload["candle_count"] == 0
        assert payload["required_candles"] == 6

        session = create_session_factory(settings)()
        try:
            event = session.scalars(select(AuditEventRecord)).one()
        finally:
            session.close()

        assert event.event_type == "backtest"
        assert event.status == "skipped"
        assert event.source == "api.control"
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


def test_controls_use_injected_shared_session_factory(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])
        shared_factory = create_session_factory(settings)
        captured: list[object] = []

        def override_session_factory() -> object:
            captured.append(shared_factory)
            return shared_factory

        app.dependency_overrides[get_session_factory_dependency] = override_session_factory

        response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        assert captured == [shared_factory]
    finally:
        teardown_client()


def test_market_sync_control_returns_completed_summary(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        session_factory = create_session_factory(settings)

        class SyncStub:
            def sync_recent_closed_candles(
                self,
                *,
                exchange: str,
                symbol: str,
                timeframe: str,
                limit: int,
            ) -> MarketDataSyncResult:
                assert exchange == settings.exchange_name
                assert symbol == settings.default_symbol
                assert timeframe == settings.default_timeframe
                assert limit == settings.market_data_sync_limit
                session = session_factory()
                try:
                    store_closes(settings, [10, 11, 12])
                finally:
                    session.close()
                return MarketDataSyncResult(
                    fetched_count=3,
                    stored_count=3,
                    latest_open_time=datetime(2026, 1, 1, 2, tzinfo=UTC),
                )

        from app.application.services import operational_control_service as controls_module

        original = controls_module.MarketDataSyncService
        controls_module.MarketDataSyncService = lambda session, client: SyncStub()
        try:
            response = client.post("/controls/market-sync")
        finally:
            controls_module.MarketDataSyncService = original

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "market data sync completed"
        assert payload["fetched_count"] == 3
        assert payload["stored_count"] == 3
        assert payload["latest_open_time"] == "2026-01-01T02:00:00Z"

        session = create_session_factory(settings)()
        try:
            event = session.scalars(select(AuditEventRecord)).one()
        finally:
            session.close()

        assert event.event_type == "market_sync"
        assert event.status == "completed"
        assert event.source == "api.control"
    finally:
        teardown_client()


def test_worker_cycle_control_refuses_live_mode_without_live_executor(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])
        from app.application.services import worker_orchestration_service as worker_module

        original_build_execution = worker_module.build_execution_service
        worker_module.build_execution_service = lambda session, current_settings: type(
            "LiveExecutionStub",
            (),
            {
                "execute": lambda self, request: type(
                    "ExecutionResult",
                    (),
                    {
                        "order": type("Order", (), {"id": 77})(),
                        "trade": None,
                        "position": None,
                    },
                )(),
            },
        )()
        try:
            response = client.post("/controls/worker-cycle")
        finally:
            worker_module.build_execution_service = original_build_execution

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "submitted"
        assert payload["detail"] == "signal submitted to live exchange"
        assert payload["signal_action"] == "buy"
    finally:
        teardown_client()


def test_live_reconcile_control_returns_completed_summary(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        session = create_session_factory(settings)()
        try:
            session.add(
                OrderRecord(
                    exchange="binance",
                    symbol="BTC/USDT",
                    side="buy",
                    order_type="market",
                    status="submitted",
                    mode="live",
                    quantity=Decimal("0.002"),
                    price=Decimal("50000"),
                    client_order_id="live-buy-1",
                    exchange_order_id="123",
                )
            )
            session.commit()
        finally:
            session.close()

        from app.application.services import operational_control_service as controls_module

        original_client_builder = controls_module.build_live_order_exchange_client
        controls_module.build_live_order_exchange_client = lambda current_settings: type(
            "OrderStatusClient",
            (),
            {
                "fetch_order_status": lambda self, **kwargs: type(
                    "OrderStatus",
                    (),
                    {
                        "status": "filled",
                        "client_order_id": kwargs.get("client_order_id"),
                        "exchange_order_id": kwargs.get("exchange_order_id"),
                        "executed_quantity": Decimal("0.002"),
                        "average_fill_price": Decimal("50000"),
                        "response_payload": {},
                    },
                )(),
            },
        )()
        try:
            response = client.post("/controls/live-reconcile")
        finally:
            controls_module.build_live_order_exchange_client = original_client_builder

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["reconciled_count"] == 1
        assert payload["filled_count"] == 1
        assert payload["review_required_count"] == 0
    finally:
        teardown_client()


def test_live_cancel_control_cancels_submitted_live_order(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        session = create_session_factory(settings)()
        try:
            order = OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="submitted",
                mode="live",
                quantity=Decimal("0.002"),
                price=Decimal("50000"),
                client_order_id="live-buy-cancel-1",
                exchange_order_id="789",
            )
            session.add(order)
            session.commit()
            order_id = order.id
        finally:
            session.close()

        from app.application.services import operational_control_service as controls_module

        original_client_builder = controls_module.build_live_order_exchange_client
        controls_module.build_live_order_exchange_client = lambda current_settings: type(
            "CancelOrderClient",
            (),
            {
                "cancel_order": lambda self, **kwargs: type(
                    "CancelResult",
                    (),
                    {
                        "status": "canceled",
                        "client_order_id": kwargs.get("client_order_id"),
                        "exchange_order_id": kwargs.get("exchange_order_id"),
                        "response_payload": {},
                    },
                )(),
            },
        )()
        try:
            response = client.post("/controls/live-cancel", json={"order_id": order_id})
        finally:
            controls_module.build_live_order_exchange_client = original_client_builder

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "live order canceled"
        assert payload["order_status"] == "canceled"
    finally:
        teardown_client()
