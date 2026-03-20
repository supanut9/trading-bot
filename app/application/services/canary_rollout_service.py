from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditEventFilters, AuditService
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class CanaryRolloutService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditService(session=session)

    def get_exposure_multiplier(self) -> Decimal:
        """
        Returns a multiplier [0.0, 1.0] based on live run duration without incidents.
        Starts at 0.1 (10%) and reaches 1.0 (100%) over 7 days of incident-free live run.
        """
        if self._settings.execution_mode != "live":
            return Decimal("1.0")

        # Check for incidents in last 7 days
        recent_incidents = self._audit.list_recent(
            limit=10,
            filters=AuditEventFilters(status="failed"),
        )

        # We also want to check for risk violations
        risk_violations = self._audit.list_recent(
            limit=10,
            filters=AuditEventFilters(event_type="risk_violation"),
        )

        last_incident_at = datetime.min.replace(tzinfo=UTC)

        for event in recent_incidents + risk_violations:
            if event.created_at > last_incident_at:
                last_incident_at = event.created_at

        # Also find the most recent startup
        startups = self._audit.list_recent(
            limit=1,
            filters=AuditEventFilters(event_type="system_startup"),
        )

        if not startups:
            # If no startup found (unexpected), start fresh
            live_duration = timedelta(0)
        else:
            # Use the later of startup or last incident
            reference_time = max(startups[0].created_at, last_incident_at)
            live_duration = datetime.now(UTC) - reference_time

        # Ramp up over 7 days (168 hours)
        ramp_up_period_days = 7
        total_seconds = ramp_up_period_days * 24 * 3600

        duration_seconds = max(0, int(live_duration.total_seconds()))

        # Multiplier formula: 0.1 + 0.9 * (duration / total_seconds)
        # Minimum 0.1
        base_multiplier = Decimal("0.1")
        progress = Decimal(min(duration_seconds, total_seconds)) / Decimal(total_seconds)
        multiplier = base_multiplier + (Decimal("0.9") * progress)

        logger.info(
            "canary_rollout_exposure live_duration=%s multiplier=%s",
            live_duration,
            multiplier.quantize(Decimal("0.0001")),
        )

        return multiplier.quantize(Decimal("0.0001"))
