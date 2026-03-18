from app.application.services.notification_service import build_notification_service
from app.application.services.operational_control_service import (
    LiveReconcileControlResult,
    OperationalControlService,
)
from app.application.services.stale_live_order_service import StaleLiveOrderService
from app.config import Settings
from app.core.logger import build_correlation_id, correlation_context, get_logger
from app.infrastructure.database.session import create_session_factory

logger = get_logger(__name__)


class LiveReconcileJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)
        self._notifications = build_notification_service(settings)
        self._session_factory = create_session_factory(settings)

    def run(self) -> LiveReconcileControlResult:
        with correlation_context(build_correlation_id("live-reconcile")):
            result = self._controls.run_live_reconcile(source="job.live_reconcile")
            if result.status == "failed":
                self._notifications.notify_live_reconcile_failure(
                    self._settings,
                    source="job.live_reconcile",
                    detail=result.detail,
                )
            with self._session_factory() as session:
                stale_orders = StaleLiveOrderService(session).list_stale_orders(
                    threshold_minutes=self._settings.stale_live_order_threshold_minutes,
                    limit=10,
                )
            self._notifications.notify_stale_live_orders(
                self._settings,
                stale_orders=stale_orders,
                threshold_minutes=self._settings.stale_live_order_threshold_minutes,
            )
            logger.info(
                "scheduled_live_reconcile_completed status=%s detail=%s reconciled_count=%s "
                "filled_count=%s review_required_count=%s exchange=%s symbol=%s timeframe=%s "
                "live_safety_status=%s",
                result.status,
                result.detail,
                result.reconciled_count,
                result.filled_count,
                result.review_required_count,
                self._settings.exchange_name,
                self._settings.default_symbol,
                self._settings.default_timeframe,
                "disabled"
                if not self._settings.live_trading_enabled
                else ("halted" if self._settings.live_trading_halted else "enabled"),
            )
            return result
