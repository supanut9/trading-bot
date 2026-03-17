from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.backtest_service import BacktestResult, BacktestService
from app.application.services.market_data_service import MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncService
from app.application.services.notification_service import (
    NotificationService,
    build_notification_service,
)
from app.application.services.worker_orchestration_service import WorkerOrchestrationService
from app.config import Settings
from app.domain.risk import RiskLimits, RiskService
from app.domain.strategies.base import Candle
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.models.candle import CandleRecord
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.exchanges.factory import build_market_data_exchange_client


@dataclass(frozen=True, slots=True)
class WorkerControlResult:
    status: str
    detail: str
    signal_action: str | None = None
    client_order_id: str | None = None
    order_id: int | None = None
    trade_id: int | None = None
    position_quantity: Decimal | None = None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class BacktestControlResult:
    status: str
    detail: str
    notified: bool
    candle_count: int
    required_candles: int
    starting_equity: Decimal | None = None
    ending_equity: Decimal | None = None
    realized_pnl: Decimal | None = None
    total_return_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    total_trades: int | None = None
    winning_trades: int | None = None
    losing_trades: int | None = None


@dataclass(frozen=True, slots=True)
class MarketSyncControlResult:
    status: str
    detail: str
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool = False


class OperationalControlService:
    _decimal_precision = Decimal("0.00000001")

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory or create_session_factory(settings)
        self._notifications = notifications or build_notification_service(settings)

    def run_worker_cycle(self) -> WorkerControlResult:
        with self._session_factory() as session:
            result = WorkerOrchestrationService(session, self._settings).run_cycle()

        notified = self._notifications.notify_worker_cycle(self._settings, result)
        return WorkerControlResult(
            status=result.status,
            detail=result.detail,
            signal_action=result.signal_action,
            client_order_id=result.client_order_id,
            order_id=result.order_id,
            trade_id=result.trade_id,
            position_quantity=result.position_quantity,
            notified=notified,
        )

    def run_market_sync(self) -> MarketSyncControlResult:
        with self._session_factory() as session:
            try:
                result = MarketDataSyncService(
                    session,
                    build_market_data_exchange_client(self._settings),
                ).sync_recent_closed_candles(
                    exchange=self._settings.exchange_name,
                    symbol=self._settings.default_symbol,
                    timeframe=self._settings.default_timeframe,
                    limit=self._settings.market_data_sync_limit,
                )
            except Exception:
                failed = MarketSyncControlResult(
                    status="failed",
                    detail="market data sync failed",
                    fetched_count=0,
                    stored_count=0,
                )
                notified = self._notifications.notify_market_sync(self._settings, failed)
                return MarketSyncControlResult(
                    status=failed.status,
                    detail=failed.detail,
                    fetched_count=failed.fetched_count,
                    stored_count=failed.stored_count,
                    latest_open_time=failed.latest_open_time,
                    notified=notified,
                )

        detail = "market data sync completed"
        if result.fetched_count == 0:
            detail = "no candles fetched"
        elif result.stored_count == 0:
            detail = "no new candles stored"

        completed = MarketSyncControlResult(
            status="completed",
            detail=detail,
            fetched_count=result.fetched_count,
            stored_count=result.stored_count,
            latest_open_time=result.latest_open_time,
        )
        notified = self._notifications.notify_market_sync(self._settings, completed)
        return MarketSyncControlResult(
            status=completed.status,
            detail=completed.detail,
            fetched_count=completed.fetched_count,
            stored_count=completed.stored_count,
            latest_open_time=completed.latest_open_time,
            notified=notified,
        )

    def run_backtest(self, *, notify: bool = True) -> BacktestControlResult:
        with self._session_factory() as session:
            records = MarketDataService(session).list_historical_candles(
                exchange=self._settings.exchange_name,
                symbol=self._settings.default_symbol,
                timeframe=self._settings.default_timeframe,
            )
            candle_count = len(records)
            required_candles = self._settings.strategy_slow_period + 1

            if not records:
                backtest_result = None
                status = "skipped"
                detail = "no_candles"
            elif candle_count < required_candles:
                backtest_result = None
                status = "skipped"
                detail = "not_enough_candles"
            else:
                backtest_result = self._run_backtest_from_records(records)
                status = "completed"
                detail = "backtest completed"

        if backtest_result is None:
            notified = False
            if notify:
                notified = self._notifications.notify_backtest_skipped(
                    self._settings,
                    reason=detail,
                    count=candle_count,
                    required=required_candles,
                )
            return BacktestControlResult(
                status=status,
                detail=detail,
                notified=notified,
                candle_count=candle_count,
                required_candles=required_candles,
            )

        notified = False
        if notify:
            notified = self._notifications.notify_backtest_completed(
                self._settings,
                backtest_result,
            )
        return BacktestControlResult(
            status=status,
            detail=detail,
            notified=notified,
            candle_count=candle_count,
            required_candles=required_candles,
            starting_equity=self._quantize_decimal(backtest_result.starting_equity),
            ending_equity=self._quantize_decimal(backtest_result.ending_equity),
            realized_pnl=self._quantize_decimal(backtest_result.realized_pnl),
            total_return_pct=self._quantize_decimal(backtest_result.total_return_pct),
            max_drawdown_pct=self._quantize_decimal(backtest_result.max_drawdown_pct),
            total_trades=backtest_result.total_trades,
            winning_trades=backtest_result.winning_trades,
            losing_trades=backtest_result.losing_trades,
        )

    def _run_backtest_from_records(self, records: Sequence[CandleRecord]) -> BacktestResult:
        return BacktestService(
            strategy=EmaCrossoverStrategy(
                fast_period=self._settings.strategy_fast_period,
                slow_period=self._settings.strategy_slow_period,
            ),
            risk_service=self._build_risk_service(),
            starting_equity=Decimal(str(self._settings.paper_account_equity)),
        ).run(
            [
                Candle(
                    open_time=record.open_time,
                    close_time=record.close_time,
                    open_price=record.open_price,
                    high_price=record.high_price,
                    low_price=record.low_price,
                    close_price=record.close_price,
                    volume=record.volume,
                )
                for record in records
            ]
        )

    def _build_risk_service(self) -> RiskService:
        return RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(self._settings.risk_per_trade_pct)),
                max_open_positions=self._settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(self._settings.max_daily_loss_pct)),
                paper_trading_only=not self._settings.live_trading_enabled,
            )
        )

    @classmethod
    def _quantize_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(cls._decimal_precision)
