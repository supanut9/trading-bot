import csv
from io import StringIO

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditService
from app.application.services.operational_control_service import OperationalControlService
from app.application.services.operations_service import OperationsService
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
        self._operations = OperationsService(session)
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
