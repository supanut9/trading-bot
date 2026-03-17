from app.application.services.notification_service import build_notification_service
from app.application.services.operational_control_service import (
    LiveReconcileControlResult,
    OperationalControlService,
)
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class StartupStateSyncJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)
        self._notifications = build_notification_service(settings)

    def run(self) -> LiveReconcileControlResult:
        result = self._controls.run_live_reconcile(source="job.startup_state_sync")
        if result.status == "failed":
            self._notifications.notify_live_reconcile_failure(
                self._settings,
                source="job.startup_state_sync",
                detail=result.detail,
            )
        log_fn = logger.info if result.status == "completed" else logger.warning
        log_fn(
            "startup_state_sync_completed status=%s detail=%s reconciled_count=%s "
            "filled_count=%s exchange=%s symbol=%s timeframe=%s",
            result.status,
            result.detail,
            result.reconciled_count,
            result.filled_count,
            self._settings.exchange_name,
            self._settings.default_symbol,
            self._settings.default_timeframe,
        )
        return result
