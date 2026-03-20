from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.execution_factory import build_execution_service
from app.application.services.live_execution_service import DuplicateLiveOrderError
from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.market_data_service import MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncService
from app.application.services.operator_runtime_config_service import OperatorRuntimeConfig
from app.application.services.paper_execution_service import PaperExecutionRequest
from app.application.services.qualification_service import QualificationService
from app.application.services.symbol_rules_service import SymbolRulesService
from app.config import Settings
from app.core.logger import get_logger
from app.domain.risk import PortfolioState, RiskLimits, RiskService, TradeContext
from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.order_repository import (
    DuplicateClientOrderIdError,
    OrderRepository,
)
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.shadow_blocked_signal_repository import (
    ShadowBlockedSignalRepository,
)
from app.infrastructure.exchanges.factory import build_market_data_exchange_client
from app.infrastructure.executions.base import ExecutionService, ExecutionUnavailableError

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
        market_sync: MarketDataSyncService | None = None,
        execution_service: ExecutionService | None = None,
        operator_config: OperatorRuntimeConfig | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._operator_config = operator_config
        self._market_data = MarketDataService(session)
        self._execution = execution_service or build_execution_service(session, settings)
        self._positions = PositionRepository(session)
        self._orders = OrderRepository(session)
        self._market_sync = market_sync
        self._strategy = strategy or EmaCrossoverStrategy(
            fast_period=self._fast_period,
            slow_period=self._slow_period,
            rsi_period=(
                settings.strategy_rsi_period if settings.strategy_rsi_filter_enabled else None
            ),
            rsi_overbought=Decimal(str(settings.strategy_rsi_overbought)),
            rsi_oversold=Decimal(str(settings.strategy_rsi_oversold)),
            volume_ma_period=(
                settings.strategy_volume_ma_period
                if settings.strategy_volume_filter_enabled
                else None
            ),
        )
        live_halt_state = LiveOperatorControlService(
            session, settings
        ).get_live_trading_halt_state()
        active_symbol = (
            operator_config.symbol if operator_config is not None else settings.default_symbol
        )
        stored_symbol_rules = SymbolRulesService(session).get_rules(
            exchange=settings.exchange_name,
            symbol=active_symbol,
        )
        self._risk = risk_service or RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(settings.risk_per_trade_pct)),
                max_open_positions=settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(settings.max_daily_loss_pct)),
                paper_trading_only=not settings.live_trading_enabled,
                live_trading_halted=live_halt_state.halted,
                live_max_order_notional=settings.live_max_order_notional,
                live_max_position_quantity=settings.live_max_position_quantity,
                symbol_rules=stored_symbol_rules,
            )
        )

    def run_cycle(self) -> WorkerCycleResult:
        candle_limit = max(
            self._slow_period + 1,
            self._settings.market_data_sync_limit,
        )
        if self._settings.market_data_sync_enabled:
            try:
                self._get_market_sync().sync_recent_closed_candles(
                    exchange=self._settings.exchange_name,
                    symbol=self._symbol,
                    timeframe=self._timeframe,
                    limit=candle_limit,
                )
            except Exception as exc:
                logger.exception(
                    "worker_cycle_skipped reason=market_data_sync_failed "
                    "exchange=%s symbol=%s timeframe=%s error=%s",
                    self._settings.exchange_name,
                    self._symbol,
                    self._timeframe,
                    exc,
                )
                return WorkerCycleResult(
                    status="market_data_sync_failed",
                    detail="failed to sync market data",
                )

        candles = self._market_data.list_recent_candles(
            exchange=self._settings.exchange_name,
            symbol=self._symbol,
            timeframe=self._timeframe,
            limit=candle_limit,
        )
        if len(candles) < self._slow_period + 1:
            logger.info(
                "worker_cycle_skipped reason=not_enough_candles "
                "exchange=%s symbol=%s timeframe=%s count=%s required=%s",
                self._settings.exchange_name,
                self._symbol,
                self._timeframe,
                len(candles),
                self._slow_period + 1,
            )
            return WorkerCycleResult(status="no_candles", detail="not enough candles")

        if self._trading_mode == "live":
            from app.application.services.live_risk_hard_gate_service import LiveRiskHardGateService

            hard_gate_report = LiveRiskHardGateService(self._session, self._settings).evaluate(
                exchange=self._settings.exchange_name,
                symbol=self._symbol,
            )
            if hard_gate_report.should_halt:
                logger.warning(
                    "worker_cycle_halted reason=live_risk_hard_gate_violation "
                    "exchange=%s symbol=%s detail=%s",
                    self._settings.exchange_name,
                    self._symbol,
                    hard_gate_report.reason,
                )
                LiveOperatorControlService(self._session, self._settings).set_live_trading_halted(
                    halted=True,
                    updated_by="system",
                    reason=hard_gate_report.reason,
                )
                self._session.commit()
                return WorkerCycleResult(
                    status="auto_halted",
                    detail=f"live trading halted automatically: {hard_gate_report.reason}",
                )

            report = QualificationService(self._session).evaluate(
                exchange=self._settings.exchange_name,
                symbol=self._symbol,
            )
            if not report.all_passed:
                logger.warning(
                    "worker_cycle_rejected reason=strategy_not_qualified exchange=%s symbol=%s",
                    self._settings.exchange_name,
                    self._symbol,
                )
                return WorkerCycleResult(
                    status="not_qualified",
                    detail="strategy has not passed all qualification gates",
                )

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
                self._symbol,
                self._timeframe,
            )
            return WorkerCycleResult(status="no_signal", detail="strategy produced no signal")

        current_position = self._positions.get(
            exchange=self._settings.exchange_name,
            symbol=self._symbol,
            mode=self._trading_mode,
        )
        latest_candle = max(candles, key=lambda candle: candle.open_time)
        client_order_id = self._build_client_order_id(signal, latest_candle.close_time)
        if self._orders.get_by_client_order_id(client_order_id) is not None:
            logger.info(
                "worker_cycle_skipped reason=duplicate_signal "
                "exchange=%s symbol=%s signal=%s client_order_id=%s",
                self._settings.exchange_name,
                self._symbol,
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
                self._symbol,
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
                self._symbol,
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
                self._symbol,
                signal.action,
                risk_decision.reason,
            )
            if self._trading_mode == "shadow":
                ShadowBlockedSignalRepository(self._session).create(
                    exchange=self._settings.exchange_name,
                    symbol=self._symbol,
                    timeframe=self._timeframe,
                    signal_action=signal.action,
                    signal_reason=signal.reason,
                    block_reason=risk_decision.reason,
                    block_source="risk",
                    price=latest_price,
                    client_order_id=client_order_id,
                )
                self._session.commit()
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
        try:
            execution = self._execution.execute(
                PaperExecutionRequest(
                    exchange=self._settings.exchange_name,
                    symbol=self._symbol,
                    side=signal.action,
                    quantity=quantity,
                    price=latest_price,
                    mode=self._trading_mode,
                    client_order_id=client_order_id,
                    submitted_reason=signal.reason,
                )
            )
        except ExecutionUnavailableError as exc:
            logger.warning(
                "worker_cycle_rejected reason=execution_unavailable "
                "exchange=%s symbol=%s signal=%s client_order_id=%s detail=%s",
                self._settings.exchange_name,
                self._symbol,
                signal.action,
                client_order_id,
                exc,
            )
            return WorkerCycleResult(
                status="execution_unavailable",
                detail=str(exc),
                signal_action=signal.action,
                client_order_id=client_order_id,
            )
        except DuplicateClientOrderIdError:
            logger.info(
                "worker_cycle_skipped reason=duplicate_signal_race "
                "exchange=%s symbol=%s signal=%s client_order_id=%s",
                self._settings.exchange_name,
                self._symbol,
                signal.action,
                client_order_id,
            )
            return WorkerCycleResult(
                status="duplicate_signal",
                detail="signal for latest candle was already executed",
                signal_action=signal.action,
                client_order_id=client_order_id,
            )
        except DuplicateLiveOrderError as exc:
            logger.warning(
                "worker_cycle_rejected reason=duplicate_live_order "
                "exchange=%s symbol=%s signal=%s client_order_id=%s detail=%s",
                self._settings.exchange_name,
                self._symbol,
                signal.action,
                client_order_id,
                exc,
            )
            return WorkerCycleResult(
                status="duplicate_live_order",
                detail=str(exc),
                signal_action=signal.action,
                client_order_id=client_order_id,
            )
        if self._trading_mode == "shadow":
            logger.info(
                "worker_cycle_shadow exchange=%s symbol=%s signal=%s "
                "client_order_id=%s shadow_trade_id=%s quantity=%s net_pnl=%s",
                self._settings.exchange_name,
                self._symbol,
                signal.action,
                client_order_id,
                execution.shadow_trade_id,
                quantity,
                execution.net_pnl,
            )
            return WorkerCycleResult(
                status="executed",
                detail="signal executed in shadow mode",
                signal_action=signal.action,
                client_order_id=client_order_id,
                position_quantity=(
                    execution.position.quantity if execution.position is not None else None
                ),
            )
        logger.info(
            "worker_cycle_executed exchange=%s symbol=%s signal=%s "
            "client_order_id=%s order_id=%s trade_id=%s quantity=%s mode=%s",
            self._settings.exchange_name,
            self._symbol,
            signal.action,
            client_order_id,
            execution.order.id,
            execution.trade.id if execution.trade is not None else None,
            quantity,
            self._trading_mode,
        )
        detail = "signal executed in paper mode"
        status = "executed"
        if self._trading_mode == "live":
            detail = "signal submitted to live exchange"
            status = "submitted"
        return WorkerCycleResult(
            status=status,
            detail=detail,
            signal_action=signal.action,
            client_order_id=client_order_id,
            order_id=execution.order.id,
            trade_id=execution.trade.id if execution.trade is not None else None,
            position_quantity=(
                execution.position.quantity if execution.position is not None else None
            ),
        )

    @property
    def _trading_mode(self) -> str:
        return self._settings.execution_mode

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
            current_position_quantity=(
                current_position.quantity if current_position is not None else Decimal("0")
            ),
            daily_realized_loss_pct=daily_realized_loss_pct,
            trading_mode="paper" if self._trading_mode == "shadow" else self._trading_mode,
        )

    @staticmethod
    def _has_open_quantity(position: PositionRecord | None) -> bool:
        return position is not None and position.quantity > Decimal("0")

    def _build_client_order_id(self, signal: Signal, close_time: datetime) -> str:
        symbol_token = self._symbol.replace("/", "-").lower()
        candle_token = close_time.strftime("%Y%m%d%H%M%S")
        return (
            f"{self._trading_mode}-{self._settings.exchange_name}-"
            f"{symbol_token}-{self._timeframe}-{signal.action}-{candle_token}"
        )

    def _get_market_sync(self) -> MarketDataSyncService:
        if self._market_sync is None:
            self._market_sync = MarketDataSyncService(
                self._session,
                build_market_data_exchange_client(self._settings),
            )
        return self._market_sync

    @property
    def _symbol(self) -> str:
        if self._operator_config is not None:
            return self._operator_config.symbol
        return self._settings.default_symbol

    @property
    def _timeframe(self) -> str:
        if self._operator_config is not None:
            return self._operator_config.timeframe
        return self._settings.default_timeframe

    @property
    def _fast_period(self) -> int:
        if self._operator_config is not None:
            return self._operator_config.fast_period
        return self._settings.strategy_fast_period

    @property
    def _slow_period(self) -> int:
        if self._operator_config is not None:
            return self._operator_config.slow_period
        return self._settings.strategy_slow_period
