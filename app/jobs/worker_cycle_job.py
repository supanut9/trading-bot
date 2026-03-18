from app.application.services.operational_control_service import (
    OperationalControlService,
    WorkerControlResult,
)
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class WorkerCycleJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)

    def run(self) -> WorkerControlResult:
        result = self._controls.run_worker_cycle(source="job.worker_cycle")
        logger.info(
            "worker_cycle_completed status=%s detail=%s signal=%s "
            "order_id=%s trade_id=%s notified=%s exchange=%s symbol=%s timeframe=%s "
            "live_safety_status=%s",
            result.status,
            result.detail,
            result.signal_action,
            result.order_id,
            result.trade_id,
            result.notified,
            self._settings.exchange_name,
            self._settings.default_symbol,
            self._settings.default_timeframe,
            "disabled"
            if not self._settings.live_trading_enabled
            else ("halted" if self._settings.live_trading_halted else "enabled"),
        )
        return result
