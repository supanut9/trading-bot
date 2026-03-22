from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.application.services.market_data_service import CandleInput, MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.audit_event import AuditEventRecord
from app.infrastructure.database.models.backtest_run import BacktestRunRecord
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.models.runtime_control import RuntimeControlRecord
from app.infrastructure.database.models.trade import TradeRecord
from app.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
    get_session,
    get_session_factory_dependency,
)
from app.main import app


def build_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'controls_api.db'}",
        STRATEGY_FAST_PERIOD=3,
        STRATEGY_SLOW_PERIOD=5,
        MARKET_DATA_SYNC_ENABLED=False,
        NOTIFICATION_CHANNEL="none",
        STRATEGY_ADX_FILTER_ENABLED=False,
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    shared_factory = create_session_factory(settings)

    def override_get_session():
        session = shared_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = override_get_session
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


def store_market_closes(
    settings: Settings,
    *,
    symbol: str,
    timeframe: str,
    closes: list[int],
) -> None:
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
            symbol=symbol,
            timeframe=timeframe,
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


_SYNC_PATCH = (
    "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated"
)


def test_backtest_control_returns_skipped_when_no_candles_exist(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
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

        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
            response = client.post("/controls/backtest")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "backtest completed"
        assert payload["candle_count"] == 9
        assert payload["required_candles"] == 6
        assert payload["total_trades"] == 2
        assert Decimal(payload["ending_equity"]) <= Decimal("10000")
        assert payload["total_fees_paid"] is not None
        assert payload["slippage_pct"] is not None
        assert payload["fee_pct"] is not None
        assert payload["strategy_name"] == "ema_crossover"
        assert payload["symbol"] == settings.default_symbol
        assert payload["timeframe"] == settings.default_timeframe
        session = create_session_factory(settings)()
        try:
            run_count = session.execute(
                select(func.count()).select_from(BacktestRunRecord)
            ).scalar_one()
        finally:
            session.close()
        assert run_count == 1
    finally:
        teardown_client()


def test_backtest_control_accepts_explicit_run_options(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        session = create_session_factory(settings)()
        try:
            start = datetime(2026, 1, 1, tzinfo=UTC)
            MarketDataService(session).store_candles(
                exchange=settings.exchange_name,
                symbol="ETH/USDT",
                timeframe="4h",
                candles=[
                    CandleInput(
                        open_time=start + timedelta(hours=index * 4),
                        close_time=start + timedelta(hours=(index * 4) + 4),
                        open_price=Decimal(close),
                        high_price=Decimal(close),
                        low_price=Decimal(close),
                        close_price=Decimal(close),
                        volume=Decimal("1"),
                    )
                    for index, close in enumerate([10, 10, 10, 10, 10, 9, 9, 9, 20])
                ],
            )
        finally:
            session.close()

        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
            response = client.post(
                "/controls/backtest",
                json={
                    "strategy_name": "ema_crossover",
                    "symbol": "ETH/USDT",
                    "timeframe": "4h",
                    "fast_period": 3,
                    "slow_period": 5,
                    "starting_equity": "15000",
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["symbol"] == "ETH/USDT"
        assert payload["timeframe"] == "4h"
        assert payload["fast_period"] == 3
        assert payload["slow_period"] == 5
        assert payload["starting_equity_input"] == "15000.00000000"
        assert payload["starting_equity"] == "15000.00000000"
    finally:
        teardown_client()


def test_live_readiness_control_returns_report(monkeypatch, tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:

        class FakeLiveReadinessService:
            def __init__(self, _session, _settings) -> None:
                pass

            def build_report(self):
                from app.application.services.live_readiness_service import (
                    LiveReadinessCheck,
                    LiveReadinessReport,
                )

                return LiveReadinessReport(
                    status="blocked",
                    ready=False,
                    checks=[
                        LiveReadinessCheck(
                            name="qualification",
                            passed=False,
                            severity="blocking",
                            detail="strategy qualification gates are not all passing",
                        )
                    ],
                    blocking_reasons=["strategy qualification gates are not all passing"],
                )

        monkeypatch.setattr(
            "app.application.services.operational_control_service.LiveReadinessService",
            FakeLiveReadinessService,
        )

        response = client.get("/controls/live-readiness")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "live readiness evaluated"
        assert payload["ready"] is False
        assert payload["blocking_reasons"] == ["strategy qualification gates are not all passing"]
        assert payload["checks"][0]["name"] == "qualification"
    finally:
        teardown_client()


def test_backtest_control_accepts_rule_builder_options(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        with patch(_SYNC_PATCH, return_value=MarketDataSyncResult(0, 0, None)):
            response = client.post(
                "/controls/backtest",
                json={
                    "strategy_name": "rule_builder",
                    "symbol": settings.default_symbol,
                    "timeframe": settings.default_timeframe,
                    "starting_equity": "100",
                    "rules": {
                        "shared_filters": {"logic": "all", "conditions": []},
                        "buy_rules": {
                            "logic": "all",
                            "conditions": [
                                {
                                    "indicator": "ema_cross",
                                    "operator": "bullish",
                                    "fast_period": 3,
                                    "slow_period": 5,
                                }
                            ],
                        },
                        "sell_rules": {
                            "logic": "all",
                            "conditions": [
                                {
                                    "indicator": "ema_cross",
                                    "operator": "bearish",
                                    "fast_period": 3,
                                    "slow_period": 5,
                                }
                            ],
                        },
                    },
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["strategy_name"] == "rule_builder"
        assert payload["required_candles"] == 6
        assert payload["fast_period"] is None
        assert payload["slow_period"] is None
        assert payload["rules"]["buy_rules"]["conditions"][0]["indicator"] == "ema_cross"
    finally:
        teardown_client()


def test_backtest_control_returns_failed_for_invalid_period_selection(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        response = client.post(
            "/controls/backtest",
            json={
                "fast_period": 5,
                "slow_period": 5,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "failed"
        assert payload["detail"] == "fast period must be smaller than slow period"
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


def test_operator_config_control_returns_current_defaults(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        response = client.get("/controls/operator-config")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["strategy_name"] == "ema_crossover"
        assert payload["symbol"] == settings.default_symbol
        assert payload["timeframe"] == settings.default_timeframe
        assert payload["trading_mode"] == "SPOT"
        assert payload["source"] == "settings"
    finally:
        teardown_client()


def test_operator_config_control_persists_runtime_defaults(tmp_path: Path) -> None:
    client, _settings = build_client(tmp_path)
    try:
        response = client.post(
            "/controls/operator-config",
            json={
                "strategy_name": "ema_crossover",
                "symbol": "ETH/USDT",
                "timeframe": "4h",
                "fast_period": 3,
                "slow_period": 5,
                "trading_mode": "FUTURES",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "operator runtime config updated"
        assert payload["symbol"] == "ETH/USDT"
        assert payload["timeframe"] == "4h"
        assert payload["trading_mode"] == "FUTURES"
        assert payload["source"] == "runtime_config"
        assert payload["changed"] is True
    finally:
        teardown_client()


def test_worker_cycle_control_uses_runtime_operator_config(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        client.post(
            "/controls/operator-config",
            json={
                "strategy_name": "ema_crossover",
                "symbol": "ETH/USDT",
                "timeframe": "4h",
                "fast_period": 3,
                "slow_period": 5,
                "trading_mode": "SPOT",
            },
        )
        store_market_closes(
            settings,
            symbol="ETH/USDT",
            timeframe="4h",
            closes=[10, 10, 10, 10, 10, 9, 9, 9, 20],
        )

        response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "executed"

        session = create_session_factory(settings)()
        try:
            order = session.scalars(select(OrderRecord).order_by(OrderRecord.id.desc())).first()
        finally:
            session.close()

        assert order is not None
        assert order.symbol == "ETH/USDT"
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
                backfill: bool = False,
            ) -> MarketDataSyncResult:
                assert exchange == settings.exchange_name
                assert symbol == settings.default_symbol
                assert timeframe == settings.default_timeframe
                assert limit == settings.market_data_sync_limit
                assert backfill is False
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
        assert payload["limit"] == settings.market_data_sync_limit
        assert payload["backfill"] is False
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


def test_market_sync_control_uses_runtime_operator_config(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        client.post(
            "/controls/operator-config",
            json={
                "strategy_name": "ema_crossover",
                "symbol": "ETH/USDT",
                "timeframe": "4h",
                "fast_period": 3,
                "slow_period": 5,
            },
        )
        session_factory = create_session_factory(settings)

        class SyncStub:
            def sync_recent_closed_candles(
                self,
                *,
                exchange: str,
                symbol: str,
                timeframe: str,
                limit: int,
                backfill: bool = False,
            ) -> MarketDataSyncResult:
                assert exchange == settings.exchange_name
                assert symbol == "ETH/USDT"
                assert timeframe == "4h"
                assert limit == settings.market_data_sync_limit
                assert backfill is False
                session = session_factory()
                try:
                    store_market_closes(
                        settings,
                        symbol="ETH/USDT",
                        timeframe="4h",
                        closes=[10, 11, 12],
                    )
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
        assert payload["symbol"] == "ETH/USDT"
        assert payload["timeframe"] == "4h"
    finally:
        teardown_client()


def test_market_sync_control_accepts_explicit_market_selection(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        client.post(
            "/controls/operator-config",
            json={
                "strategy_name": "ema_crossover",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "fast_period": 3,
                "slow_period": 5,
                "trading_mode": "SPOT",
            },
        )
        session_factory = create_session_factory(settings)

        class SyncStub:
            def sync_recent_closed_candles(
                self,
                *,
                exchange: str,
                symbol: str,
                timeframe: str,
                limit: int,
                backfill: bool = False,
            ) -> MarketDataSyncResult:
                assert exchange == settings.exchange_name
                assert symbol == "SOL/USDT"
                assert timeframe == "15m"
                assert limit == 250
                assert backfill is True
                session = session_factory()
                try:
                    store_market_closes(
                        settings,
                        symbol="SOL/USDT",
                        timeframe="15m",
                        closes=[100, 101, 102],
                    )
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
            response = client.post(
                "/controls/market-sync",
                json={
                    "symbol": "SOL/USDT",
                    "timeframe": "15m",
                    "limit": 250,
                    "backfill": True,
                },
            )
        finally:
            controls_module.MarketDataSyncService = original

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "market data backfill completed"
        assert payload["symbol"] == "SOL/USDT"
        assert payload["timeframe"] == "15m"
        assert payload["limit"] == 250
        assert payload["backfill"] is True
    finally:
        teardown_client()


def test_market_sync_control_accepts_backfill_and_limit_override(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:

        class SyncStub:
            def sync_recent_closed_candles(
                self,
                *,
                exchange: str,
                symbol: str,
                timeframe: str,
                limit: int,
                backfill: bool = False,
            ) -> MarketDataSyncResult:
                assert exchange == settings.exchange_name
                assert symbol == settings.default_symbol
                assert timeframe == settings.default_timeframe
                assert limit == 500
                assert backfill is True
                return MarketDataSyncResult(
                    fetched_count=500,
                    stored_count=500,
                    latest_open_time=datetime(2026, 1, 21, 19, tzinfo=UTC),
                )

        from app.application.services import operational_control_service as controls_module

        original = controls_module.MarketDataSyncService
        controls_module.MarketDataSyncService = lambda session, client: SyncStub()
        try:
            response = client.post(
                "/controls/market-sync",
                json={"limit": 500, "backfill": True},
            )
        finally:
            controls_module.MarketDataSyncService = original

        assert response.status_code == 200
        payload = response.json()
        assert payload["detail"] == "market data backfill completed"
        assert payload["limit"] == 500
        assert payload["backfill"] is True
        assert payload["fetched_count"] == 500
        assert payload["stored_count"] == 500
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
            with patch(
                "app.application.services.worker_orchestration_service.QualificationService"
            ) as mock_qual:
                mock_qual.return_value.evaluate.return_value = type(
                    "Report", (), {"all_passed": True}
                )()
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


def test_worker_cycle_control_rejects_live_entry_when_halted(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.live_trading_halted = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        with patch(
            "app.application.services.worker_orchestration_service.QualificationService"
        ) as mock_qual:
            mock_qual.return_value.evaluate.return_value = type(
                "Report", (), {"all_passed": True}
            )()
            response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "risk_rejected"
        assert payload["detail"] == "live trading is halted by configuration"
        assert payload["signal_action"] == "buy"
    finally:
        teardown_client()


def test_live_halt_control_updates_runtime_state_and_status(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"

        response = client.post("/controls/live-halt", json={"halted": True})

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["detail"] == "live entry halted"
        assert payload["live_trading_halted"] is True
        assert payload["changed"] is True

        status_response = client.get("/status")
        assert status_response.status_code == 200
        assert status_response.json()["live_trading_halted"] is True
        assert status_response.json()["live_safety_status"] == "halted"

        session = create_session_factory(settings)()
        try:
            control = session.scalars(select(RuntimeControlRecord)).one()
            event = session.scalars(
                select(AuditEventRecord).order_by(AuditEventRecord.id.desc())
            ).first()
        finally:
            session.close()

        assert control.control_name == "live_trading_halted"
        assert control.bool_value is True
        assert control.updated_by == "api.control"
        assert event is not None
        assert event.event_type == "live_halt"
        assert event.source == "api.control"
    finally:
        teardown_client()


def test_worker_cycle_control_uses_runtime_halt_override(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"
        settings.live_trading_halted = False
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        halt_response = client.post("/controls/live-halt", json={"halted": True})
        assert halt_response.status_code == 200

        with patch(
            "app.application.services.worker_orchestration_service.QualificationService"
        ) as mock_qual:
            mock_qual.return_value.evaluate.return_value = type(
                "Report", (), {"all_passed": True}
            )()
            response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "risk_rejected"
        assert payload["detail"] == "live trading is halted by configuration"
        assert payload["signal_action"] == "buy"
    finally:
        teardown_client()


def test_worker_cycle_control_rejects_duplicate_live_order(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    try:
        settings.paper_trading = False
        settings.live_trading_enabled = True
        settings.exchange_api_key = "key"
        settings.exchange_api_secret = "secret"
        store_closes(settings, [10, 10, 10, 10, 10, 9, 9, 9, 20])

        session = create_session_factory(settings)()
        try:
            session.add(
                OrderRecord(
                    exchange=settings.exchange_name,
                    symbol=settings.default_symbol,
                    side="buy",
                    order_type="market",
                    status="submitted",
                    mode="live",
                    quantity=Decimal("0.002"),
                    price=Decimal("50000"),
                    client_order_id="existing-live-order-1",
                    exchange_order_id="existing-exchange-1",
                )
            )
            session.commit()
        finally:
            session.close()

        with patch(
            "app.application.services.worker_orchestration_service.QualificationService"
        ) as mock_qual:
            mock_qual.return_value.evaluate.return_value = type(
                "Report", (), {"all_passed": True}
            )()
            response = client.post("/controls/worker-cycle")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "duplicate_live_order"
        assert payload["detail"] == "active live order already exists for the same market side"
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
        assert payload["recovery_summary"] == "orders=1 filled=1"
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
