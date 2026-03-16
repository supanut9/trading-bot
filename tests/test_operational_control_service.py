from dataclasses import dataclass

from app.application.services.operational_control_service import (
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

    def notify_worker_cycle(self, _settings: Settings, _result: WorkerCycleResult) -> bool:
        self.closed_state_during_notify.append(self._state.closed)
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
