from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.market_data_service import MarketDataService
from app.application.services.paper_execution_service import (
    PaperExecutionRequest,
    PaperExecutionService,
)
from app.config import Settings
from app.core.logger import get_logger
from app.domain.risk import PortfolioState, RiskLimits, RiskService, TradeContext
from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.repositories.position_repository import PositionRepository

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerCycleResult:
    status: str
    detail: str
    signal_action: str | None = None
    client_order_id: str | None = None
    order_id: int | None = None
    trade_id: int | None = None
    position_quantity: Decimal | None = None


class WorkerOrchestrationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        strategy: EmaCrossoverStrategy | None = None,
        risk_service: RiskService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._market_data = MarketDataService(session)
        self._execution = PaperExecutionService(session)
        self._positions = PositionRepository(session)
        self._orders = OrderRepository(session)
        self._strategy = strategy or EmaCrossoverStrategy(
            fast_period=settings.strategy_fast_period,
            slow_period=settings.strategy_slow_period,
        )
        self._risk = risk_service or RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(settings.risk_per_trade_pct)),
                max_open_positions=settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(settings.max_daily_loss_pct)),
                paper_trading_only=not settings.live_trading_enabled,
            )
        )

    def run_cycle(self) -> WorkerCycleResult:
        candles = self._market_data.list_recent_candles(
            exchange=self._settings.exchange_name,
            symbol=self._settings.default_symbol,
            timeframe=self._settings.default_timeframe,
            limit=max(self._settings.strategy_slow_period + 1, 100),
        )
        if len(candles) < self._settings.strategy_slow_period + 1:
            logger.info(
                "worker_cycle_skipped reason=not_enough_candles "
                "exchange=%s symbol=%s timeframe=%s count=%s required=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                self._settings.default_timeframe,
                len(candles),
                self._settings.strategy_slow_period + 1,
            )
            return WorkerCycleResult(status="no_candles", detail="not enough candles")

        strategy_input = [
            Candle(
                open_time=candle.open_time,
                close_time=candle.close_time,
                open_price=candle.open_price,
                high_price=candle.high_price,
                low_price=candle.low_price,
                close_price=candle.close_price,
                volume=candle.volume,
            )
            for candle in candles
        ]
        signal = self._strategy.evaluate(strategy_input)
        if signal is None:
            logger.info(
                "worker_cycle_skipped reason=no_signal exchange=%s symbol=%s timeframe=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                self._settings.default_timeframe,
            )
            return WorkerCycleResult(status="no_signal", detail="strategy produced no signal")

        current_position = self._positions.get(
            exchange=self._settings.exchange_name,
            symbol=self._settings.default_symbol,
            mode=self._trading_mode,
        )
        latest_candle = max(candles, key=lambda candle: candle.open_time)
        client_order_id = self._build_client_order_id(signal, latest_candle.close_time)
        if self._orders.get_by_client_order_id(client_order_id) is not None:
            logger.info(
                "worker_cycle_skipped reason=duplicate_signal "
                "exchange=%s symbol=%s signal=%s client_order_id=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                signal.action,
                client_order_id,
            )
            return WorkerCycleResult(
                status="duplicate_signal",
                detail="signal for latest candle was already executed",
                signal_action=signal.action,
                client_order_id=client_order_id,
            )

        if signal.action == "buy" and self._has_open_quantity(current_position):
            logger.info(
                "worker_cycle_skipped reason=position_already_open "
                "exchange=%s symbol=%s signal=%s quantity=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                signal.action,
                current_position.quantity if current_position else Decimal("0"),
            )
            return WorkerCycleResult(
                status="position_open",
                detail="buy signal skipped because position is already open",
                signal_action=signal.action,
            )

        if signal.action == "sell" and not self._has_open_quantity(current_position):
            logger.info(
                "worker_cycle_skipped reason=no_open_position exchange=%s symbol=%s signal=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                signal.action,
            )
            return WorkerCycleResult(
                status="no_position",
                detail="sell signal skipped because no position is open",
                signal_action=signal.action,
            )

        latest_price = latest_candle.close_price
        risk_decision = self._risk.evaluate(
            portfolio=self._build_portfolio_state(current_position),
            trade=TradeContext(signal=signal, entry_price=latest_price),
        )
        if not risk_decision.approved:
            logger.warning(
                "worker_cycle_rejected exchange=%s symbol=%s signal=%s reason=%s",
                self._settings.exchange_name,
                self._settings.default_symbol,
                signal.action,
                risk_decision.reason,
            )
            return WorkerCycleResult(
                status="risk_rejected",
                detail=risk_decision.reason,
                signal_action=signal.action,
                client_order_id=client_order_id,
            )

        quantity = (
            current_position.quantity
            if signal.action == "sell" and current_position is not None
            else risk_decision.quantity
        )
        execution = self._execution.execute(
            PaperExecutionRequest(
                exchange=self._settings.exchange_name,
                symbol=self._settings.default_symbol,
                side=signal.action,
                quantity=quantity,
                price=latest_price,
                mode=self._trading_mode,
                client_order_id=client_order_id,
                submitted_reason=signal.reason,
            )
        )
        logger.info(
            "worker_cycle_executed exchange=%s symbol=%s signal=%s "
            "client_order_id=%s order_id=%s trade_id=%s quantity=%s",
            self._settings.exchange_name,
            self._settings.default_symbol,
            signal.action,
            client_order_id,
            execution.order.id,
            execution.trade.id,
            quantity,
        )
        return WorkerCycleResult(
            status="executed",
            detail="signal executed in paper mode",
            signal_action=signal.action,
            client_order_id=client_order_id,
            order_id=execution.order.id,
            trade_id=execution.trade.id,
            position_quantity=execution.position.quantity,
        )

    @property
    def _trading_mode(self) -> str:
        return "paper" if self._settings.paper_trading else "live"

    def _build_portfolio_state(self, current_position: PositionRecord | None) -> PortfolioState:
        realized_pnl = (
            current_position.realized_pnl if current_position is not None else Decimal("0")
        )
        base_equity = Decimal(str(self._settings.paper_account_equity))
        account_equity = base_equity + realized_pnl
        if base_equity > Decimal("0") and realized_pnl < Decimal("0"):
            daily_realized_loss_pct = abs(realized_pnl) / base_equity
        else:
            daily_realized_loss_pct = Decimal("0")

        return PortfolioState(
            account_equity=account_equity,
            open_positions=1 if self._has_open_quantity(current_position) else 0,
            daily_realized_loss_pct=daily_realized_loss_pct,
            trading_mode=self._trading_mode,
        )

    @staticmethod
    def _has_open_quantity(position: PositionRecord | None) -> bool:
        return position is not None and position.quantity > Decimal("0")

    def _build_client_order_id(self, signal: Signal, close_time: datetime) -> str:
        symbol_token = self._settings.default_symbol.replace("/", "-").lower()
        candle_token = close_time.strftime("%Y%m%d%H%M%S")
        return (
            f"{self._trading_mode}-{self._settings.exchange_name}-"
            f"{symbol_token}-{self._settings.default_timeframe}-{signal.action}-{candle_token}"
        )
