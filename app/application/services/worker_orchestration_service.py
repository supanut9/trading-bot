import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.application.services.execution_factory import build_execution_service
from app.application.services.live_execution_service import (
    DuplicateLiveOrderError,
    InsufficientExpectedProfitError,
)
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
from app.domain.strategies.base import Candle, Signal, Strategy
from app.domain.strategies.breakout_atr import BreakoutAtrStrategy
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.domain.strategies.macd_crossover import MacdCrossoverStrategy
from app.domain.strategies.mean_reversion_bollinger import MeanReversionBollingerStrategy
from app.domain.strategies.multi_timeframe import is_htf_trend_aligned
from app.domain.strategies.rsi_momentum import RsiMomentumStrategy
from app.infrastructure.database.models.position import PositionRecord
from app.infrastructure.database.repositories.order_repository import (
    DuplicateClientOrderIdError,
    OrderRepository,
)
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.shadow_blocked_signal_repository import (
    ShadowBlockedSignalRepository,
)
from app.infrastructure.database.repositories.trade_repository import TradeRepository
from app.infrastructure.exchanges.base import ExchangeConnectionError, ExchangeError
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
        strategy: Strategy | None = None,
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
        self._strategy = strategy or self._build_strategy(operator_config, settings)
        live_halt_state = LiveOperatorControlService(
            session, settings
        ).get_live_trading_halt_state()
        # Risk is built per-symbol in _run_symbol_cycle; store override and base limits template.
        self._risk_override = risk_service
        self._risk_limits_base = RiskLimits(
            risk_per_trade_pct=Decimal(str(settings.risk_per_trade_pct)),
            max_open_positions=settings.max_open_positions,
            max_daily_loss_pct=Decimal(str(settings.max_daily_loss_pct)),
            paper_trading_only=not settings.live_trading_enabled,
            live_trading_halted=live_halt_state.halted,
            live_max_order_notional=settings.live_max_order_notional,
            live_max_position_quantity=settings.live_max_position_quantity,
            volatility_sizing_enabled=settings.volatility_sizing_enabled,
        )

    def run_cycle(self) -> WorkerCycleResult:
        symbols = self._active_symbols
        if len(symbols) == 1:
            return self._run_symbol_cycle(symbols[0], self._timeframe)

        # Multi-symbol: guard — only allowed in paper/shadow modes
        if self._trading_mode == "live":
            return WorkerCycleResult(
                status="multi_symbol_live_blocked",
                detail="multi-symbol trading is not supported in live mode",
            )

        results: list[WorkerCycleResult] = []
        for symbol in symbols:
            result = self._run_symbol_cycle(symbol, self._timeframe)
            results.append(result)
            logger.info(
                "multi_symbol_cycle symbol=%s status=%s detail=%s",
                symbol,
                result.status,
                result.detail,
            )

        executed = [r for r in results if r.status in ("executed", "stop_loss_exit", "submitted")]
        return WorkerCycleResult(
            status="multi_symbol_cycle",
            detail=(
                f"processed {len(symbols)} symbols; "
                f"{len(executed)} executed, {len(results) - len(executed)} skipped"
            ),
        )

    def _run_symbol_cycle(self, symbol: str, timeframe: str) -> WorkerCycleResult:
        candle_limit = max(
            self._min_required_candles,
            self._settings.market_data_sync_limit,
        )
        if self._settings.market_data_sync_enabled:
            try:
                self._get_market_sync().sync_recent_closed_candles(
                    exchange=self._settings.exchange_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=candle_limit,
                )
            except Exception as exc:
                logger.exception(
                    "worker_cycle_skipped reason=market_data_sync_failed "
                    "exchange=%s symbol=%s timeframe=%s error=%s",
                    self._settings.exchange_name,
                    symbol,
                    timeframe,
                    exc,
                )
                return WorkerCycleResult(
                    status="market_data_sync_failed",
                    detail="failed to sync market data",
                )

        candles = self._market_data.list_recent_candles(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            limit=candle_limit,
        )
        if len(candles) < self._min_required_candles:
            logger.info(
                "worker_cycle_skipped reason=not_enough_candles "
                "exchange=%s symbol=%s timeframe=%s count=%s required=%s",
                self._settings.exchange_name,
                symbol,
                timeframe,
                len(candles),
                self._min_required_candles,
            )
            return WorkerCycleResult(status="no_candles", detail="not enough candles")

        latest_candle = max(candles, key=lambda c: c.open_time)
        mark_price = latest_candle.close_price
        self._mark_open_position_to_market_for_symbol(symbol, mark_price)

        current_position = self._positions.get(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
        )
        stop_result = self._check_and_execute_stop_exit_for_symbol(
            symbol, current_position, mark_price
        )
        if stop_result is not None:
            return stop_result
        self._update_trailing_stop_for_symbol(symbol, current_position, mark_price, candles)

        if self._trading_mode == "live" and self._settings.live_order_routing_mode == "limit":
            from app.application.services.smart_order_fallback_service import (
                SmartOrderFallbackService,
            )
            from app.infrastructure.exchanges.factory import build_live_order_exchange_client

            client = build_live_order_exchange_client(self._settings)
            fallback_service = SmartOrderFallbackService(
                self._session, self._settings, client=client
            )
            fallback_service.process_fallbacks()

        hard_gate_report = None
        if self._trading_mode == "live":
            from app.application.services.live_risk_hard_gate_service import LiveRiskHardGateService

            hard_gate_report = LiveRiskHardGateService(self._session, self._settings).evaluate(
                exchange=self._settings.exchange_name,
                symbol=symbol,
            )
            if hard_gate_report.should_halt:
                logger.warning(
                    "worker_cycle_halted reason=live_risk_hard_gate_violation "
                    "exchange=%s symbol=%s detail=%s",
                    self._settings.exchange_name,
                    symbol,
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
                symbol=symbol,
            )
            if not report.all_passed:
                logger.warning(
                    "worker_cycle_rejected reason=strategy_not_qualified exchange=%s symbol=%s",
                    self._settings.exchange_name,
                    symbol,
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
                symbol,
                timeframe,
            )
            return WorkerCycleResult(status="no_signal", detail="strategy produced no signal")

        client_order_id = self._build_client_order_id_for_symbol(
            symbol, timeframe, signal, latest_candle.close_time
        )
        if self._orders.get_by_client_order_id(client_order_id) is not None:
            logger.info(
                "worker_cycle_skipped reason=duplicate_signal "
                "exchange=%s symbol=%s signal=%s client_order_id=%s",
                self._settings.exchange_name,
                symbol,
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
                symbol,
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
                symbol,
                signal.action,
            )
            return WorkerCycleResult(
                status="no_position",
                detail="sell signal skipped because no position is open",
                signal_action=signal.action,
            )

        if self._settings.multi_tf_confirmation_enabled:
            htf_timeframe = self._settings.multi_tf_confirmation_timeframe
            htf_period = self._settings.multi_tf_confirmation_period
            htf_records = self._market_data.list_recent_candles(
                exchange=self._settings.exchange_name,
                symbol=symbol,
                timeframe=htf_timeframe,
                limit=htf_period + 30,
            )
            htf_candles = [
                Candle(
                    open_time=r.open_time,
                    close_time=r.close_time,
                    open_price=r.open_price,
                    high_price=r.high_price,
                    low_price=r.low_price,
                    close_price=r.close_price,
                    volume=r.volume,
                )
                for r in htf_records
            ]
            if not is_htf_trend_aligned(htf_candles, signal, htf_period):
                logger.info(
                    "worker_cycle_skipped reason=multi_tf_rejected "
                    "exchange=%s symbol=%s signal=%s htf_timeframe=%s",
                    self._settings.exchange_name,
                    symbol,
                    signal.action,
                    htf_timeframe,
                )
                return WorkerCycleResult(
                    status="multi_tf_rejected",
                    detail=f"signal rejected: HTF ({htf_timeframe}) trend not aligned",
                    signal_action=signal.action,
                )

        latest_price = latest_candle.close_price
        atr_for_sizing = (
            self._compute_atr_from_candles(candles)
            if self._settings.volatility_sizing_enabled
            else None
        )
        risk = self._get_risk_for_symbol(symbol)
        all_positions = self._positions.list_all()
        risk_decision = risk.evaluate(
            portfolio=self._build_portfolio_state(symbol, current_position, all_positions),
            trade=TradeContext(signal=signal, entry_price=latest_price, atr_value=atr_for_sizing),
        )
        if not risk_decision.approved:
            logger.warning(
                "worker_cycle_rejected exchange=%s symbol=%s signal=%s reason=%s hard=%s",
                self._settings.exchange_name,
                symbol,
                signal.action,
                risk_decision.reason,
                risk_decision.is_hard_violation,
            )

            if (
                risk_decision.is_hard_violation
                and self._trading_mode == "live"
                and self._settings.live_trading_enabled
            ):
                logger.critical(
                    "critical_risk_gate_violated action=halting_live_execution reason=%s",
                    risk_decision.reason,
                )
                LiveOperatorControlService(self._session, self._settings).set_live_trading_halted(
                    halted=True,
                    updated_by="system",
                    reason=f"Risk Guard: {risk_decision.reason}",
                )
                self._session.commit()
                return WorkerCycleResult(
                    status="auto_halted",
                    detail=(
                        f"live trading halted due to critical risk violation: "
                        f"{risk_decision.reason}"
                    ),
                    signal_action=signal.action,
                    client_order_id=client_order_id,
                )

            if self._trading_mode == "shadow":
                ShadowBlockedSignalRepository(self._session).create(
                    exchange=self._settings.exchange_name,
                    symbol=symbol,
                    timeframe=timeframe,
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

        canary_multiplier = (
            hard_gate_report.canary_multiplier if hard_gate_report is not None else Decimal("1.0")
        )
        quantity = (
            current_position.quantity
            if signal.action == "sell" and current_position is not None
            else (risk_decision.quantity * canary_multiplier).quantize(Decimal("0.00000001"))
        )
        try:
            execution = self._execution.execute(
                PaperExecutionRequest(
                    exchange=self._settings.exchange_name,
                    symbol=symbol,
                    side=signal.action,
                    quantity=quantity,
                    price=latest_price,
                    mode=self._trading_mode,
                    trading_mode=self._settings.trading_mode,
                    client_order_id=client_order_id,
                    submitted_reason=signal.reason,
                )
            )
        except ExecutionUnavailableError as exc:
            logger.warning(
                "worker_cycle_rejected reason=execution_unavailable "
                "exchange=%s symbol=%s signal=%s client_order_id=%s detail=%s",
                self._settings.exchange_name,
                symbol,
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
                symbol,
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
                symbol,
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
        except (ExchangeError, ExchangeConnectionError) as exc:
            logger.error(
                "worker_cycle_failed reason=exchange_error "
                "exchange=%s symbol=%s signal=%s client_order_id=%s detail=%s",
                self._settings.exchange_name,
                symbol,
                signal.action,
                client_order_id,
                exc,
            )
            from app.application.services.audit_service import AuditService
            from app.application.services.live_incident_auto_halt_service import (
                LiveIncidentAutoHaltService,
            )

            AuditService(session=self._session).record_event(
                event_type="worker_cycle",
                source="worker",
                status="failed",
                detail=f"exchange_error: {exc}",
                exchange=self._settings.exchange_name,
                symbol=symbol,
                timeframe=timeframe,
            )
            self._session.commit()

            if self._trading_mode == "live":
                LiveIncidentAutoHaltService(
                    self._session, self._settings
                ).evaluate_and_halt_if_needed()

            return WorkerCycleResult(
                status="execution_failed",
                detail=str(exc),
                signal_action=signal.action,
                client_order_id=client_order_id,
            )
        except InsufficientExpectedProfitError as exc:
            logger.warning(
                "worker_cycle_rejected reason=insufficient_expected_profit "
                "exchange=%s symbol=%s signal=%s client_order_id=%s detail=%s",
                self._settings.exchange_name,
                symbol,
                signal.action,
                client_order_id,
                exc,
            )
            return WorkerCycleResult(
                status="insufficient_expected_profit",
                detail=str(exc),
                signal_action=signal.action,
                client_order_id=client_order_id,
            )
        if signal.action == "buy":
            self._set_position_stop_for_symbol(symbol, latest_price, candles)

        if self._trading_mode == "shadow":
            logger.info(
                "worker_cycle_shadow exchange=%s symbol=%s signal=%s "
                "client_order_id=%s shadow_trade_id=%s quantity=%s net_pnl=%s",
                self._settings.exchange_name,
                symbol,
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
            symbol,
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

    def _build_portfolio_state(
        self,
        symbol: str,
        current_position: PositionRecord | None,
        all_positions: list[PositionRecord],
    ) -> PortfolioState:
        realized_pnl = (
            current_position.realized_pnl if current_position is not None else Decimal("0")
        )
        base_equity = Decimal(str(self._settings.paper_account_equity))
        account_equity = base_equity + realized_pnl

        if base_equity > Decimal("0") and realized_pnl < Decimal("0"):
            daily_realized_loss_pct = abs(realized_pnl) / base_equity
        else:
            daily_realized_loss_pct = Decimal("0")

        # Hard Risk Gates: Additional stats
        mode = "paper" if self._trading_mode == "shadow" else self._trading_mode
        trades = TradeRepository(self._session)

        # Weekly realized loss (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        weekly_pnl = trades.get_realized_pnl_sum(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            mode=mode,
            since=seven_days_ago,
        )
        if base_equity > Decimal("0") and weekly_pnl < Decimal("0"):
            weekly_realized_loss_pct = abs(weekly_pnl) / base_equity
        else:
            weekly_realized_loss_pct = Decimal("0")

        # Consecutive losses
        consecutive_losses = trades.get_consecutive_losses(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            mode=mode,
        )

        # Concurrent exposure: total notional across ALL open positions / equity
        total_notional = Decimal("0")
        for pos in all_positions:
            if pos.quantity > Decimal("0") and pos.average_entry_price is not None:
                total_notional += pos.quantity * pos.average_entry_price
        if account_equity > Decimal("0"):
            concurrent_exposure_pct = total_notional / account_equity
        else:
            concurrent_exposure_pct = Decimal("0")

        current_quantity = (
            current_position.quantity if current_position is not None else Decimal("0")
        )
        open_count = sum(1 for p in all_positions if p.quantity > Decimal("0"))

        return PortfolioState(
            account_equity=account_equity,
            open_positions=open_count,
            current_position_quantity=current_quantity,
            daily_realized_loss_pct=daily_realized_loss_pct,
            weekly_realized_loss_pct=weekly_realized_loss_pct,
            concurrent_exposure_pct=concurrent_exposure_pct,
            consecutive_losses=consecutive_losses,
            execution_mode=mode,  # type: ignore
            trading_mode=self._settings.trading_mode,  # type: ignore
        )

    def _check_and_execute_stop_exit_for_symbol(
        self,
        symbol: str,
        position: PositionRecord | None,
        mark_price: Decimal,
    ) -> WorkerCycleResult | None:
        if position is None or position.quantity <= Decimal("0"):
            return None
        if position.stop_loss_price is None:
            return None
        if self._settings.stop_loss_atr_multiplier <= 0:
            return None
        triggered = (position.side == "long" and mark_price <= position.stop_loss_price) or (
            position.side == "short" and mark_price >= position.stop_loss_price
        )
        if not triggered:
            return None
        logger.info(
            "stop_loss_triggered exchange=%s symbol=%s side=%s stop=%s price=%s quantity=%s",
            self._settings.exchange_name,
            symbol,
            position.side,
            position.stop_loss_price,
            mark_price,
            position.quantity,
        )
        side = "sell" if position.side == "long" else "buy"
        from datetime import datetime as _dt

        client_order_id = (
            f"stop-{self._trading_mode}-{symbol.replace('/', '-').lower()}"
            f"-{_dt.now().strftime('%Y%m%d%H%M%S')}"
        )
        try:
            self._execution.execute(
                PaperExecutionRequest(
                    exchange=self._settings.exchange_name,
                    symbol=symbol,
                    side=side,
                    quantity=position.quantity,
                    price=mark_price,
                    mode=self._trading_mode,
                    trading_mode=self._settings.trading_mode,
                    client_order_id=client_order_id,
                    submitted_reason="stop_loss_hit",
                )
            )
        except Exception as exc:
            logger.error(
                "stop_loss_execution_failed exchange=%s symbol=%s error=%s",
                self._settings.exchange_name,
                symbol,
                exc,
            )
            return None
        return WorkerCycleResult(
            status="stop_loss_exit",
            detail=f"position closed by stop loss at {mark_price}",
            signal_action=side,
            client_order_id=client_order_id,
            position_quantity=Decimal("0"),
        )

    def _set_position_stop_for_symbol(
        self, symbol: str, entry_price: Decimal, candles: list
    ) -> None:
        if self._settings.stop_loss_atr_multiplier <= 0:
            return
        atr = self._compute_atr_from_candles(candles)
        if atr is None:
            return
        multiplier = Decimal(str(self._settings.stop_loss_atr_multiplier))
        stop_price = entry_price - atr * multiplier
        if stop_price <= Decimal("0"):
            return
        position = self._positions.get(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
        )
        if position is None or position.quantity <= Decimal("0"):
            return
        self._positions.upsert(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
            side=position.side,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=position.unrealized_pnl,
            stop_loss_price=stop_price,
            highest_price_since_entry=entry_price,
        )
        self._session.commit()
        logger.info(
            "stop_loss_set exchange=%s symbol=%s stop=%s atr=%s entry=%s",
            self._settings.exchange_name,
            symbol,
            stop_price,
            atr,
            entry_price,
        )

    def _update_trailing_stop_for_symbol(
        self, symbol: str, position: PositionRecord | None, mark_price: Decimal, candles: list
    ) -> None:
        if not self._settings.trailing_stop_enabled:
            return
        if position is None or position.quantity <= Decimal("0"):
            return
        if position.stop_loss_price is None:
            return
        if self._settings.stop_loss_atr_multiplier <= 0:
            return
        atr = self._compute_atr_from_candles(candles)
        if atr is None:
            return
        multiplier = Decimal(str(self._settings.stop_loss_atr_multiplier))
        if position.side == "long":
            new_high = max(position.highest_price_since_entry or mark_price, mark_price)
            new_stop = new_high - atr * multiplier
            if new_stop <= position.stop_loss_price:
                return
            updated_stop = new_stop
            updated_peak = new_high
        else:
            new_low = min(position.highest_price_since_entry or mark_price, mark_price)
            new_stop = new_low + atr * multiplier
            if new_stop >= position.stop_loss_price:
                return
            updated_stop = new_stop
            updated_peak = new_low
        self._positions.upsert(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
            side=position.side,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=position.unrealized_pnl,
            stop_loss_price=updated_stop,
            highest_price_since_entry=updated_peak,
        )
        self._session.commit()

    def _compute_atr_from_candles(self, candles: list) -> Decimal | None:
        from app.domain.strategies.indicators import calculate_atr

        period = self._settings.stop_loss_atr_period
        if len(candles) < period + 1:
            return None
        recent = sorted(candles, key=lambda c: c.open_time)[-(period + 1) :]
        try:
            return calculate_atr(
                highs=[c.high_price for c in recent],
                lows=[c.low_price for c in recent],
                closes=[c.close_price for c in recent],
                period=period,
            )
        except ValueError:
            return None

    def _mark_open_position_to_market_for_symbol(self, symbol: str, mark_price: Decimal) -> None:
        position = self._positions.get(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
        )
        if (
            position is None
            or position.quantity <= Decimal("0")
            or position.average_entry_price is None
        ):
            return
        if position.side == "long":
            unrealized_pnl = (mark_price - position.average_entry_price) * position.quantity
        else:
            unrealized_pnl = (position.average_entry_price - mark_price) * position.quantity
        self._positions.upsert(
            exchange=self._settings.exchange_name,
            symbol=symbol,
            trading_mode=self._settings.trading_mode,
            mode=self._trading_mode,
            side=position.side,
            quantity=position.quantity,
            average_entry_price=position.average_entry_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=unrealized_pnl,
        )
        self._session.commit()

    def _get_risk_for_symbol(self, symbol: str) -> RiskService:
        if self._risk_override is not None:
            return self._risk_override

        symbol_rules = SymbolRulesService(self._session).get_rules(
            exchange=self._settings.exchange_name,
            symbol=symbol,
        )
        limits = dataclasses.replace(self._risk_limits_base, symbol_rules=symbol_rules)
        return RiskService(limits)

    @staticmethod
    def _has_open_quantity(position: PositionRecord | None) -> bool:
        return position is not None and position.quantity > Decimal("0")

    def _build_client_order_id_for_symbol(
        self, symbol: str, timeframe: str, signal: Signal, close_time: datetime
    ) -> str:
        symbol_token = symbol.replace("/", "-").lower()
        candle_token = close_time.strftime("%Y%m%d%H%M%S")
        return (
            f"{self._trading_mode}-{self._settings.trading_mode}-{self._settings.exchange_name}-"
            f"{symbol_token}-{timeframe}-{signal.action}-{candle_token}"
        )

    @property
    def _active_symbols(self) -> list[str]:
        if self._settings.trading_symbols:
            return self._settings.trading_symbols
        return [self._symbol]

    @staticmethod
    def _build_strategy(
        operator_config: OperatorRuntimeConfig | None,
        settings: Settings,
    ) -> Strategy:
        strategy_name = (
            operator_config.strategy_name if operator_config is not None else "ema_crossover"
        )
        fast = (
            operator_config.fast_period
            if operator_config is not None
            else settings.strategy_fast_period
        )
        slow = (
            operator_config.slow_period
            if operator_config is not None
            else settings.strategy_slow_period
        )
        if strategy_name == "macd_crossover":
            return MacdCrossoverStrategy(
                fast_period=fast,
                slow_period=slow,
                signal_period=9,
            )
        if strategy_name == "mean_reversion_bollinger":
            return MeanReversionBollingerStrategy(
                bb_period=20,
                bb_std_dev=Decimal("2"),
                rsi_period=14,
                rsi_oversold=Decimal("35"),
                rsi_overbought=Decimal("65"),
            )
        if strategy_name == "rsi_momentum":
            return RsiMomentumStrategy(rsi_period=14)
        if strategy_name == "breakout_atr":
            return BreakoutAtrStrategy(
                breakout_period=20,
                atr_period=14,
                atr_breakout_multiplier=Decimal("0.5"),
                atr_stop_multiplier=Decimal("2.0"),
            )
        # ema_crossover (default) and rule_builder fall back to EMA
        return EmaCrossoverStrategy(
            fast_period=fast,
            slow_period=slow,
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
            adx_period=(
                settings.strategy_adx_period if settings.strategy_adx_filter_enabled else None
            ),
            adx_threshold=Decimal(str(settings.strategy_adx_threshold)),
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

    @property
    def _min_required_candles(self) -> int:
        strategy_name = (
            self._operator_config.strategy_name
            if self._operator_config is not None
            else "ema_crossover"
        )
        if strategy_name == "macd_crossover":
            return self._slow_period + 9 + 1  # slow + signal_period + 1
        if strategy_name == "mean_reversion_bollinger":
            return max(20, 14 + 1) + 1  # max(bb_period, rsi_period+1) + 1
        if strategy_name == "rsi_momentum":
            return 14 + 2
        if strategy_name == "breakout_atr":
            return max(20, 14) + 2  # max(breakout_period, atr_period) + 2
        return self._slow_period + 1  # ema_crossover and rule_builder
