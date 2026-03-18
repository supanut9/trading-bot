import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.application.services.audit_service import AuditService
from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
    get_session_factory_dependency,
)
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, object, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'reports_api.db'}",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        NOTIFICATION_CHANNEL="none",
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    shared_factory = create_session_factory(settings)
    session = shared_factory()

    def override_get_session() -> object:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session_factory_dependency] = lambda: shared_factory
    return TestClient(app), session, settings


def teardown_client(session: object) -> None:
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    session.close()


def read_csv_rows(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(content)))


def seed_execution_data(session: object) -> None:
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


def test_positions_report_exports_csv_rows(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        seed_execution_data(session)

        response = client.get("/reports/positions.csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"] == 'attachment; filename="positions.csv"'
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["symbol"] == "BTC/USDT"
        assert rows[0]["quantity"] == "0.30000000"
        assert rows[0]["realized_pnl"] == "200.00000000"
    finally:
        teardown_client(session)


def test_reports_dashboard_renders_html_snapshot(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        seed_execution_data(session)
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.get("/reports")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "Reporting Deck" in response.text
        assert "Open Positions" in response.text
        assert "Latest Price" in response.text
        assert "Recent Trades" in response.text
        assert "Stale Live Orders" in response.text
        assert "Backtest Snapshot" in response.text
        assert "Session Summary" in response.text
        assert "Performance Summary" in response.text
        assert "Daily Performance" in response.text
        assert "Recent Audit Events" in response.text
        assert "BTC/USDT" in response.text
        assert "Download positions CSV" in response.text
    finally:
        teardown_client(session)


def test_reports_dashboard_renders_stale_live_order_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        order = OrderRecord(
            exchange="binance",
            symbol="BTC/USDT",
            side="buy",
            order_type="market",
            status="submitted",
            mode="live",
            quantity=Decimal("0.001"),
            client_order_id="stale-live-1",
            exchange_order_id="123",
            created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
        )
        session.add(order)
        session.commit()
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"
        settings.stale_live_order_threshold_minutes = 30

        response = client.get("/reports")

        assert response.status_code == 200
        assert "Stale Live Orders" in response.text
        assert f"<td>{order.id}</td>" in response.text
        assert "submitted" in response.text
    finally:
        teardown_client(session)


def test_reports_dashboard_renders_live_recovery_summary(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="submitted",
                mode="live",
                quantity=Decimal("0.001"),
                client_order_id="recovery-live-1",
                exchange_order_id="456",
                created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
            )
        )
        AuditService(session=session).record_control_result(
            control_type="live_reconcile",
            source="job.live_reconcile",
            status="completed",
            detail="live orders reconciled",
            settings=settings,
            payload={"reconciled_count": 1, "filled_count": 0},
        )
        session.commit()
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        response = client.get("/reports")

        assert response.status_code == 200
        assert "Unresolved Live Orders" in response.text
        assert "Recovery Events" in response.text
        assert "Latest recovery event: live_reconcile completed" in response.text
        assert "Download live recovery CSV" in response.text
    finally:
        teardown_client(session)


def test_reports_dashboard_renders_latest_worker_summary(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_control_result(
            control_type="worker_cycle",
            source="api.console",
            status="executed",
            detail="signal executed in paper mode",
            settings=settings,
            payload={
                "signal_action": "buy",
                "client_order_id": "worker-summary-1",
                "notified": False,
            },
        )
        session.commit()

        response = client.get("/reports")

        assert response.status_code == 200
        assert "Latest worker cycle: executed" in response.text
        assert "Latest Worker Status" in response.text
        assert "Worker Signal" in response.text
        assert "worker-summary-1" in response.text
    finally:
        teardown_client(session)


def test_reports_dashboard_renders_performance_summary_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        seed_execution_data(session)
        response = client.get("/reports")

        assert response.status_code == 200
        assert "Performance Summary" in response.text
        assert "paper" in response.text
        assert "Expectancy" in response.text
        assert "Download performance CSV" in response.text
    finally:
        teardown_client(session)


def test_trades_report_applies_limit_and_keeps_recent_first(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        seed_execution_data(session)

        response = client.get("/reports/trades.csv?limit=1")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["side"] == "sell"
        assert rows[0]["price"] == "21000.00000000"
    finally:
        teardown_client(session)


def test_backtest_summary_report_exports_completed_csv(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.get("/reports/backtest-summary.csv")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == (
            'attachment; filename="backtest-summary.csv"'
        )
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["status"] == "completed"
        assert rows[0]["candle_count"] == "9"
        assert rows[0]["total_trades"] == "2"
        assert rows[0]["ending_equity"] == "10000.00000000"
    finally:
        teardown_client(session)


def test_audit_report_exports_recent_events_csv(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_control_result(
            control_type="worker_cycle",
            source="api.control",
            status="executed",
            detail="signal executed in paper mode",
            settings=settings,
            payload={"notified": False},
        )
        AuditService(session=session).record_notification_delivery(
            source="notification",
            channel="log",
            status="sent",
            detail="worker.executed delivery sent",
            related_event_type="worker.executed",
            payload={
                "event_type": "worker.executed",
                "metadata": {
                    "exchange": settings.exchange_name,
                    "symbol": settings.default_symbol,
                    "timeframe": settings.default_timeframe,
                },
            },
        )
        session.commit()

        response = client.get("/reports/audit.csv?limit=1")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == 'attachment; filename="audit.csv"'
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["event_type"] == "notification_delivery"
        assert rows[0]["source"] == "notification"
        assert rows[0]["status"] == "sent"
    finally:
        teardown_client(session)


def test_live_recovery_report_exports_unresolved_orders_with_latest_context(
    tmp_path: Path,
) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="submitted",
                mode="live",
                quantity=Decimal("0.001"),
                client_order_id="recovery-order-1",
                exchange_order_id="456",
                created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
            )
        )
        AuditService(session=session).record_control_result(
            control_type="live_cancel",
            source="api.control",
            status="completed",
            detail="live order canceled",
            settings=settings,
            payload={"order_id": 1},
        )
        session.commit()

        response = client.get("/reports/live-recovery.csv")

        assert response.status_code == 200
        assert response.headers["content-disposition"] == (
            'attachment; filename="live-recovery.csv"'
        )
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["client_order_id"] == "recovery-order-1"
        assert rows[0]["latest_recovery_event_type"] == "live_cancel"
        assert rows[0]["latest_recovery_event_status"] == "completed"
    finally:
        teardown_client(session)


def test_positions_report_does_not_require_backtest_notification_config(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        settings.notification_channel = "webhook"
        settings.notification_webhook_url = None
        seed_execution_data(session)

        response = client.get("/reports/positions.csv")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["symbol"] == "BTC/USDT"
    finally:
        teardown_client(session)
