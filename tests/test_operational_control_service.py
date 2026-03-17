from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.services.market_data_sync_service import MarketDataSyncResult
from app.application.services.operational_control_service import (
    MarketSyncControlResult,
    OperationalControlService,
    WorkerControlResult,
)
from app.application.services.worker_orchestration_service import WorkerCycleResult
from app.config import Settings


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


def test_worker_control_notifies_after_session_scope_exits(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    session_state = SessionState()
    notifications = RecordingNotifications(session_state)

    class FakeOrchestrationService:
        def __init__(self, session: FakeSession, active_settings: Settings) -> None:
            assert session._state is session_state
            assert active_settings is settings

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
    )

    result = service.run_worker_cycle()

    assert isinstance(result, WorkerControlResult)
    assert result.notified is True
    assert notifications.closed_state_during_notify == [True]


def test_market_sync_control_returns_completed_result(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    session_state = SessionState()
    notifications = RecordingNotifications(session_state)

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
        ) -> MarketDataSyncResult:
            assert exchange == settings.exchange_name
            assert symbol == settings.default_symbol
            assert timeframe == settings.default_timeframe
            assert limit == settings.market_data_sync_limit
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
    )

    result = service.run_market_sync()

    assert result == MarketSyncControlResult(
        status="completed",
        detail="market data sync completed",
        fetched_count=4,
        stored_count=2,
        latest_open_time=datetime(2026, 1, 1, 3, tzinfo=UTC),
        notified=True,
    )
    assert len(notifications.market_sync_results) == 1


def test_market_sync_control_reports_no_new_candles(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./operational_controls.db")
    notifications = RecordingNotifications(SessionState())

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
        ) -> MarketDataSyncResult:
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
    )

    result = service.run_market_sync()

    assert result.detail == "no new candles stored"
    assert result.notified is True
