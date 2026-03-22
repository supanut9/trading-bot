import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditEventView, AuditService
from app.application.services.live_order_state import (
    UNRESOLVED_LIVE_ORDER_STATUSES,
    requires_operator_review,
)
from app.application.services.live_recovery_state import (
    classify_recovery_state,
    next_action_for_recovery_state,
)
from app.config import Settings
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository


@dataclass(frozen=True, slots=True)
class RecoveryOrderView:
    order: OrderRecord
    recovery_state: str
    requires_operator_review: bool
    next_action: str


@dataclass(frozen=True, slots=True)
class LiveOrderRecoveryReport:
    unresolved_orders: list[RecoveryOrderView]
    recovery_events: list["RecoveryEventView"]


@dataclass(frozen=True, slots=True)
class RecoveryReportFilters:
    order_status: str | None = None
    requires_review: bool | None = None
    event_type: str | None = None
    search: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryEventView:
    created_at: datetime
    event_type: str
    source: str
    status: str
    detail: str
    context: str


class LiveOrderRecoveryReportService:
    _recovery_event_types = {"live_reconcile", "live_cancel"}
    _recovery_sources = {"job.startup_state_sync", "job.live_reconcile", "api.control"}

    def __init__(self, session: Session, settings: Settings) -> None:
        self._orders = OrderRepository(session)
        self._audit = AuditService(session=session)
        self._settings = settings

    def build_report(
        self,
        *,
        order_limit: int = 25,
        audit_limit: int = 10,
        filters: RecoveryReportFilters | None = None,
    ) -> LiveOrderRecoveryReport:
        active_filters = filters or RecoveryReportFilters()
        unresolved_records = self._orders.list_live_orders_by_status(
            statuses=UNRESOLVED_LIVE_ORDER_STATUSES,
            limit=order_limit,
        )
        unresolved_orders = [
            RecoveryOrderView(
                order=order,
                recovery_state=self._recovery_state(order),
                requires_operator_review=requires_operator_review(order.status),
                next_action=next_action_for_recovery_state(self._recovery_state(order)),
            )
            for order in unresolved_records
        ]
        unresolved_orders = self._filter_orders(unresolved_orders, active_filters)
        recovery_events = [
            self._to_recovery_event_view(event)
            for event in self._audit.list_recent(limit=50)
            if event.event_type in self._recovery_event_types
            and event.source in self._recovery_sources
        ][:audit_limit]
        recovery_events = self._filter_events(recovery_events, active_filters)
        return LiveOrderRecoveryReport(
            unresolved_orders=unresolved_orders,
            recovery_events=recovery_events,
        )

    @staticmethod
    def _filter_orders(
        orders: list[RecoveryOrderView],
        filters: RecoveryReportFilters,
    ) -> list[RecoveryOrderView]:
        filtered = orders
        if filters.order_status is not None:
            filtered = [order for order in filtered if order.order.status == filters.order_status]
        if filters.requires_review is not None:
            filtered = [
                order
                for order in filtered
                if order.requires_operator_review == filters.requires_review
            ]
        if not filters.search:
            return filtered
        term = filters.search.strip().lower()
        if not term:
            return filtered
        return [
            order
            for order in filtered
            if term
            in " ".join(
                [
                    str(order.order.id),
                    order.order.symbol,
                    order.order.side,
                    order.order.status,
                    order.order.client_order_id or "",
                    order.order.exchange_order_id or "",
                    order.recovery_state,
                    order.next_action,
                ]
            ).lower()
        ]

    @staticmethod
    def _filter_events(
        events: list[RecoveryEventView],
        filters: RecoveryReportFilters,
    ) -> list[RecoveryEventView]:
        filtered = events
        if filters.event_type is not None:
            filtered = [event for event in filtered if event.event_type == filters.event_type]
        if filters.order_status is not None:
            filtered = [event for event in filtered if event.status == filters.order_status]
        if not filters.search:
            return filtered
        term = filters.search.strip().lower()
        if not term:
            return filtered
        return [
            event
            for event in filtered
            if term
            in " ".join(
                [
                    event.event_type,
                    event.source,
                    event.status,
                    event.detail,
                    event.context,
                ]
            ).lower()
        ]

    def _to_recovery_event_view(self, event: AuditEventView) -> RecoveryEventView:
        payload: dict[str, object] = {}
        if event.payload_json:
            payload = json.loads(event.payload_json)
        return RecoveryEventView(
            created_at=event.created_at,
            event_type=event.event_type,
            source=event.source,
            status=event.status,
            detail=event.detail,
            context=self._event_context(event.event_type, payload),
        )

    @staticmethod
    def _event_context(event_type: str, payload: dict[str, object]) -> str:
        if event_type == "live_reconcile":
            return LiveOrderRecoveryReportService._format_fields(
                [
                    ("reconciled", payload.get("reconciled_count")),
                    ("filled", payload.get("filled_count")),
                    ("review_required", payload.get("review_required_count")),
                ]
            )
        if event_type == "live_cancel":
            return LiveOrderRecoveryReportService._format_fields(
                [
                    ("order_id", payload.get("order_id")),
                    ("client_order_id", payload.get("client_order_id")),
                    ("exchange_order_id", payload.get("exchange_order_id")),
                    ("order_status", payload.get("order_status")),
                ]
            )
        return "-"

    @staticmethod
    def _format_fields(fields: list[tuple[str, object]]) -> str:
        values = [f"{name}={value}" for name, value in fields if value not in {None, ""}]
        if not values:
            return "-"
        return " ".join(values)

    def _recovery_state(self, order: OrderRecord) -> str:
        return classify_recovery_state(
            status=order.status,
            updated_at=order.updated_at,
            stale_threshold_minutes=self._settings.stale_live_order_threshold_minutes,
        )

    @staticmethod
    def latest_event_summary(
        events: list[RecoveryEventView],
    ) -> tuple[datetime | None, str | None, str | None, str | None]:
        if not events:
            return None, None, None, None
        latest = events[0]
        return latest.created_at, latest.event_type, latest.status, latest.context
