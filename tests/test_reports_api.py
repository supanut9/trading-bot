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


def test_reports_html_dashboard_is_removed(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        response = client.get("/reports")

        assert response.status_code == 404
    finally:
        teardown_client(session)


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


def test_trades_report_honors_limit_parameter(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        seed_execution_data(session)

        response = client.get("/reports/trades.csv?limit=1")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["side"] == "sell"
    finally:
        teardown_client(session)


def test_backtest_summary_report_exports_csv_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        response = client.get("/reports/backtest-summary.csv")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["status"] in {"completed", "skipped"}
        assert rows[0]["detail"] != ""
    finally:
        teardown_client(session)


def test_audit_csv_export_filters_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_control_result(
            control_type="worker_cycle",
            source="api.control",
            status="completed",
            detail="worker completed",
            settings=settings,
            payload={"channel": "log"},
        )
        AuditService(session=session).record_control_result(
            control_type="notification_delivery",
            source="notification.log",
            status="failed",
            detail="delivery failed",
            settings=settings,
            payload={"channel": "webhook", "related_event_type": "worker_cycle"},
        )
        session.commit()

        response = client.get("/reports/audit.csv?audit_event_type=notification_delivery")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["event_type"] == "notification_delivery"
        assert rows[0]["status"] == "failed"
    finally:
        teardown_client(session)


def test_notification_delivery_csv_export_filters_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_control_result(
            control_type="notification_delivery",
            source="notification.webhook",
            status="failed",
            detail="delivery failed",
            settings=settings,
            payload={
                "channel": "webhook",
                "related_event_type": "worker_cycle",
            },
        )
        AuditService(session=session).record_control_result(
            control_type="notification_delivery",
            source="notification.log",
            status="completed",
            detail="delivery ok",
            settings=settings,
            payload={
                "channel": "log",
                "related_event_type": "backtest",
            },
        )
        session.commit()

        response = client.get("/reports/notification-delivery.csv?notification_status=failed")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["status"] == "failed"
        assert '"channel": "webhook"' in rows[0]["payload_json"]
    finally:
        teardown_client(session)


def test_live_recovery_csv_export_filters_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="review_required",
                mode="live",
                quantity=Decimal("0.001"),
                client_order_id="filtered-order",
                exchange_order_id="789",
                created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
            )
        )
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="submitted",
                mode="live",
                quantity=Decimal("0.001"),
                client_order_id="other-order",
                exchange_order_id="790",
                created_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, 0, tzinfo=UTC),
            )
        )
        AuditService(session=session).record_control_result(
            control_type="live_cancel",
            source="api.control",
            status="completed",
            detail="cancelled",
            settings=settings,
            payload={"client_order_id": "filtered-order"},
        )
        session.commit()
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        response = client.get(
            "/reports/live-recovery.csv?recovery_requires_review=true&recovery_search=filtered-order"
        )

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["client_order_id"] == "filtered-order"
        assert rows[0]["requires_operator_review"] == "true"
    finally:
        teardown_client(session)
