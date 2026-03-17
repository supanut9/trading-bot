from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.operational_control_service import (
    BacktestControlResult,
    OperationalControlService,
)
from app.application.services.operations_service import OperationsService, PositionView, TradeView
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
    database_status: str
    position_count: int
    trade_count: int
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    positions: list[PositionView]
    trades: list[TradeView]
    backtest: BacktestControlResult


class ReportingDashboardService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._operations = OperationsService(session)
        self._settings = settings
        self._session_factory = session_factory

    def build_dashboard(self) -> ReportingDashboard:
        status = StatusService(self._settings).get_status()
        positions = self._operations.list_positions()
        trades = self._operations.list_trades(limit=10)
        backtest = OperationalControlService(
            self._settings,
            session_factory=self._session_factory,
        ).run_backtest(notify=False)

        return ReportingDashboard(
            app_name=str(status["app"]),
            environment=str(status["environment"]),
            exchange=str(status["exchange"]),
            symbol=str(status["symbol"]),
            timeframe=str(status["timeframe"]),
            paper_trading=bool(status["paper_trading"]),
            live_trading_enabled=bool(status["live_trading_enabled"]),
            database_status=str(status["database_status"]),
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
            backtest=backtest,
        )
