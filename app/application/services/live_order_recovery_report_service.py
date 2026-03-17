from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditEventView, AuditService
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository


@dataclass(frozen=True, slots=True)
class LiveOrderRecoveryReport:
    unresolved_orders: list[OrderRecord]
    recovery_events: list[AuditEventView]


class LiveOrderRecoveryReportService:
    _recovery_event_types = {"live_reconcile", "live_cancel"}
    _recovery_sources = {"job.startup_state_sync", "job.live_reconcile", "api.control"}

    def __init__(self, session: Session) -> None:
        self._orders = OrderRepository(session)
        self._audit = AuditService(session=session)

    def build_report(
        self,
        *,
        order_limit: int = 25,
        audit_limit: int = 10,
    ) -> LiveOrderRecoveryReport:
        unresolved_orders = self._orders.list_live_orders_by_status(
            statuses=("submitting", "submitted", "new", "partially_filled"),
            limit=order_limit,
        )
        recovery_events = [
            event
            for event in self._audit.list_recent(limit=50)
            if event.event_type in self._recovery_event_types
            and event.source in self._recovery_sources
        ][:audit_limit]
        return LiveOrderRecoveryReport(
            unresolved_orders=unresolved_orders,
            recovery_events=recovery_events,
        )

    @staticmethod
    def latest_event_summary(
        events: list[AuditEventView],
    ) -> tuple[datetime | None, str | None, str | None]:
        if not events:
            return None, None, None
        latest = events[0]
        return latest.created_at, latest.event_type, latest.status
