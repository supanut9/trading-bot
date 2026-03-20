"""
Service that monitors for repeated technical exchange errors and auto-halts
live trading when the consecutive failure threshold is breached.
"""

from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditEventFilters, AuditService
from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class LiveIncidentAutoHaltService:
    """
    Polls the audit log for consecutive exchange-level failures and halts live
    trading if the configured threshold is exceeded.

    Intended to be called once per worker cycle (after exchange interaction).
    """

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditService(session=session)
        self._control = LiveOperatorControlService(session=session, settings=settings)

    def evaluate_and_halt_if_needed(self) -> bool:
        """
        Returns True if trading was halted by this check, False otherwise.
        """
        threshold = self._settings.live_consecutive_exchange_error_auto_halt_threshold
        if threshold is None:
            return False

        if not self._settings.live_trading_enabled:
            return False

        recent_events = self._audit.list_recent(
            limit=threshold + 5,
            filters=AuditEventFilters(event_type="worker_cycle"),
        )

        consecutive_failures = 0
        for event in recent_events:
            if event.status == "failed":
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= threshold:
            reason = (
                f"consecutive_exchange_error_auto_halt "
                f"(threshold={threshold}, count={consecutive_failures})"
            )
            logger.critical(
                "live_incident_auto_halt triggered exchange_error_count=%s threshold=%s",
                consecutive_failures,
                threshold,
            )
            self._control.set_live_trading_halted(
                halted=True,
                updated_by="system",
                reason=reason,
            )
            self._session.commit()
            return True

        return False
