from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditEventFilters
from app.application.services.live_order_recovery_report_service import RecoveryReportFilters
from app.application.services.reporting_export_service import ReportingExportService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session, get_session_factory_dependency

router = APIRouter(prefix="/reports", tags=["reports"])
session_dependency = Depends(get_session)
settings_dependency = Depends(get_settings)
session_factory_dependency = Depends(get_session_factory_dependency)


def _csv_response(filename: str, content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_recovery_filters(
    *,
    order_status: str | None,
    requires_review: bool | None,
    event_type: str | None,
    search: str | None,
) -> RecoveryReportFilters:
    return RecoveryReportFilters(
        order_status=order_status.strip() if order_status and order_status.strip() else None,
        requires_review=requires_review,
        event_type=event_type.strip() if event_type and event_type.strip() else None,
        search=search.strip() if search and search.strip() else None,
    )


def _build_notification_filters(
    *,
    status: str | None,
    channel: str | None,
    related_event_type: str | None,
) -> AuditEventFilters:
    return AuditEventFilters(
        event_type="notification_delivery",
        status=status.strip() if status and status.strip() else None,
        channel=channel.strip() if channel and channel.strip() else None,
        related_event_type=(
            related_event_type.strip()
            if related_event_type and related_event_type.strip()
            else None
        ),
    )


def _build_audit_filters(
    *,
    event_type: str | None,
    status: str | None,
    source: str | None,
    search: str | None,
) -> AuditEventFilters:
    return AuditEventFilters(
        event_type=event_type.strip() if event_type and event_type.strip() else None,
        status=status.strip() if status and status.strip() else None,
        source=source.strip() if source and source.strip() else None,
        search=search.strip().lower() if search and search.strip() else None,
    )


@router.get("/positions.csv")
def export_positions(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
) -> Response:
    content = ReportingExportService(session, settings).export_positions_csv()
    return _csv_response("positions.csv", content)


@router.get("/trades.csv")
def export_trades(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Response:
    content = ReportingExportService(session, settings).export_trades_csv(limit=limit)
    return _csv_response("trades.csv", content)


@router.get("/backtest-summary.csv")
def export_backtest_summary(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> Response:
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_backtest_summary_csv()
    return _csv_response("backtest-summary.csv", content)


@router.get("/audit.csv")
def export_audit_events(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    audit_event_type: str | None = None,
    audit_status: str | None = None,
    audit_source: str | None = None,
    audit_search: str | None = None,
) -> Response:
    filters = _build_audit_filters(
        event_type=audit_event_type,
        status=audit_status,
        source=audit_source,
        search=audit_search,
    )
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_audit_events_csv(limit=limit, filters=filters)
    return _csv_response("audit.csv", content)


@router.get("/notification-delivery.csv")
def export_notification_delivery(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    notification_status: str | None = None,
    notification_channel: str | None = None,
    notification_related_event_type: str | None = None,
) -> Response:
    filters = _build_notification_filters(
        status=notification_status,
        channel=notification_channel,
        related_event_type=notification_related_event_type,
    )
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_notification_delivery_csv(limit=limit, filters=filters)
    return _csv_response("notification-delivery.csv", content)


@router.get("/live-recovery.csv")
def export_live_recovery(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    recovery_order_status: str | None = None,
    recovery_requires_review: bool | None = None,
    recovery_event_type: str | None = None,
    recovery_search: str | None = None,
) -> Response:
    filters = _build_recovery_filters(
        order_status=recovery_order_status,
        requires_review=recovery_requires_review,
        event_type=recovery_event_type,
        search=recovery_search,
    )
    content = ReportingExportService(
        session,
        settings,
        session_factory=session_factory,
    ).export_live_recovery_csv(filters=filters)
    return _csv_response("live-recovery.csv", content)
