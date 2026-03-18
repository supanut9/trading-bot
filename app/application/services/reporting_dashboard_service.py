import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditEventView, AuditService
from app.application.services.live_order_recovery_report_service import (
    LiveOrderRecoveryReportService,
    RecoveryOrderView,
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
    symbol: str
    timeframe: str
    paper_trading: bool
    live_trading_enabled: bool
    live_trading_halted: bool
    database_status: str
    latest_price_status: str
    latest_price: str | None
    position_count: int
    trade_count: int
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    positions: list[PositionView]
    trades: list[TradeView]
    stale_live_orders: list[StaleLiveOrderView]
    recovery_orders: list[RecoveryOrderView]
    recovery_events: list[AuditEventView]
    unresolved_live_orders: int
    recovery_event_count: int
    latest_recovery_event_at: str | None
    latest_recovery_event_type: str | None
    latest_recovery_event_status: str | None
    latest_worker_event_at: str | None
    latest_worker_event_status: str | None
    latest_worker_event_detail: str | None
    latest_worker_signal_action: str | None
    latest_worker_client_order_id: str | None
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
    ) -> None:
        self._session = session
        self._operations = OperationsService(session)
        self._audit = AuditService(session=session)
        self._stale_orders = StaleLiveOrderService(session)
        self._recovery_report = LiveOrderRecoveryReportService(session)
        self._performance = PerformanceAnalyticsService(session)
        self._settings = settings
        self._session_factory = session_factory

    def build_dashboard(self) -> ReportingDashboard:
        status = StatusService(self._settings, session=self._session).get_status()
        positions = self._operations.list_positions()
        trades = self._operations.list_trades(limit=10)
        stale_live_orders = self._stale_orders.list_stale_orders(
            threshold_minutes=self._settings.stale_live_order_threshold_minutes,
            limit=10,
        )
        recovery_report = self._recovery_report.build_report(order_limit=25, audit_limit=10)
        latest_recovery_at, latest_recovery_type, latest_recovery_status = (
            self._recovery_report.latest_event_summary(recovery_report.recovery_events)
        )
        backtest = OperationalControlService(
            self._settings,
            session_factory=self._session_factory,
        ).run_backtest(notify=False, audit=False, source="reporting.snapshot")
        audit_events = self._audit.list_recent(limit=10)
        analytics = self._performance.build()
        (
            latest_worker_event_at,
            latest_worker_event_status,
            latest_worker_event_detail,
            latest_worker_signal_action,
            latest_worker_client_order_id,
        ) = self._latest_worker_summary(audit_events)

        return ReportingDashboard(
            app_name=str(status["app"]),
            environment=str(status["environment"]),
            exchange=str(status["exchange"]),
            symbol=str(status["symbol"]),
            timeframe=str(status["timeframe"]),
            paper_trading=bool(status["paper_trading"]),
            live_trading_enabled=bool(status["live_trading_enabled"]),
            live_trading_halted=bool(status["live_trading_halted"]),
            database_status=str(status["database_status"]),
            latest_price_status=str(status["latest_price_status"]),
            latest_price=(
                str(status["latest_price"]) if status["latest_price"] is not None else None
            ),
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
            latest_worker_event_at=latest_worker_event_at,
            latest_worker_event_status=latest_worker_event_status,
            latest_worker_event_detail=latest_worker_event_detail,
            latest_worker_signal_action=latest_worker_signal_action,
            latest_worker_client_order_id=latest_worker_client_order_id,
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
