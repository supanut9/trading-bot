from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.operational_control_service import (
    LiveCancelControlResult,
    LiveReconcileControlResult,
    MarketSyncControlResult,
    OperationalControlService,
    WorkerControlResult,
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
        def __init__(self, _session: FakeSession, client: object) -> None:
            assert client is not None

        def reconcile_recent_live_orders(self):
            return [
                type("Result", (), {"trade_created": True, "requires_operator_review": False})(),
                type("Result", (), {"trade_created": False, "requires_operator_review": True})(),
            ]

    monkeypatch.setattr(
        "app.application.services.operational_control_service.LiveFillReconciliationService",
        FakeReconcileService,
    )
    monkeypatch.setattr(
        "app.application.services.operational_control_service.build_live_order_exchange_client",
        lambda _settings: object(),
    )

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_reconcile(source="job.live_reconcile")

    assert result == LiveReconcileControlResult(
        status="completed",
        detail="live orders require operator review",
        reconciled_count=2,
        filled_count=1,
        review_required_count=1,
        notified=False,
    )
    assert len(audit.entries) == 1
    assert audit.entries[0]["control_type"] == "live_reconcile"
    assert audit.entries[0]["source"] == "job.live_reconcile"


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

    service = OperationalControlService(
        settings,
        session_factory=lambda: FakeSession(SessionState()),
        audit=audit,
    )

    result = service.run_live_reconcile(source="job.live_reconcile")

    assert result == LiveReconcileControlResult(
        status="failed",
        detail="live reconciliation failed",
        reconciled_count=0,
        filled_count=0,
        review_required_count=0,
        notified=False,
    )
    assert len(audit.entries) == 1
    assert audit.entries[0]["status"] == "failed"


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
