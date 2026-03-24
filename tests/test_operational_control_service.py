from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.operational_control_service import (
    BacktestRunOptions,
    LiveCancelControlResult,
    MarketSyncControlResult,
    MarketSyncRunOptions,
    OperationalControlService,
    WorkerControlResult,
    required_candles_for_backtest_options,
)
from app.application.services.worker_orchestration_service import WorkerCycleResult
from app.config import Settings
from app.infrastructure.database.models.order import OrderRecord


@dataclass
class SessionState:
    closed: bool = False


class FakeSession:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._state.closed = True


class RecordingNotifications:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.closed_state_during_notify: list[bool] = []
        self.market_sync_results = []

    def notify_worker_cycle(self, _settings: Settings, _result: WorkerCycleResult) -> bool:
        self.closed_state_during_notify.append(self._state.closed)
        return True

    def notify_market_sync(self, _settings: Settings, result: MarketSyncControlResult) -> bool:
        self.market_sync_results.append(result)
        return True


class RecordingAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    def record_control_result(self, **kwargs: object) -> None:
        self.entries.append(kwargs)


def test_worker_control_notifies_after_session_scope_exits(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    session_state = SessionState()
    notifications = RecordingNotifications(session_state)
    audit = RecordingAudit()

    class FakeOrchestrationService:
        def __init__(
            self,
            session: FakeSession,
            active_settings: Settings,
            *,
            operator_config=None,
        ) -> None:
            assert session._state is session_state
            assert active_settings is settings
            assert operator_config is not None

        def run_cycle(self) -> WorkerCycleResult:
            return WorkerCycleResult(status="executed", detail="signal executed in paper mode")

    monkeypatch.setattr(
        "app.application.services.operational_control_service.WorkerOrchestrationService",
        FakeOrchestrationService,
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(session_state),
        notifications=notifications,
        audit=audit,
    )

    result = service.run_worker_cycle(source="api.control")

    assert isinstance(result, WorkerControlResult)
    assert result.notified is True
    assert notifications.closed_state_during_notify == [True]
    assert len(audit.entries) == 1
    assert audit.entries[0]["control_type"] == "worker_cycle"
    assert audit.entries[0]["source"] == "api.control"


def test_market_sync_control_returns_completed_result(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    session_state = SessionState()
    notifications = RecordingNotifications(session_state)
    audit = RecordingAudit()

    class FakeSyncService:
        def __init__(self, session: FakeSession, _client: object) -> None:
            assert session._state is session_state

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
            return MarketDataSyncResult(
                fetched_count=4,
                stored_count=2,
                latest_open_time=datetime(2026, 1, 1, 3, tzinfo=UTC),
            )

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataSyncService",
        FakeSyncService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_market_data_exchange_client",
        lambda _settings: object(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(session_state),
        notifications=notifications,
        audit=audit,
    )

    result = service.run_market_sync()

    assert result == MarketSyncControlResult(
        status="completed",
        detail="market data sync completed",
        symbol=settings.default_symbol,
        timeframe=settings.default_timeframe,
        limit=settings.market_data_sync_limit,
        backfill=False,
        fetched_count=4,
        stored_count=2,
        latest_open_time=datetime(2026, 1, 1, 3, tzinfo=UTC),
        notified=True,
    )
    assert len(notifications.market_sync_results) == 1
    assert len(audit.entries) == 1
    assert audit.entries[0]["control_type"] == "market_sync"


def test_market_sync_control_reports_no_new_candles(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    notifications = RecordingNotifications(SessionState())
    audit = RecordingAudit()

    class FakeSyncService:
        def __init__(self, _session: FakeSession, _client: object) -> None:
            pass

        def sync_recent_closed_candles(
            self,
            *,
            exchange: str,
            symbol: str,
            timeframe: str,
            limit: int,
            backfill: bool = False,
        ) -> MarketDataSyncResult:
            assert backfill is False
            return MarketDataSyncResult(
                fetched_count=4,
                stored_count=0,
                latest_open_time=datetime(2026, 1, 1, 3, tzinfo=UTC),
            )

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataSyncService",
        FakeSyncService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_market_data_exchange_client",
        lambda _settings: object(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        notifications=notifications,
        audit=audit,
    )

    result = service.run_market_sync()

    assert result.detail == "no new candles stored"
    assert result.notified is True
    assert len(audit.entries) == 1
    assert audit.entries[0]["status"] == "completed"


def test_market_sync_control_accepts_explicit_market_options(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    notifications = RecordingNotifications(SessionState())
    audit = RecordingAudit()

    class FakeSyncService:
        def __init__(self, _session: FakeSession, _client: object) -> None:
            pass

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
            assert limit == 250
            assert backfill is True
            return MarketDataSyncResult(
                fetched_count=12,
                stored_count=12,
                latest_open_time=datetime(2026, 1, 1, 11, tzinfo=UTC),
            )

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataSyncService",
        FakeSyncService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_market_data_exchange_client",
        lambda _settings: object(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        notifications=notifications,
        audit=audit,
    )

    result = service.run_market_sync(
        options=MarketSyncRunOptions(
            symbol="ETH/USDT",
            timeframe="4h",
            limit=250,
            backfill=True,
        )
    )

    assert result == MarketSyncControlResult(
        status="completed",
        detail="market data backfill completed",
        symbol="ETH/USDT",
        timeframe="4h",
        limit=250,
        backfill=True,
        fetched_count=12,
        stored_count=12,
        latest_open_time=datetime(2026, 1, 1, 11, tzinfo=UTC),
        notified=True,
    )
    assert len(audit.entries) == 1
    assert audit.entries[0]["payload"]["symbol"] == "ETH/USDT"


def test_live_reconcile_control_returns_completed_result(monkeypatch) -> None:
    settings = Settings(
        DATABASE_URL="sqlite:///./operational_controls.db",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    audit = RecordingAudit()

    class FakeReconcileService:
        def __init__(self, _session: FakeSession, _settings: Settings, client: object) -> None:
            assert client is not None

        def reconcile_recent_live_orders(self):
            return [
                type(
                    "Result",
                    (),
                    {
                        "trade_created": True,
                        "requires_operator_review": False,
                        "recovery_state": "awaiting_exchange",
                    },
                )(),
                type(
                    "Result",
                    (),
                    {
                        "trade_created": False,
                        "requires_operator_review": True,
                        "recovery_state": "manual_review_required",
                    },
                )(),
            ]

    monkeypatch.setattr(
        "app.application.services.operational_control_service.LiveFillReconciliationService",
        FakeReconcileService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_live_order_exchange_client",
        lambda _settings: object(),
    )
    monkeypatch.setattr(
        OperationalControlService,
        "_build_live_recovery_summary",
        lambda self, session: type(
            "Summary",
            (),
            {
                "posture": "manual_review_required",
                "dominant_recovery_state": "manual_review_required",
                "next_action": "inspect_exchange_state",
                "summary": "1 unresolved live order requires manual exchange-state review",
                "unresolved_order_count": 1,
                "awaiting_exchange_count": 0,
                "partial_fill_in_flight_count": 0,
                "stale_open_order_count": 0,
                "stale_partial_fill_count": 0,
                "manual_review_required_count": 1,
                "requires_operator_review_count": 1,
                "stale_order_count": 0,
            },
        )(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_reconcile(source="job.live_reconcile")

    assert result.status == "completed"
    assert result.detail == "live orders require operator review"
    assert result.reconciled_count == 2
    assert result.filled_count == 1
    assert result.review_required_count == 1
    assert result.recovery_summary == "orders=2 filled=1 review_required=1"
    assert result.live_recovery_summary is not None
    assert result.live_recovery_summary.posture == "manual_review_required"
    assert result.live_recovery_summary.next_action == "inspect_exchange_state"
    assert len(audit.entries) == 1
    assert audit.entries[0]["control_type"] == "live_reconcile"
    assert audit.entries[0]["source"] == "job.live_reconcile"
    assert (
        audit.entries[0]["payload"]["live_recovery_summary"]["posture"] == "manual_review_required"
    )


def test_live_reconcile_control_returns_failed_result_on_client_error(monkeypatch) -> None:
    settings = Settings(
        DATABASE_URL="sqlite:///./operational_controls.db",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    audit = RecordingAudit()

    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_live_order_exchange_client",
        lambda _settings: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        OperationalControlService,
        "_load_live_recovery_summary",
        lambda self: type(
            "Summary",
            (),
            {
                "posture": "stale_orders",
                "dominant_recovery_state": "stale_open_order",
                "next_action": "reconcile_or_cancel",
                "summary": "1 stale live order requires reconcile or cancel review",
                "unresolved_order_count": 1,
                "awaiting_exchange_count": 0,
                "partial_fill_in_flight_count": 0,
                "stale_open_order_count": 1,
                "stale_partial_fill_count": 0,
                "manual_review_required_count": 0,
                "requires_operator_review_count": 0,
                "stale_order_count": 1,
            },
        )(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_reconcile(source="job.live_reconcile")

    assert result.status == "failed"
    assert result.detail == "live reconciliation failed"
    assert result.reconciled_count == 0
    assert result.filled_count == 0
    assert result.review_required_count == 0
    assert result.recovery_summary == "reconciliation_failed"
    assert result.live_recovery_summary is not None
    assert result.live_recovery_summary.posture == "stale_orders"
    assert result.live_recovery_summary.next_action == "reconcile_or_cancel"
    assert len(audit.entries) == 1
    assert audit.entries[0]["status"] == "failed"
    assert audit.entries[0]["payload"]["live_recovery_summary"]["posture"] == "stale_orders"


def test_live_cancel_control_returns_failed_when_identifier_missing() -> None:
    settings = Settings(
        DATABASE_URL="sqlite:///./operational_controls.db",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    audit = RecordingAudit()

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_cancel(source="api.control")

    assert result == LiveCancelControlResult(
        status="failed",
        detail="exactly one live order identifier is required",
        order_id=None,
        client_order_id=None,
        exchange_order_id=None,
        order_status=None,
        notified=False,
    )
    assert audit.entries[0]["control_type"] == "live_cancel"


def test_live_cancel_control_skips_non_cancelable_status(tmp_path) -> None:
    settings = Settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'cancel_control.db'}",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    from app.infrastructure.database.base import Base
    from app.infrastructure.database.session import (
        create_engine_from_settings,
        create_session_factory,
    )

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(settings)
    with session_factory() as session:
        session.add(
            OrderRecord(
                exchange="binance",
                symbol="BTC/USDT",
                side="buy",
                order_type="market",
                status="filled",
                mode="live",
                quantity=1,
                client_order_id="filled-live-order",
                exchange_order_id="999",
            )
        )
        session.commit()
        order_id = session.query(OrderRecord).one().id

    audit = RecordingAudit()
    service = OperationalControlService(
        settings,
        session_factory=session_factory,
        audit=audit,
    )

    result = service.run_live_cancel(order_id=order_id, source="api.control")

    assert result == LiveCancelControlResult(
        status="skipped",
        detail="live order is not cancelable in its current status",
        order_id=order_id,
        client_order_id="filled-live-order",
        exchange_order_id="999",
        order_status="filled",
        notified=False,
    )
    assert audit.entries[0]["status"] == "skipped"


def test_live_halt_rejects_resume_when_readiness_checks_fail(monkeypatch) -> None:
    settings = Settings(
        DATABASE_URL="sqlite:///./operational_controls.db",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    audit = RecordingAudit()

    class FakeLiveReadinessService:
        def __init__(self, _session, _settings) -> None:
            pass

        def build_report(self):
            return type(
                "Report",
                (),
                {
                    "ready": False,
                    "blocking_reasons": [
                        "live recovery posture is blocked: "
                        "1 unresolved live order(s) require manual exchange-state "
                        "review before trusting local recovery state "
                        "(next action: inspect_exchange_state)"
                    ],
                },
            )()

    monkeypatch.setattr(
        "app.application.services.operational_control_service.LiveReadinessService",
        FakeLiveReadinessService,
    )
    monkeypatch.setattr(
        OperationalControlService,
        "_build_live_recovery_summary",
        lambda self, session: type(
            "Summary",
            (),
            {
                "posture": "manual_review_required",
                "dominant_recovery_state": "manual_review_required",
                "next_action": "inspect_exchange_state",
                "summary": "1 unresolved live order requires manual exchange-state review",
                "unresolved_order_count": 1,
                "awaiting_exchange_count": 0,
                "partial_fill_in_flight_count": 0,
                "stale_open_order_count": 0,
                "stale_partial_fill_count": 0,
                "manual_review_required_count": 1,
                "requires_operator_review_count": 1,
                "stale_order_count": 0,
            },
        )(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_halt(halted=False, source="api.control")

    assert result.status == "failed"
    assert (
        result.detail == "cannot resume live trading: live recovery posture is blocked: "
        "1 unresolved live order(s) require manual exchange-state review before "
        "trusting local recovery state (next action: inspect_exchange_state)"
    )
    assert result.live_recovery_summary is not None
    assert result.live_recovery_summary.posture == "manual_review_required"
    assert len(audit.entries) == 1
    assert audit.entries[0]["payload"]["reason"] == "live_readiness_failed"
    assert (
        audit.entries[0]["payload"]["live_recovery_summary"]["posture"] == "manual_review_required"
    )


def test_runtime_promotion_rejects_update_when_prerequisites_fail(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    audit = RecordingAudit()

    class FakeRuntimePromotionService:
        def __init__(self, _session, _settings) -> None:
            pass

        def set_stage(self, *, stage: str, updated_by: str):
            raise ValueError("live readiness is blocked")

        def get_state(self):
            return type(
                "State",
                (),
                {"stage": "paper", "blockers": ("live readiness is blocked",)},
            )()

    monkeypatch.setattr(
        "app.application.services.operational_control_service.RuntimePromotionService",
        FakeRuntimePromotionService,
    )
    monkeypatch.setattr(
        OperationalControlService,
        "_build_live_recovery_summary",
        lambda self, session: type(
            "Summary",
            (),
            {
                "posture": "clear",
                "dominant_recovery_state": "resolved",
                "next_action": "none",
                "summary": "No unresolved live recovery work remains.",
                "unresolved_order_count": 0,
                "awaiting_exchange_count": 0,
                "partial_fill_in_flight_count": 0,
                "stale_open_order_count": 0,
                "stale_partial_fill_count": 0,
                "manual_review_required_count": 0,
                "requires_operator_review_count": 0,
                "stale_order_count": 0,
            },
        )(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_update_runtime_promotion(stage="canary", source="api.control")

    assert result.status == "failed"
    assert result.detail == "cannot promote runtime stage: live readiness is blocked"
    assert result.stage == "paper"
    assert result.changed is False
    assert result.blockers == ("live readiness is blocked",)
    assert result.live_recovery_summary is not None
    assert result.live_recovery_summary.posture == "clear"
    assert audit.entries[0]["control_type"] == "runtime_promotion"
    assert audit.entries[0]["payload"]["live_recovery_summary"]["posture"] == "clear"


# ---------------------------------------------------------------------------
# Leverage resolution tests
# ---------------------------------------------------------------------------


def _make_service_for_leverage(settings: Settings) -> OperationalControlService:
    """Build an OperationalControlService with no-op session/notifications/audit."""

    class NullSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class NullNotifications:
        def notify_worker_cycle(self, *args, **kwargs):
            return False

        def notify_market_sync(self, *args, **kwargs):
            return False

        def notify_backtest_completed(self, *args, **kwargs):
            return False

        def notify_backtest_skipped(self, *args, **kwargs):
            return False

    class NullAudit:
        def record_control_result(self, **kwargs):
            pass

    return OperationalControlService(
        settings,
        session_factory=lambda: NullSession(),
        notifications=NullNotifications(),
        audit=NullAudit(),
    )


def test_resolve_leverage_1_for_spot() -> None:
    settings = Settings(DATABASE_URL="sqlite:///./leverage_test.db")
    service = _make_service_for_leverage(settings)

    result = service._resolve_leverage(
        requested_leverage=50,
        symbol="BTCUSDT",
        trading_mode="SPOT",
    )

    assert result == 1


def test_resolve_leverage_manual_passthrough() -> None:
    settings = Settings(DATABASE_URL="sqlite:///./leverage_test.db")
    service = _make_service_for_leverage(settings)

    result = service._resolve_leverage(
        requested_leverage=10,
        symbol="BTCUSDT",
        trading_mode="FUTURES",
    )

    assert result == 10


def test_resolve_leverage_auto_fallback(monkeypatch) -> None:
    """When exchange raises, auto-resolve falls back to 1."""
    settings = Settings(DATABASE_URL="sqlite:///./leverage_test.db")
    service = _make_service_for_leverage(settings)

    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_live_order_exchange_client",
        lambda _settings, **_kwargs: (_ for _ in ()).throw(RuntimeError("no API keys")),
    )

    result = service._resolve_leverage(
        requested_leverage=None,
        symbol="BTCUSDT",
        trading_mode="FUTURES",
    )

    assert result == 1


def test_resolve_leverage_auto_from_exchange(monkeypatch) -> None:
    """When exchange returns leverage=20, auto-resolve returns 20."""
    settings = Settings(DATABASE_URL="sqlite:///./leverage_test.db")
    service = _make_service_for_leverage(settings)

    class FakeClient:
        def fetch_position_risk(self, *, symbol: str):
            return [{"leverage": "20", "symbol": symbol}]

    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_live_order_exchange_client",
        lambda _settings, **_kwargs: FakeClient(),
    )

    result = service._resolve_leverage(
        requested_leverage=None,
        symbol="BTCUSDT",
        trading_mode="FUTURES",
    )

    assert result == 20


def test_control_result_includes_leverage_fields(monkeypatch) -> None:
    """run_backtest result includes leverage, margin_mode, and liquidation_count."""
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415
    from decimal import Decimal  # noqa: PLC0415

    settings = Settings(DATABASE_URL="sqlite:///./leverage_test.db")

    start = datetime(2026, 1, 1, tzinfo=UTC)
    fake_candles = [
        type(
            "CandleRecord",
            (),
            {
                "open_time": start + timedelta(hours=i),
                "close_time": start + timedelta(hours=i + 1),
                "open_price": Decimal("100"),
                "high_price": Decimal("100"),
                "low_price": Decimal("100"),
                "close_price": Decimal("100"),
                "volume": Decimal("1"),
            },
        )()
        for i in range(60)
    ]

    class FakeMarketDataService:
        def __init__(self, _session):
            pass

        def list_historical_candles(self, **kwargs):
            return fake_candles

    class FakeBacktestRunHistoryService:
        def __init__(self, **kwargs):
            pass

        def record_run(self, **kwargs):
            pass

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataService",
        FakeMarketDataService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.BacktestRunHistoryService",
        FakeBacktestRunHistoryService,
    )
    monkeypatch.setattr(
        "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated",
        lambda *a, **kw: None,
    )

    class NullSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class NullNotifications:
        def notify_worker_cycle(self, *a, **kw):
            return False

        def notify_market_sync(self, *a, **kw):
            return False

        def notify_backtest_completed(self, *a, **kw):
            return False

        def notify_backtest_skipped(self, *a, **kw):
            return False

    class NullAudit:
        def record_control_result(self, **kwargs):
            pass

    service = OperationalControlService(
        settings,
        session_factory=lambda: NullSession(),
        notifications=NullNotifications(),
        audit=NullAudit(),
    )

    result = service.run_backtest(
        options=BacktestRunOptions(
            strategy_name="ema_crossover",
            exchange="binance",
            symbol="BTCUSDT",
            timeframe="1h",
            fast_period=5,
            slow_period=10,
            starting_equity=Decimal("10000"),
            trading_mode="FUTURES",
            leverage=15,
            margin_mode="CROSS",
        ),
        notify=False,
        audit=False,
        record_history=False,
    )

    assert result.leverage == 15
    assert result.margin_mode == "CROSS"
    assert result.liquidation_count == 0
    assert result.trading_mode == "FUTURES"


def test_run_backtest_returns_failed_when_model_file_is_missing(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./ml_backtest_missing_model.db")

    start = datetime(2026, 1, 1, tzinfo=UTC)
    fake_candles = [
        type(
            "CandleRecord",
            (),
            {
                "open_time": start + timedelta(hours=i),
                "close_time": start + timedelta(hours=i + 1),
                "open_price": Decimal("100"),
                "high_price": Decimal("100"),
                "low_price": Decimal("100"),
                "close_price": Decimal("100"),
                "volume": Decimal("1"),
            },
        )()
        for i in range(60)
    ]

    class FakeMarketDataService:
        def __init__(self, _session):
            pass

        def list_historical_candles(self, **kwargs):
            return fake_candles

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataService",
        FakeMarketDataService,
    )
    monkeypatch.setattr(
        "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated",
        lambda *a, **kw: None,
    )

    class NullSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def commit(self):
            pass

    class NullNotifications:
        def notify_backtest_completed(self, *a, **kw):
            return False

        def notify_backtest_skipped(self, *a, **kw):
            return False

    class NullAudit:
        def record_control_result(self, **kwargs):
            pass

    service = OperationalControlService(
        settings,
        session_factory=lambda: NullSession(),
        notifications=NullNotifications(),
        audit=NullAudit(),
    )

    result = service.run_backtest(
        options=BacktestRunOptions(
            strategy_name="ml_signal",
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="2d",
            starting_equity=Decimal("10000"),
            model_type="xgboost",
        ),
        notify=False,
        audit=False,
        record_history=False,
    )

    assert result.status == "failed"
    assert "Model metadata not found" in result.detail or "Model not found" in result.detail


def test_required_candles_for_ema_adx_trend_uses_trend_ema_floor() -> None:
    required = required_candles_for_backtest_options(
        BacktestRunOptions(strategy_name="ema_adx_trend", adx_period=14)
    )

    assert required == 101


def test_required_candles_for_ema_adx_trend_volume_uses_trend_ema_floor() -> None:
    required = required_candles_for_backtest_options(
        BacktestRunOptions(strategy_name="ema_adx_trend_volume", adx_period=14)
    )

    assert required == 101


def test_run_backtest_uses_history_candle_target_for_auto_sync(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./backtest_history_target.db")
    sync_limits: list[int] = []

    start = datetime(2026, 1, 1, tzinfo=UTC)
    fake_candles = [
        type(
            "CandleRecord",
            (),
            {
                "open_time": start + timedelta(hours=i),
                "close_time": start + timedelta(hours=i + 1),
                "open_price": Decimal("100"),
                "high_price": Decimal("100"),
                "low_price": Decimal("100"),
                "close_price": Decimal("100"),
                "volume": Decimal("1"),
            },
        )()
        for i in range(5000)
    ]

    class FakeMarketDataService:
        def __init__(self, _session):
            pass

        def list_historical_candles(self, **kwargs):
            return fake_candles

    class FakeBacktestRunHistoryService:
        def __init__(self, **kwargs):
            pass

        def record_run(self, **kwargs):
            pass

    def fake_sync(*args, **kwargs):
        sync_limits.append(kwargs["total_limit"])
        return None

    monkeypatch.setattr(
        "app.application.services.operational_control_service.MarketDataService",
        FakeMarketDataService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.BacktestRunHistoryService",
        FakeBacktestRunHistoryService,
    )
    monkeypatch.setattr(
        "app.application.services.market_data_sync_service.MarketDataSyncService.sync_candles_paginated",
        fake_sync,
    )

    class NullSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def commit(self):
            pass

    class NullNotifications:
        def notify_backtest_completed(self, *a, **kw):
            return False

        def notify_backtest_skipped(self, *a, **kw):
            return False

    class NullAudit:
        def record_control_result(self, **kwargs):
            pass

    service = OperationalControlService(
        settings,
        session_factory=lambda: NullSession(),
        notifications=NullNotifications(),
        audit=NullAudit(),
    )

    service.run_backtest(
        options=BacktestRunOptions(
            strategy_name="ema_crossover",
            exchange="binance",
            symbol="ETH/USDT",
            timeframe="1h",
            fast_period=20,
            slow_period=50,
            starting_equity=Decimal("10000"),
            history_candle_target=5000,
        ),
        notify=False,
        audit=False,
        record_history=False,
    )

    assert sync_limits[0] == 5100
