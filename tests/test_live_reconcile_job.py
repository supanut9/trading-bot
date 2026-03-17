from dataclasses import dataclass

from app.application.services.operational_control_service import LiveReconcileControlResult
from app.config import Settings
from app.jobs.live_reconcile_job import LiveReconcileJob


@dataclass
class RecordingNotifications:
    reconcile_failures: list[tuple[str, str]]
    stale_counts: list[int]

    def notify_live_reconcile_failure(
        self, settings: Settings, *, source: str, detail: str
    ) -> bool:
        self.reconcile_failures.append((source, detail))
        return True

    def notify_stale_live_orders(
        self, settings: Settings, *, stale_orders, threshold_minutes: int
    ) -> bool:
        self.stale_counts.append(len(stale_orders))
        return True


def test_live_reconcile_job_notifies_failure_and_stale_orders(monkeypatch) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )
    notifications = RecordingNotifications(reconcile_failures=[], stale_counts=[])

    class FakeControls:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run_live_reconcile(self, *, source: str) -> LiveReconcileControlResult:
            assert source == "job.live_reconcile"
            return LiveReconcileControlResult(
                status="failed",
                detail="live reconciliation failed",
                reconciled_count=0,
                filled_count=0,
                notified=False,
            )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeStaleService:
        def __init__(self, session) -> None:
            pass

        def list_stale_orders(self, *, threshold_minutes: int, limit: int):
            return [object(), object()]

    monkeypatch.setattr("app.jobs.live_reconcile_job.OperationalControlService", FakeControls)
    monkeypatch.setattr(
        "app.jobs.live_reconcile_job.build_notification_service",
        lambda active_settings: notifications,
    )
    monkeypatch.setattr(
        "app.jobs.live_reconcile_job.create_session_factory",
        lambda active_settings: lambda: FakeSession(),
    )
    monkeypatch.setattr("app.jobs.live_reconcile_job.StaleLiveOrderService", FakeStaleService)

    result = LiveReconcileJob(settings).run()

    assert result.status == "failed"
    assert notifications.reconcile_failures == [
        ("job.live_reconcile", "live reconciliation failed")
    ]
    assert notifications.stale_counts == [2]
