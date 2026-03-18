from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditEventView, AuditService
from app.application.services.live_order_state import (
    UNRESOLVED_LIVE_ORDER_STATUSES,
    requires_operator_review,
)
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository


@dataclass(frozen=True, slots=True)
class RecoveryOrderView:
    order: OrderRecord
    requires_operator_review: bool
    next_action: str


@dataclass(frozen=True, slots=True)
class LiveOrderRecoveryReport:
    unresolved_orders: list[RecoveryOrderView]
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
        unresolved_records = self._orders.list_live_orders_by_status(
            statuses=UNRESOLVED_LIVE_ORDER_STATUSES,
            limit=order_limit,
        )
        unresolved_orders = [
            RecoveryOrderView(
                order=order,
                requires_operator_review=requires_operator_review(order.status),
                next_action=self._next_action(order.status),
            )
            for order in unresolved_records
        ]
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
    def _next_action(status: str) -> str:
        if status == "review_required":
            return "inspect_exchange_state"
        if status in {"submitting", "submitted", "open", "partially_filled"}:
            return "reconcile_or_cancel"
        return "none"

    @staticmethod
    def latest_event_summary(
        events: list[AuditEventView],
    ) -> tuple[datetime | None, str | None, str | None]:
        if not events:
            return None, None, None
        latest = events[0]
        return latest.created_at, latest.event_type, latest.status
