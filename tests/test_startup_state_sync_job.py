from dataclasses import dataclass

from app.application.services.operational_control_service import LiveReconcileControlResult
from app.config import Settings
from app.jobs.startup_state_sync_job import StartupStateSyncJob


@dataclass
class RecordingNotifications:
    reconcile_failures: list[tuple[str, str]]

    def notify_live_reconcile_failure(
        self, settings: Settings, *, source: str, detail: str
    ) -> bool:
        self.reconcile_failures.append((source, detail))
        return True


def test_startup_state_sync_job_notifies_failure(monkeypatch) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    notifications = RecordingNotifications(reconcile_failures=[])

    class FakeControls:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run_live_reconcile(self, *, source: str) -> LiveReconcileControlResult:
            assert source == "job.startup_state_sync"
            return LiveReconcileControlResult(
                status="failed",
                detail="live reconciliation failed",
                reconciled_count=0,
                filled_count=0,
                notified=False,
            )

    monkeypatch.setattr("app.jobs.startup_state_sync_job.OperationalControlService", FakeControls)
    monkeypatch.setattr(
        "app.jobs.startup_state_sync_job.build_notification_service",
        lambda active_settings: notifications,
    )

    result = StartupStateSyncJob(settings).run()

    assert result.status == "failed"
    assert notifications.reconcile_failures == [
        ("job.startup_state_sync", "live reconciliation failed")
    ]
