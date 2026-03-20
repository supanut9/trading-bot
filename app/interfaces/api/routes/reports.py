from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditEventFilters
from app.application.services.backtest_run_history_service import BacktestRunHistoryService
from app.application.services.live_order_recovery_report_service import RecoveryReportFilters
from app.application.services.live_performance_review_service import LivePerformanceReviewService
from app.application.services.operator_runtime_config_service import OperatorRuntimeConfigService
from app.application.services.reporting_dashboard_service import ReportingDashboardService
from app.application.services.reporting_export_service import ReportingExportService
from app.application.services.shadow_report_service import ShadowReportService
from app.application.services.status_service import StatusService
from app.config import Settings, get_settings
from app.infrastructure.database.session import get_session, get_session_factory_dependency
from app.interfaces.api.schemas import (
    AuditDashboardResponse,
    AuditEventResponse,
    AuditReportFiltersResponse,
    BacktestRunHistoryResponse,
    BacktestRunResponse,
    LivePerformanceReviewResponse,
    NotificationDashboardResponse,
    NotificationReportFiltersResponse,
    RecoveryDashboardResponse,
    RecoveryEventResponse,
    RecoveryOrderResponse,
    RecoveryReportFiltersResponse,
    ShadowQualityReportResponse,
    StaleLiveOrderResponse,
    StrategyRuleBuilderRequest,
)

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


@router.get("/backtest-runs", response_model=BacktestRunHistoryResponse)
def get_backtest_runs(
    session: Session = session_dependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BacktestRunHistoryResponse:
    runs = BacktestRunHistoryService(session=session).list_recent(limit=limit)
    return BacktestRunHistoryResponse(
        run_count=len(runs),
        runs=[
            BacktestRunResponse(
                id=run.id,
                created_at=run.created_at,
                source=run.source,
                status=run.status,
                detail=run.detail,
                strategy_name=run.strategy_name,
                exchange=run.exchange,
                symbol=run.symbol,
                timeframe=run.timeframe,
                fast_period=run.fast_period,
                slow_period=run.slow_period,
                starting_equity_input=run.starting_equity_input,
                candle_count=run.candle_count,
                required_candles=run.required_candles,
                starting_equity=run.starting_equity,
                ending_equity=run.ending_equity,
                realized_pnl=run.realized_pnl,
                total_return_pct=run.total_return_pct,
                max_drawdown_pct=run.max_drawdown_pct,
                total_trades=run.total_trades,
                winning_trades=run.winning_trades,
                losing_trades=run.losing_trades,
                rules=(
                    StrategyRuleBuilderRequest.model_validate(run.rules_payload)
                    if run.rules_payload is not None
                    else None
                ),
            )
            for run in runs
        ],
    )


@router.get("/recovery", response_model=RecoveryDashboardResponse)
def get_recovery_dashboard(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    recovery_order_status: str | None = None,
    recovery_requires_review: bool | None = None,
    recovery_event_type: str | None = None,
    recovery_search: str | None = None,
) -> RecoveryDashboardResponse:
    filters = _build_recovery_filters(
        order_status=recovery_order_status,
        requires_review=recovery_requires_review,
        event_type=recovery_event_type,
        search=recovery_search,
    )
    dashboard = ReportingDashboardService(
        session,
        settings,
        session_factory=session_factory,
        recovery_filters=filters,
    ).build_dashboard()
    status = StatusService(settings, session=session).get_status()
    return RecoveryDashboardResponse(
        live_trading_enabled=dashboard.live_trading_enabled,
        live_trading_halted=dashboard.live_trading_halted,
        live_safety_status=str(status["live_safety_status"]),
        stale_threshold_minutes=settings.stale_live_order_threshold_minutes,
        stale_live_orders=[
            StaleLiveOrderResponse.model_validate(order) for order in dashboard.stale_live_orders
        ],
        unresolved_orders=[
            RecoveryOrderResponse(
                id=order.order.id,
                symbol=order.order.symbol,
                side=order.order.side,
                status=order.order.status,
                client_order_id=order.order.client_order_id,
                exchange_order_id=order.order.exchange_order_id,
                quantity=order.order.quantity,
                price=order.order.price,
                updated_at=order.order.updated_at,
                requires_operator_review=order.requires_operator_review,
                next_action=order.next_action,
            )
            for order in dashboard.recovery_orders
        ],
        recovery_events=[
            RecoveryEventResponse.model_validate(event) for event in dashboard.recovery_events
        ],
        unresolved_live_orders=dashboard.unresolved_live_orders,
        recovery_event_count=dashboard.recovery_event_count,
        latest_recovery_event_at=dashboard.latest_recovery_event_at,
        latest_recovery_event_type=dashboard.latest_recovery_event_type,
        latest_recovery_event_status=dashboard.latest_recovery_event_status,
        latest_recovery_event_context=dashboard.latest_recovery_event_context,
        filters=RecoveryReportFiltersResponse(
            order_status=dashboard.recovery_filters.order_status,
            requires_review=dashboard.recovery_filters.requires_review,
            event_type=dashboard.recovery_filters.event_type,
            search=dashboard.recovery_filters.search,
        ),
    )


@router.get("/notifications", response_model=NotificationDashboardResponse)
def get_notification_dashboard(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    notification_status: str | None = None,
    notification_channel: str | None = None,
    notification_related_event_type: str | None = None,
) -> NotificationDashboardResponse:
    filters = _build_notification_filters(
        status=notification_status,
        channel=notification_channel,
        related_event_type=notification_related_event_type,
    )
    dashboard = ReportingDashboardService(
        session,
        settings,
        session_factory=session_factory,
        notification_filters=filters,
    ).build_dashboard()
    return NotificationDashboardResponse(
        delivery_count=dashboard.notification_delivery_count,
        failed_count=dashboard.notification_delivery_failed_count,
        latest_delivery_at=dashboard.latest_notification_delivery_at,
        latest_delivery_status=dashboard.latest_notification_delivery_status,
        latest_delivery_channel=dashboard.latest_notification_delivery_channel,
        latest_related_event_type=dashboard.latest_notification_related_event_type,
        filters=NotificationReportFiltersResponse(
            status=dashboard.notification_filters.status,
            channel=dashboard.notification_filters.channel,
            related_event_type=dashboard.notification_filters.related_event_type,
        ),
        events=[
            AuditEventResponse.model_validate(event)
            for event in dashboard.notification_delivery_events
        ],
    )


@router.get("/audit", response_model=AuditDashboardResponse)
def get_audit_dashboard(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    audit_event_type: str | None = None,
    audit_status: str | None = None,
    audit_source: str | None = None,
    audit_search: str | None = None,
) -> AuditDashboardResponse:
    filters = _build_audit_filters(
        event_type=audit_event_type,
        status=audit_status,
        source=audit_source,
        search=audit_search,
    )
    dashboard = ReportingDashboardService(
        session,
        settings,
        session_factory=session_factory,
        audit_filters=filters,
    ).build_dashboard()
    return AuditDashboardResponse(
        event_count=len(dashboard.audit_events),
        filters=AuditReportFiltersResponse(
            event_type=dashboard.audit_filters.event_type,
            status=dashboard.audit_filters.status,
            source=dashboard.audit_filters.source,
            search=dashboard.audit_filters.search,
        ),
        events=[AuditEventResponse.model_validate(event) for event in dashboard.audit_events],
    )


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


@router.get("/backtest-runs.csv")
def export_backtest_runs(
    session: Session = session_dependency,
    settings: Settings = settings_dependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Response:
    content = ReportingExportService(session, settings).export_backtest_runs_csv(limit=limit)
    return _csv_response("backtest-runs.csv", content)


@router.get("/shadow", response_model=ShadowQualityReportResponse, status_code=200)
def get_shadow_report(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
) -> ShadowQualityReportResponse:
    with session_factory() as session:
        config = OperatorRuntimeConfigService(session, settings).get_effective_config()
        report = ShadowReportService(session).get_quality_report(
            exchange=settings.exchange_name,
            symbol=config.symbol,
        )
    return ShadowQualityReportResponse.model_validate(report, from_attributes=True)


@router.get("/performance-review", response_model=LivePerformanceReviewResponse, status_code=200)
def get_performance_review(
    settings: Settings = settings_dependency,
    session_factory: sessionmaker[Session] = session_factory_dependency,
    review_period_days: int = 30,
) -> LivePerformanceReviewResponse:
    with session_factory() as session:
        config = OperatorRuntimeConfigService(session, settings).get_effective_config()
        review = LivePerformanceReviewService(session).get_performance_review(
            exchange=settings.exchange_name,
            symbol=config.symbol,
            review_period_days=review_period_days,
        )
    return LivePerformanceReviewResponse.model_validate(review, from_attributes=True)


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
