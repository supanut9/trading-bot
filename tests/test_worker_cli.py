from dataclasses import dataclass

from app.application.services.worker_orchestration_service import WorkerCycleResult
from app.config import Settings, get_settings
from app.worker import main


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

    def notify_worker_cycle(self, _settings: Settings, _result: WorkerCycleResult) -> bool:
        self.closed_state_during_notify.append(self._state.closed)
        return True


def test_worker_notifies_after_session_scope_exits(monkeypatch) -> None:
    settings = Settings(
        DATABASE_URL="sqlite:///./worker_cli.db",
        WORKER_RUN_ONCE=True,
    )
    session_state = SessionState()
    notifications = RecordingNotifications(session_state)

    class FakeOrchestrationService:
        def __init__(self, session: FakeSession, active_settings: Settings) -> None:
            assert session._state is session_state
            assert active_settings is settings

        def run_cycle(self) -> WorkerCycleResult:
            return WorkerCycleResult(status="executed", detail="signal executed in paper mode")

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr(
        "app.worker.create_session_factory",
        lambda _settings: lambda: FakeSession(session_state),
    )
    monkeypatch.setattr("app.worker.build_notification_service", lambda _settings: notifications)
    monkeypatch.setattr("app.worker.WorkerOrchestrationService", FakeOrchestrationService)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert notifications.closed_state_during_notify == [True]
