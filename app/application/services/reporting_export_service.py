import csv
from io import StringIO

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditService
from app.application.services.live_order_recovery_report_service import (
    LiveOrderRecoveryReportService,
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
        ).run_backtest(notify=False, audit=False, source="reporting.snapshot")

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

    def export_audit_events_csv(self, *, limit: int = 100) -> str:
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
                "payload_json",
            ]
        )
        for event in self._audit.list_recent(limit=limit):
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
                    event.payload_json,
                ]
            )
        return output.getvalue()

    def export_live_recovery_csv(self) -> str:
        report = self._recovery.build_report(order_limit=50, audit_limit=10)
        latest_at, latest_type, latest_status = self._recovery.latest_event_summary(
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
            ]
        )
        for order in report.unresolved_orders:
            writer.writerow(
                [
                    order.id,
                    order.exchange,
                    order.symbol,
                    order.side,
                    order.status,
                    order.client_order_id,
                    order.exchange_order_id,
                    order.updated_at.isoformat(),
                    latest_at.isoformat() if latest_at is not None else None,
                    latest_type,
                    latest_status,
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
