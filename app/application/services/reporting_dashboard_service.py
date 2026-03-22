import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import (
    AuditEventFilters,
    AuditEventView,
    AuditService,
)
from app.application.services.live_order_recovery_report_service import (
    LiveOrderRecoveryReportService,
    RecoveryEventView,
    RecoveryOrderView,
    RecoveryReportFilters,
)
from app.application.services.operational_control_service import (
    BacktestControlResult,
    OperationalControlService,
)
from app.application.services.operations_service import OperationsService, PositionView, TradeView
from app.application.services.performance_analytics_service import (
    DailyPerformanceRow,
    EquityCurvePoint,
    PerformanceAnalyticsService,
    PerformanceSummary,
)
from app.application.services.stale_live_order_service import (
    StaleLiveOrderService,
    StaleLiveOrderView,
)
from app.application.services.status_service import StatusService
from app.config import Settings


@dataclass(frozen=True, slots=True)
class ReportingDashboard:
    app_name: str
    environment: str
    exchange: str
    strategy_name: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    operator_config_source: str
    paper_trading: bool
    live_trading_enabled: bool
    live_trading_halted: bool
    database_status: str
    latest_price_status: str
    latest_price: str | None
    recovery_filters: RecoveryReportFilters
    notification_filters: AuditEventFilters
    audit_filters: AuditEventFilters
    position_count: int
    trade_count: int
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    positions: list[PositionView]
    trades: list[TradeView]
    stale_live_orders: list[StaleLiveOrderView]
    recovery_orders: list[RecoveryOrderView]
    recovery_events: list[RecoveryEventView]
    unresolved_live_orders: int
    recovery_event_count: int
    latest_recovery_event_at: str | None
    latest_recovery_event_type: str | None
    latest_recovery_event_status: str | None
    latest_recovery_event_context: str | None
    latest_worker_event_at: str | None
    latest_worker_event_status: str | None
    latest_worker_event_detail: str | None
    latest_worker_signal_action: str | None
    latest_worker_client_order_id: str | None
    notification_delivery_count: int
    notification_delivery_failed_count: int
    latest_notification_delivery_at: str | None
    latest_notification_delivery_status: str | None
    latest_notification_delivery_channel: str | None
    latest_notification_related_event_type: str | None
    notification_delivery_events: list[AuditEventView]
    performance_summaries: list[PerformanceSummary]
    performance_equity_curve: list[EquityCurvePoint]
    performance_daily_rows: list[DailyPerformanceRow]
    backtest: BacktestControlResult
    audit_events: list[AuditEventView]


class ReportingDashboardService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
        recovery_filters: RecoveryReportFilters | None = None,
        notification_filters: AuditEventFilters | None = None,
        audit_filters: AuditEventFilters | None = None,
    ) -> None:
        self._session = session
        self._operations = OperationsService(session)
        self._audit = AuditService(session=session)
        self._stale_orders = StaleLiveOrderService(session)
        self._recovery_report = LiveOrderRecoveryReportService(session, settings)
        self._performance = PerformanceAnalyticsService(session)
        self._settings = settings
        self._session_factory = session_factory
        self._recovery_filters = recovery_filters or RecoveryReportFilters()
        self._notification_filters = notification_filters or AuditEventFilters(
            event_type="notification_delivery"
        )
        self._audit_filters = audit_filters or AuditEventFilters()

    def build_dashboard(self) -> ReportingDashboard:
        status = StatusService(self._settings, session=self._session).get_status()
        positions = self._operations.list_positions()
        trades = self._operations.list_trades(limit=10)
        stale_live_orders = self._stale_orders.list_stale_orders(
            threshold_minutes=self._settings.stale_live_order_threshold_minutes,
            limit=10,
        )
        recovery_report = self._recovery_report.build_report(
            order_limit=25,
            audit_limit=10,
            filters=self._recovery_filters,
        )
        (
            latest_recovery_at,
            latest_recovery_type,
            latest_recovery_status,
            latest_recovery_context,
        ) = self._recovery_report.latest_event_summary(recovery_report.recovery_events)
        backtest = OperationalControlService(
            self._settings,
            session_factory=self._session_factory,
        ).run_backtest(
            notify=False,
            audit=False,
            record_history=False,
            source="reporting.snapshot",
        )
        audit_events = self._audit.list_recent(limit=10, filters=self._audit_filters)
        notification_delivery_events = self._audit.list_recent(
            limit=10,
            filters=self._notification_filters,
        )
        analytics = self._performance.build()
        (
            latest_worker_event_at,
            latest_worker_event_status,
            latest_worker_event_detail,
            latest_worker_signal_action,
            latest_worker_client_order_id,
        ) = self._latest_worker_summary(audit_events)
        (
            latest_notification_delivery_at,
            latest_notification_delivery_status,
            latest_notification_delivery_channel,
            latest_notification_related_event_type,
        ) = self._latest_notification_delivery_summary(notification_delivery_events)

        return ReportingDashboard(
            app_name=str(status["app"]),
            environment=str(status["environment"]),
            exchange=str(status["exchange"]),
            strategy_name=str(status["strategy_name"]),
            symbol=str(status["symbol"]),
            timeframe=str(status["timeframe"]),
            fast_period=int(status["fast_period"]),
            slow_period=int(status["slow_period"]),
            operator_config_source=str(status["operator_config_source"]),
            paper_trading=bool(status["paper_trading"]),
            live_trading_enabled=bool(status["live_trading_enabled"]),
            live_trading_halted=bool(status["live_trading_halted"]),
            database_status=str(status["database_status"]),
            latest_price_status=str(status["latest_price_status"]),
            latest_price=(
                str(status["latest_price"]) if status["latest_price"] is not None else None
            ),
            recovery_filters=self._recovery_filters,
            notification_filters=self._notification_filters,
            audit_filters=self._audit_filters,
            position_count=len(positions),
            trade_count=len(trades),
            total_realized_pnl=sum(
                (position.realized_pnl for position in positions),
                Decimal("0"),
            ),
            total_unrealized_pnl=sum(
                (position.unrealized_pnl for position in positions),
                Decimal("0"),
            ),
            positions=positions,
            trades=trades,
            stale_live_orders=stale_live_orders,
            recovery_orders=recovery_report.unresolved_orders[:10],
            recovery_events=recovery_report.recovery_events,
            unresolved_live_orders=len(recovery_report.unresolved_orders),
            recovery_event_count=len(recovery_report.recovery_events),
            latest_recovery_event_at=(
                latest_recovery_at.isoformat() if latest_recovery_at is not None else None
            ),
            latest_recovery_event_type=latest_recovery_type,
            latest_recovery_event_status=latest_recovery_status,
            latest_recovery_event_context=latest_recovery_context,
            latest_worker_event_at=latest_worker_event_at,
            latest_worker_event_status=latest_worker_event_status,
            latest_worker_event_detail=latest_worker_event_detail,
            latest_worker_signal_action=latest_worker_signal_action,
            latest_worker_client_order_id=latest_worker_client_order_id,
            notification_delivery_count=len(notification_delivery_events),
            notification_delivery_failed_count=sum(
                1 for event in notification_delivery_events if event.status == "failed"
            ),
            latest_notification_delivery_at=latest_notification_delivery_at,
            latest_notification_delivery_status=latest_notification_delivery_status,
            latest_notification_delivery_channel=latest_notification_delivery_channel,
            latest_notification_related_event_type=latest_notification_related_event_type,
            notification_delivery_events=notification_delivery_events,
            performance_summaries=analytics.summaries,
            performance_equity_curve=analytics.equity_curve,
            performance_daily_rows=analytics.daily_rows[:7],
            backtest=backtest,
            audit_events=audit_events,
        )

    @staticmethod
    def _latest_worker_summary(
        audit_events: list[AuditEventView],
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        for event in audit_events:
            if event.event_type != "worker_cycle":
                continue
            payload: dict[str, object] = {}
            if event.payload_json:
                payload = json.loads(event.payload_json)
            signal_action = payload.get("signal_action")
            client_order_id = payload.get("client_order_id")
            return (
                event.created_at.isoformat(),
                event.status,
                event.detail,
                str(signal_action) if signal_action is not None else None,
                str(client_order_id) if client_order_id is not None else None,
            )
        return (None, None, None, None, None)

    @staticmethod
    def _latest_notification_delivery_summary(
        audit_events: list[AuditEventView],
    ) -> tuple[str | None, str | None, str | None, str | None]:
        if not audit_events:
            return (None, None, None, None)
        event = audit_events[0]
        return (
            event.created_at.isoformat(),
            event.status,
            event.channel,
            event.related_event_type,
        )
