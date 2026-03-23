import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.application.services.audit_service import AuditService
from app.application.services.backtest_run_history_service import BacktestRunHistoryService
from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.operational_control_service import BacktestControlResult
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


_SYNC_PATCH = (
    "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated"
)


def test_backtest_summary_report_exports_csv_rows(tmp_path: Path) -> None:
    from app.application.services.market_data_sync_service import MarketDataSyncResult

    client, session, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
            response = client.get("/reports/backtest-summary.csv")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["status"] in {"completed", "skipped"}
        assert rows[0]["detail"] != ""
        assert "benchmark_return_pct" in rows[0]
        assert "benchmark_excess_return_pct" in rows[0]
        assert rows[0]["slippage_pct"] != ""
        assert rows[0]["fee_pct"] != ""
        assert rows[0]["spread_pct"] != ""
        assert rows[0]["signal_latency_bars"] != ""
        assert "allow_partial_fills" in rows[0]
        assert "assumption_summary" in rows[0]
    finally:
        teardown_client(session)


def test_backtest_runs_dashboard_returns_recent_runs(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        BacktestRunHistoryService(session=session).record_run(
            source="api.control",
            result=BacktestControlResult(
                status="completed",
                detail="backtest completed",
                notified=False,
                strategy_name="ema_crossover",
                exchange="binance",
                symbol="BTC/USDT",
                timeframe="1h",
                fast_period=12,
                slow_period=26,
                starting_equity_input=Decimal("10000"),
                candle_count=120,
                required_candles=27,
                starting_equity=Decimal("10000"),
                ending_equity=Decimal("10250"),
                realized_pnl=Decimal("250"),
                total_return_pct=Decimal("2.5"),
                benchmark_realized_pnl=Decimal("180"),
                benchmark_return_pct=Decimal("1.8"),
                benchmark_excess_return_pct=Decimal("0.7"),
                max_drawdown_pct=Decimal("1.1"),
                total_trades=4,
                winning_trades=3,
                losing_trades=1,
            ),
        )
        session.commit()

        response = client.get("/reports/backtest-runs")

        assert response.status_code == 200
        payload = response.json()
        assert payload["run_count"] == 1
        assert payload["runs"][0]["source"] == "api.control"
        assert payload["runs"][0]["strategy_name"] == "ema_crossover"
        assert payload["runs"][0]["fast_period"] == 12
        assert payload["runs"][0]["total_return_pct"] == "2.50000000"
        assert payload["runs"][0]["benchmark_return_pct"] == "1.80000000"
        assert payload["runs"][0]["benchmark_excess_return_pct"] == "0.70000000"
        assert "signal_latency_bars=0" in payload["runs"][0]["assumption_summary"]
        assert payload["runs"][0]["allowed_weekdays_utc"] == []
        assert payload["runs"][0]["allowed_hours_utc"] == []
        assert payload["runs"][0]["max_volume_fill_pct"] is None
        assert payload["runs"][0]["allow_partial_fills"] is False
    finally:
        teardown_client(session)


def test_backtest_runs_csv_export_filters_limit(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        history = BacktestRunHistoryService(session=session)
        history.record_run(
            source="api.control",
            result=BacktestControlResult(
                status="completed",
                detail="backtest completed",
                notified=False,
                strategy_name="ema_crossover",
                exchange="binance",
                symbol="BTC/USDT",
                timeframe="1h",
                fast_period=12,
                slow_period=26,
                starting_equity_input=Decimal("10000"),
                candle_count=120,
                required_candles=27,
                starting_equity=Decimal("10000"),
                ending_equity=Decimal("10250"),
                realized_pnl=Decimal("250"),
                total_return_pct=Decimal("2.5"),
                benchmark_realized_pnl=Decimal("180"),
                benchmark_return_pct=Decimal("1.8"),
                benchmark_excess_return_pct=Decimal("0.7"),
                max_drawdown_pct=Decimal("1.1"),
                total_trades=4,
                winning_trades=3,
                losing_trades=1,
                slippage_pct=Decimal("0.001"),
                fee_pct=Decimal("0.001"),
                spread_pct=Decimal("0.002"),
                signal_latency_bars=1,
                assumption_summary=(
                    "slippage_pct=0.001, fee_pct=0.001, spread_pct=0.002, signal_latency_bars=1"
                ),
                allowed_weekdays_utc=(1, 3),
                allowed_hours_utc=(8, 12),
                max_volume_fill_pct=Decimal("0.25"),
                allow_partial_fills=True,
            ),
        )
        history.record_run(
            source="cli.backtest",
            result=BacktestControlResult(
                status="skipped",
                detail="not_enough_candles",
                notified=False,
                strategy_name="rule_builder",
                exchange="binance",
                symbol="ETH/USDT",
                timeframe="4h",
                fast_period=None,
                slow_period=None,
                starting_equity_input=Decimal("15000"),
                candle_count=20,
                required_candles=51,
            ),
        )
        session.commit()

        response = client.get("/reports/backtest-runs.csv?limit=1")

        assert response.status_code == 200
        rows = read_csv_rows(response.text)
        assert len(rows) == 1
        assert rows[0]["source"] == "cli.backtest"
        assert rows[0]["strategy_name"] == "rule_builder"
        assert rows[0]["required_candles"] == "51"
        assert "benchmark_return_pct" in rows[0]
        assert "benchmark_excess_return_pct" in rows[0]
        assert "slippage_pct" in rows[0]
        assert "fee_pct" in rows[0]
        assert "spread_pct" in rows[0]
        assert "signal_latency_bars" in rows[0]
        assert "allowed_weekdays_utc" in rows[0]
        assert "allowed_hours_utc" in rows[0]
        assert "max_volume_fill_pct" in rows[0]
        assert "allow_partial_fills" in rows[0]
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
        assert rows[0]["recovery_state"] == "manual_review_required"
    finally:
        teardown_client(session)


def test_recovery_dashboard_returns_filtered_recovery_data(tmp_path: Path) -> None:
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
        settings.live_trading_halted = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        response = client.get(
            "/reports/recovery?recovery_requires_review=true&recovery_search=filtered-order"
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["live_trading_enabled"] is True
        assert payload["live_trading_halted"] is True
        assert payload["live_safety_status"] == "halted"
        assert payload["summary"]["posture"] == "manual_review_required"
        assert payload["summary"]["dominant_recovery_state"] == "manual_review_required"
        assert payload["summary"]["next_action"] == "inspect_exchange_state"
        assert payload["summary"]["manual_review_required_count"] == 1
        assert payload["unresolved_live_orders"] == 1
        assert payload["recovery_event_count"] == 1
        assert payload["filters"]["requires_review"] is True
        assert payload["filters"]["search"] == "filtered-order"
        assert payload["unresolved_orders"][0]["client_order_id"] == "filtered-order"
        assert payload["unresolved_orders"][0]["requires_operator_review"] is True
        assert payload["unresolved_orders"][0]["recovery_state"] == "manual_review_required"
        assert payload["recovery_events"][0]["event_type"] == "live_cancel"
        assert "client_order_id=filtered-order" in payload["recovery_events"][0]["context"]
    finally:
        teardown_client(session)


def test_notification_dashboard_returns_filtered_delivery_data(tmp_path: Path) -> None:
    client, session, _settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_notification_delivery(
            source="notification.webhook",
            channel="webhook",
            status="failed",
            detail="delivery failed",
            related_event_type="worker_cycle",
            payload={
                "metadata": {
                    "exchange": "binance",
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                },
                "correlation_id": "corr-123",
            },
        )
        AuditService(session=session).record_notification_delivery(
            source="notification.log",
            channel="log",
            status="completed",
            detail="delivery ok",
            related_event_type="backtest",
            payload={
                "metadata": {
                    "exchange": "binance",
                    "symbol": "BTC/USDT",
                    "timeframe": "1h",
                }
            },
        )
        session.commit()

        response = client.get(
            "/reports/notifications?notification_status=failed&notification_channel=webhook"
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["delivery_count"] == 1
        assert payload["failed_count"] == 1
        assert payload["latest_delivery_status"] == "failed"
        assert payload["latest_delivery_channel"] == "webhook"
        assert payload["latest_related_event_type"] == "worker_cycle"
        assert payload["filters"]["status"] == "failed"
        assert payload["filters"]["channel"] == "webhook"
        assert len(payload["events"]) == 1
        assert payload["events"][0]["event_type"] == "notification_delivery"
        assert payload["events"][0]["correlation_id"] == "corr-123"
    finally:
        teardown_client(session)


def test_audit_dashboard_returns_filtered_audit_rows(tmp_path: Path) -> None:
    client, session, settings = build_client(tmp_path)
    try:
        AuditService(session=session).record_control_result(
            control_type="worker_cycle",
            source="api.control",
            status="completed",
            detail="worker completed",
            settings=settings,
            payload={
                "exchange": "binance",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "correlation_id": "corr-789",
            },
        )
        AuditService(session=session).record_control_result(
            control_type="market_sync",
            source="scheduler",
            status="failed",
            detail="sync failed",
            settings=settings,
            payload={"exchange": "binance", "symbol": "ETH/USDT"},
        )
        session.commit()

        response = client.get("/reports/audit?audit_event_type=worker_cycle&audit_search=corr-789")

        assert response.status_code == 200
        payload = response.json()
        assert payload["event_count"] == 1
        assert payload["filters"]["event_type"] == "worker_cycle"
        assert payload["filters"]["search"] == "corr-789"
        assert payload["events"][0]["event_type"] == "worker_cycle"
        assert payload["events"][0]["source"] == "api.control"
        assert payload["events"][0]["correlation_id"] == "corr-789"
    finally:
        teardown_client(session)
