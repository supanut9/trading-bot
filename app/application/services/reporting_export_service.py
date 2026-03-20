import csv
from io import StringIO

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditEventFilters, AuditService
from app.application.services.backtest_run_history_service import BacktestRunHistoryService
from app.application.services.live_order_recovery_report_service import (
    LiveOrderRecoveryReportService,
    RecoveryReportFilters,
)
from app.application.services.operational_control_service import OperationalControlService
from app.application.services.operations_service import OperationsService
from app.application.services.performance_analytics_service import PerformanceAnalyticsService
from app.config import Settings


class ReportingExportService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._audit = AuditService(session=session)
        self._backtest_runs = BacktestRunHistoryService(session=session)
        self._recovery = LiveOrderRecoveryReportService(session)
        self._operations = OperationsService(session)
        self._performance = PerformanceAnalyticsService(session)
        self._settings = settings
        self._session_factory = session_factory

    def export_positions_csv(self) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "exchange",
                "symbol",
                "side",
                "mode",
                "quantity",
                "average_entry_price",
                "realized_pnl",
                "unrealized_pnl",
            ]
        )
        for position in self._operations.list_positions():
            writer.writerow(
                [
                    position.exchange,
                    position.symbol,
                    position.side,
                    position.mode,
                    position.quantity,
                    position.average_entry_price,
                    position.realized_pnl,
                    position.unrealized_pnl,
                ]
            )
        return output.getvalue()

    def export_trades_csv(self, *, limit: int = 100) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "order_id",
                "exchange",
                "symbol",
                "side",
                "quantity",
                "price",
                "fee_amount",
                "fee_asset",
            ]
        )
        for trade in self._operations.list_trades(limit=limit):
            writer.writerow(
                [
                    trade.id,
                    trade.order_id,
                    trade.exchange,
                    trade.symbol,
                    trade.side,
                    trade.quantity,
                    trade.price,
                    trade.fee_amount,
                    trade.fee_asset,
                ]
            )
        return output.getvalue()

    def export_backtest_summary_csv(self) -> str:
        result = OperationalControlService(
            self._settings,
            session_factory=self._session_factory,
        ).run_backtest(
            notify=False,
            audit=False,
            record_history=False,
            source="reporting.snapshot",
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "status",
                "detail",
                "candle_count",
                "required_candles",
                "starting_equity",
                "ending_equity",
                "realized_pnl",
                "total_return_pct",
                "max_drawdown_pct",
                "total_trades",
                "winning_trades",
                "losing_trades",
            ]
        )
        writer.writerow(
            [
                result.status,
                result.detail,
                result.candle_count,
                result.required_candles,
                result.starting_equity,
                result.ending_equity,
                result.realized_pnl,
                result.total_return_pct,
                result.max_drawdown_pct,
                result.total_trades,
                result.winning_trades,
                result.losing_trades,
            ]
        )
        return output.getvalue()

    def export_backtest_runs_csv(self, *, limit: int = 20) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "source",
                "status",
                "detail",
                "strategy_name",
                "exchange",
                "symbol",
                "timeframe",
                "fast_period",
                "slow_period",
                "starting_equity_input",
                "candle_count",
                "required_candles",
                "starting_equity",
                "ending_equity",
                "realized_pnl",
                "total_return_pct",
                "max_drawdown_pct",
                "total_trades",
                "winning_trades",
                "losing_trades",
                "rules_json",
            ]
        )
        for run in self._backtest_runs.list_recent(limit=limit):
            writer.writerow(
                [
                    run.id,
                    run.created_at.isoformat(),
                    run.source,
                    run.status,
                    run.detail,
                    run.strategy_name,
                    run.exchange,
                    run.symbol,
                    run.timeframe,
                    run.fast_period,
                    run.slow_period,
                    run.starting_equity_input,
                    run.candle_count,
                    run.required_candles,
                    run.starting_equity,
                    run.ending_equity,
                    run.realized_pnl,
                    run.total_return_pct,
                    run.max_drawdown_pct,
                    run.total_trades,
                    run.winning_trades,
                    run.losing_trades,
                    run.rules_payload,
                ]
            )
        return output.getvalue()

    def export_audit_events_csv(
        self,
        *,
        limit: int = 100,
        filters: AuditEventFilters | None = None,
    ) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "event_type",
                "source",
                "status",
                "detail",
                "exchange",
                "symbol",
                "timeframe",
                "channel",
                "related_event_type",
                "correlation_id",
                "payload_json",
            ]
        )
        for event in self._audit.list_recent(limit=limit, filters=filters):
            writer.writerow(
                [
                    event.id,
                    event.created_at.isoformat(),
                    event.event_type,
                    event.source,
                    event.status,
                    event.detail,
                    event.exchange,
                    event.symbol,
                    event.timeframe,
                    event.channel,
                    event.related_event_type,
                    event.correlation_id,
                    event.payload_json,
                ]
            )
        return output.getvalue()

    def export_notification_delivery_csv(
        self,
        *,
        limit: int = 100,
        filters: AuditEventFilters | None = None,
    ) -> str:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "status",
                "channel",
                "related_event_type",
                "detail",
                "exchange",
                "symbol",
                "timeframe",
                "payload_json",
            ]
        )
        active_filters = filters or AuditEventFilters()
        delivery_filters = AuditEventFilters(
            event_type="notification_delivery",
            status=active_filters.status,
            channel=active_filters.channel,
            related_event_type=active_filters.related_event_type,
        )
        for event in self._audit.list_recent(limit=limit, filters=delivery_filters):
            writer.writerow(
                [
                    event.id,
                    event.created_at.isoformat(),
                    event.status,
                    event.channel,
                    event.related_event_type,
                    event.detail,
                    event.exchange,
                    event.symbol,
                    event.timeframe,
                    event.payload_json,
                ]
            )
        return output.getvalue()

    def export_live_recovery_csv(
        self,
        *,
        filters: RecoveryReportFilters | None = None,
    ) -> str:
        report = self._recovery.build_report(order_limit=50, audit_limit=10, filters=filters)
        latest_at, latest_type, latest_status, latest_context = self._recovery.latest_event_summary(
            report.recovery_events
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "order_id",
                "exchange",
                "symbol",
                "side",
                "status",
                "client_order_id",
                "exchange_order_id",
                "updated_at",
                "latest_recovery_event_at",
                "latest_recovery_event_type",
                "latest_recovery_event_status",
                "latest_recovery_event_context",
                "requires_operator_review",
                "next_action",
            ]
        )
        for order in report.unresolved_orders:
            writer.writerow(
                [
                    order.order.id,
                    order.order.exchange,
                    order.order.symbol,
                    order.order.side,
                    order.order.status,
                    order.order.client_order_id,
                    order.order.exchange_order_id,
                    order.order.updated_at.isoformat(),
                    latest_at.isoformat() if latest_at is not None else None,
                    latest_type,
                    latest_status,
                    latest_context,
                    str(order.requires_operator_review).lower(),
                    order.next_action,
                ]
            )
        return output.getvalue()

    def export_performance_daily_csv(self) -> str:
        analytics = self._performance.build()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "mode",
                "trade_date",
                "trade_count",
                "closed_trade_count",
                "winning_trades",
                "losing_trades",
                "realized_pnl",
                "fees",
                "net_pnl",
            ]
        )
        for row in analytics.daily_rows:
            writer.writerow(
                [
                    row.mode,
                    row.trade_date.isoformat(),
                    row.trade_count,
                    row.closed_trade_count,
                    row.winning_trades,
                    row.losing_trades,
                    row.realized_pnl,
                    row.fees,
                    row.net_pnl,
                ]
            )
        return output.getvalue()

    def export_performance_equity_csv(self) -> str:
        analytics = self._performance.build()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "mode",
                "recorded_at",
                "net_pnl",
                "drawdown",
            ]
        )
        for point in analytics.equity_curve:
            writer.writerow(
                [
                    point.mode,
                    point.recorded_at.isoformat(),
                    point.net_pnl,
                    point.drawdown,
                ]
            )
        return output.getvalue()
