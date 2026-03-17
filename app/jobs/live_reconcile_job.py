from app.application.services.operational_control_service import (
    LiveReconcileControlResult,
    OperationalControlService,
)
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class LiveReconcileJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)

    def run(self) -> LiveReconcileControlResult:
        result = self._controls.run_live_reconcile(source="job.live_reconcile")
        logger.info(
            "scheduled_live_reconcile_completed status=%s detail=%s reconciled_count=%s "
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
