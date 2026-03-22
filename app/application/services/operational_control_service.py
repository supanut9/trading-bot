from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from app.application.services.audit_service import AuditService
from app.application.services.backtest_run_history_service import BacktestRunHistoryService
from app.application.services.backtest_service import (
    BacktestResult,
    BacktestService,
    WalkForwardResult,
)
from app.application.services.live_fill_reconciliation_service import (
    LiveFillReconciliationService,
)
from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.live_order_state import (
    CANCELABLE_LIVE_ORDER_STATUSES,
    resolve_cancellation_state,
    transition_live_order,
)
from app.application.services.live_readiness_service import LiveReadinessService
from app.application.services.market_data_service import MarketDataService
from app.application.services.market_data_sync_service import MarketDataSyncService
from app.application.services.model_registry import (
    default_model_path,
    load_model,
)
from app.application.services.notification_service import (
    NotificationService,
    build_notification_service,
)
from app.application.services.operator_runtime_config_service import (
    OPERATOR_STRATEGY_EMA_CROSSOVER,
    OperatorRuntimeConfig,
    OperatorRuntimeConfigService,
)
from app.application.services.symbol_rules_service import SymbolRulesService
from app.application.services.worker_orchestration_service import WorkerOrchestrationService
from app.config import Settings
from app.domain.risk import RiskLimits, RiskService
from app.domain.strategies.base import Candle, Strategy
from app.domain.strategies.breakout_atr import BreakoutAtrStrategy
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.domain.strategies.macd_crossover import MacdCrossoverStrategy
from app.domain.strategies.mean_reversion_bollinger import MeanReversionBollingerStrategy
from app.domain.strategies.ml_signal import MLSignalStrategy
from app.domain.strategies.rsi_momentum import RsiMomentumStrategy
from app.domain.strategies.rule_builder import (
    RuleBuilderStrategy,
    RuleBuilderStrategyConfig,
    StrategyRuleCondition,
    StrategyRuleGroup,
)
from app.infrastructure.database.models.candle import CandleRecord
from app.infrastructure.database.repositories.order_repository import OrderRepository
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.exchanges.factory import (
    build_live_order_exchange_client,
    build_market_data_exchange_client,
)

BACKTEST_STRATEGY_EMA_CROSSOVER = OPERATOR_STRATEGY_EMA_CROSSOVER
BACKTEST_STRATEGY_RULE_BUILDER = "rule_builder"
BACKTEST_STRATEGY_MACD_CROSSOVER = "macd_crossover"
BACKTEST_STRATEGY_MEAN_REVERSION_BOLLINGER = "mean_reversion_bollinger"
BACKTEST_STRATEGY_RSI_MOMENTUM = "rsi_momentum"
BACKTEST_STRATEGY_BREAKOUT_ATR = "breakout_atr"
BACKTEST_STRATEGY_XGBOOST_SIGNAL = "xgboost_signal"
BACKTEST_STRATEGY_ML_SIGNAL = "ml_signal"

_ALL_BACKTEST_STRATEGIES = {
    BACKTEST_STRATEGY_EMA_CROSSOVER,
    BACKTEST_STRATEGY_RULE_BUILDER,
    BACKTEST_STRATEGY_MACD_CROSSOVER,
    BACKTEST_STRATEGY_MEAN_REVERSION_BOLLINGER,
    BACKTEST_STRATEGY_RSI_MOMENTUM,
    BACKTEST_STRATEGY_BREAKOUT_ATR,
    BACKTEST_STRATEGY_XGBOOST_SIGNAL,
    BACKTEST_STRATEGY_ML_SIGNAL,
}

_TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
    "3d": 4320,
    "1w": 10080,
}
_BACKTEST_MIN_DAYS = 7


def _compute_backtest_sync_limit(timeframe: str, required_candles: int) -> int:
    """Return how many candles to fetch for a backtest.

    Always covers at least 7 days of history so small-timeframe strategies
    have enough bars to produce signals, regardless of strategy warm-up size.
    """
    minutes = _TIMEFRAME_MINUTES.get(timeframe, 60)
    seven_day_candles = (_BACKTEST_MIN_DAYS * 24 * 60) // minutes
    return max(required_candles + 100, seven_day_candles)


@dataclass(frozen=True, slots=True)
class BacktestRunOptions:
    strategy_name: str = BACKTEST_STRATEGY_EMA_CROSSOVER
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    starting_equity: Decimal | None = None
    slippage_pct: Decimal | None = None
    fee_pct: Decimal | None = None
    walk_forward_split_ratio: Decimal | None = None
    rules: RuleBuilderStrategyConfig | None = None
    rsi_period: int | None = None
    rsi_overbought: Decimal | None = None
    rsi_oversold: Decimal | None = None
    volume_ma_period: int | None = None
    # MACD crossover params
    macd_signal_period: int | None = None
    # Bollinger mean-reversion params
    bb_period: int | None = None
    bb_std_dev: Decimal | None = None
    # Breakout ATR params
    breakout_period: int | None = None
    atr_period: int | None = None
    atr_breakout_multiplier: Decimal | None = None
    atr_stop_multiplier: Decimal | None = None
    # ADX regime filter
    adx_period: int | None = None
    adx_threshold: Decimal | None = None
    # Multi-timeframe confirmation
    multi_tf_timeframe: str | None = None
    multi_tf_period: int | None = None
    trading_mode: str = "SPOT"
    leverage: int | None = None  # None = auto-fetch for FUTURES
    margin_mode: str = "ISOLATED"
    # XGBoost / ML strategy params
    xgb_model_path: str | None = None
    xgb_buy_threshold: Decimal | None = None
    xgb_sell_threshold: Decimal | None = None
    model_type: str | None = None  # "xgboost" | "lightgbm" | "random_forest"
    oos_only: bool = False  # if True, slice candles to OOS window only


def required_candles_for_backtest_options(options: BacktestRunOptions) -> int:
    sname = options.strategy_name
    if sname == BACKTEST_STRATEGY_RULE_BUILDER and options.rules is not None:
        return options.rules.minimum_candles()
    if sname == BACKTEST_STRATEGY_MACD_CROSSOVER:
        slow = options.slow_period or 26
        sig = options.macd_signal_period or 9
        return slow + sig + 1
    if sname == BACKTEST_STRATEGY_MEAN_REVERSION_BOLLINGER:
        bb = options.bb_period or 20
        rsi = options.rsi_period or 14
        return max(bb, rsi + 1) + 1
    if sname == BACKTEST_STRATEGY_RSI_MOMENTUM:
        return (options.rsi_period or 14) + 2
    if sname == BACKTEST_STRATEGY_BREAKOUT_ATR:
        bp = options.breakout_period or 20
        ap = options.atr_period or 14
        return max(bp, ap) + 2
    if sname in (BACKTEST_STRATEGY_XGBOOST_SIGNAL, BACKTEST_STRATEGY_ML_SIGNAL):
        return 37  # MIN_CANDLES_FOR_FEATURES
    base = max((options.slow_period or 0) + 1, 0)
    rsi_min = (options.rsi_period + 1) if options.rsi_period is not None else 0
    vol_min = options.volume_ma_period if options.volume_ma_period is not None else 0
    adx_min = (2 * options.adx_period + 1) if options.adx_period is not None else 0
    return max(base, rsi_min, vol_min, adx_min)


def _fill_ema_periods(
    config: "RuleBuilderStrategyConfig",
    fast_period: int | None,
    slow_period: int | None,
) -> "RuleBuilderStrategyConfig":
    """Fill fast_period/slow_period on all ema_cross conditions that have them unset."""

    def fill_group(group: "StrategyRuleGroup") -> "StrategyRuleGroup":
        filled = []
        for cond in group.conditions:
            if cond.indicator == "ema_cross":
                cond = replace(
                    cond,
                    fast_period=cond.fast_period if cond.fast_period is not None else fast_period,
                    slow_period=cond.slow_period if cond.slow_period is not None else slow_period,
                )
            filled.append(cond)
        return replace(group, conditions=tuple(filled))

    return replace(
        config,
        shared_filters=fill_group(config.shared_filters),
        buy_rules=fill_group(config.buy_rules),
        sell_rules=fill_group(config.sell_rules),
    )


@dataclass(frozen=True, slots=True)
class BacktestExecutionResult:
    action: str
    price: Decimal
    fill_price: Decimal
    quantity: Decimal
    fee: Decimal
    realized_pnl: Decimal
    reason: str
    candle_open_time: datetime = datetime.min
    liquidation_price: Decimal | None = None
    was_liquidated: bool = False


@dataclass(frozen=True, slots=True)
class BacktestCandleResult:
    open_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


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
class WalkForwardControlResult:
    split_ratio: Decimal
    in_sample_candles: int
    out_of_sample_candles: int
    in_sample_total_return_pct: Decimal
    in_sample_max_drawdown_pct: Decimal
    in_sample_total_trades: int
    in_sample_winning_trades: int
    in_sample_losing_trades: int
    out_of_sample_total_return_pct: Decimal
    out_of_sample_max_drawdown_pct: Decimal
    out_of_sample_total_trades: int
    out_of_sample_winning_trades: int
    out_of_sample_losing_trades: int
    return_degradation_pct: Decimal
    overfitting_warning: bool
    overfitting_threshold_pct: Decimal


@dataclass(frozen=True, slots=True)
class BacktestControlResult:
    status: str
    detail: str
    notified: bool
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int | None
    slow_period: int | None
    starting_equity_input: Decimal
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
    total_fees_paid: Decimal | None = None
    slippage_pct: Decimal | None = None
    fee_pct: Decimal | None = None
    walk_forward: WalkForwardControlResult | None = None
    rules: RuleBuilderStrategyConfig | None = None
    executions: tuple[BacktestExecutionResult, ...] = ()
    candles: tuple[BacktestCandleResult, ...] = ()
    adx_period: int | None = None
    adx_threshold: Decimal | None = None
    leverage: int = 1
    margin_mode: str = "ISOLATED"
    liquidation_count: int = 0
    stop_loss_count: int = 0
    trading_mode: str = "SPOT"


@dataclass(frozen=True, slots=True)
class MarketSyncControlResult:
    status: str
    detail: str
    symbol: str
    timeframe: str
    limit: int
    backfill: bool
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class MarketSyncRunOptions:
    symbol: str | None = None
    timeframe: str | None = None
    limit: int | None = None
    backfill: bool = False


@dataclass(frozen=True, slots=True)
class LiveReconcileControlResult:
    status: str
    detail: str
    reconciled_count: int
    filled_count: int
    review_required_count: int
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveCancelControlResult:
    status: str
    detail: str
    order_id: int | None
    client_order_id: str | None
    exchange_order_id: str | None
    order_status: str | None
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveHaltControlResult:
    status: str
    detail: str
    live_trading_halted: bool
    changed: bool
    notified: bool = False


@dataclass(frozen=True, slots=True)
class LiveReadinessCheckResult:
    name: str
    passed: bool
    severity: str
    detail: str


@dataclass(frozen=True, slots=True)
class LiveReadinessControlResult:
    status: str
    detail: str
    ready: bool
    checks: tuple[LiveReadinessCheckResult, ...]
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OperatorConfigControlResult:
    status: str
    detail: str
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    trading_mode: str
    source: str
    changed: bool = False
    notified: bool = False


@dataclass(frozen=True, slots=True)
class SymbolRulesControlResult:
    status: str
    detail: str
    exchange: str
    symbol: str
    min_qty: Decimal | None = None
    max_qty: Decimal | None = None
    step_size: Decimal | None = None
    min_notional: Decimal | None = None
    tick_size: Decimal | None = None
    fetched_at: str | None = None
    source: str | None = None


class OperationalControlService:
    _decimal_precision = Decimal("0.00000001")

    def __init__(
        self,
        settings: Settings,
        *,
        session_factory: sessionmaker[Session] | None = None,
        notifications: NotificationService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory or create_session_factory(settings)
        self._notifications = notifications or build_notification_service(
            settings,
            session_factory=self._session_factory,
        )
        self._audit = audit or AuditService(session_factory=self._session_factory)
        self._backtest_runs = BacktestRunHistoryService(session_factory=self._session_factory)

    def run_worker_cycle(
        self,
        *,
        source: str = "internal",
        audit: bool = True,
    ) -> WorkerControlResult:
        with self._session_factory() as session:
            operator_config = OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()
            result = WorkerOrchestrationService(
                session,
                self._settings,
                operator_config=operator_config,
            ).run_cycle()

        notified = self._notifications.notify_worker_cycle(self._settings, result)
        control_result = WorkerControlResult(
            status=result.status,
            detail=result.detail,
            signal_action=result.signal_action,
            client_order_id=result.client_order_id,
            order_id=result.order_id,
            trade_id=result.trade_id,
            position_quantity=result.position_quantity,
            notified=notified,
        )
        if audit:
            self._audit.record_control_result(
                control_type="worker_cycle",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "signal_action": control_result.signal_action,
                    "client_order_id": control_result.client_order_id,
                    "order_id": control_result.order_id,
                    "trade_id": control_result.trade_id,
                    "position_quantity": control_result.position_quantity,
                    "notified": control_result.notified,
                },
            )
        return control_result

    def run_market_sync(
        self,
        *,
        options: MarketSyncRunOptions | None = None,
        source: str = "internal",
        audit: bool = True,
    ) -> MarketSyncControlResult:
        active = options or MarketSyncRunOptions()
        resolved_limit = (
            active.limit if active.limit is not None else self._settings.market_data_sync_limit
        )
        with self._session_factory() as session:
            operator_config = OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()
            resolved_symbol = (active.symbol or operator_config.symbol).strip()
            resolved_timeframe = (active.timeframe or operator_config.timeframe).strip()
            try:
                svc = MarketDataSyncService(
                    session,
                    build_market_data_exchange_client(self._settings),
                )
                if resolved_limit > 1000:
                    result = svc.sync_candles_paginated(
                        exchange=self._settings.exchange_name,
                        symbol=resolved_symbol,
                        timeframe=resolved_timeframe,
                        total_limit=resolved_limit,
                    )
                else:
                    result = svc.sync_recent_closed_candles(
                        exchange=self._settings.exchange_name,
                        symbol=resolved_symbol,
                        timeframe=resolved_timeframe,
                        limit=resolved_limit,
                        backfill=active.backfill,
                    )
            except Exception:
                failed = MarketSyncControlResult(
                    status="failed",
                    detail="market data sync failed",
                    symbol=resolved_symbol,
                    timeframe=resolved_timeframe,
                    limit=resolved_limit,
                    backfill=active.backfill,
                    fetched_count=0,
                    stored_count=0,
                )
                notified = self._notifications.notify_market_sync(self._settings, failed)
                control_result = MarketSyncControlResult(
                    status=failed.status,
                    detail=failed.detail,
                    symbol=failed.symbol,
                    timeframe=failed.timeframe,
                    fetched_count=failed.fetched_count,
                    stored_count=failed.stored_count,
                    latest_open_time=failed.latest_open_time,
                    notified=notified,
                )
                if audit:
                    self._audit.record_control_result(
                        control_type="market_sync",
                        source=source,
                        status=control_result.status,
                        detail=control_result.detail,
                        settings=self._settings,
                        payload={
                            "symbol": control_result.symbol,
                            "timeframe": control_result.timeframe,
                            "limit": control_result.limit,
                            "backfill": control_result.backfill,
                            "fetched_count": control_result.fetched_count,
                            "stored_count": control_result.stored_count,
                            "latest_open_time": control_result.latest_open_time,
                            "notified": control_result.notified,
                        },
                    )
                return control_result

        detail = "market data sync completed"
        if active.backfill:
            detail = "market data backfill completed"
        if result.fetched_count == 0:
            detail = "no candles fetched"
        elif result.stored_count == 0:
            detail = "no new candles stored" if not active.backfill else "no candles stored"

        completed = MarketSyncControlResult(
            status="completed",
            detail=detail,
            symbol=resolved_symbol,
            timeframe=resolved_timeframe,
            limit=resolved_limit,
            backfill=active.backfill,
            fetched_count=result.fetched_count,
            stored_count=result.stored_count,
            latest_open_time=result.latest_open_time,
        )
        notified = self._notifications.notify_market_sync(self._settings, completed)
        control_result = MarketSyncControlResult(
            status=completed.status,
            detail=completed.detail,
            symbol=completed.symbol,
            timeframe=completed.timeframe,
            limit=completed.limit,
            backfill=completed.backfill,
            fetched_count=completed.fetched_count,
            stored_count=completed.stored_count,
            latest_open_time=completed.latest_open_time,
            notified=notified,
        )
        if audit:
            self._audit.record_control_result(
                control_type="market_sync",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "limit": control_result.limit,
                    "backfill": control_result.backfill,
                    "fetched_count": control_result.fetched_count,
                    "stored_count": control_result.stored_count,
                    "latest_open_time": control_result.latest_open_time,
                    "notified": control_result.notified,
                },
            )
        return control_result

    def run_backtest(
        self,
        *,
        options: BacktestRunOptions | None = None,
        notify: bool = True,
        source: str = "internal",
        audit: bool = True,
        record_history: bool = True,
    ) -> BacktestControlResult:
        defaults = self._get_effective_operator_config()
        resolved_leverage = 1
        try:
            resolved = self._resolve_backtest_options(options, defaults=defaults)
            resolved_leverage = self._resolve_leverage(
                requested_leverage=resolved.leverage,
                symbol=resolved.symbol,
                trading_mode=resolved.trading_mode,
            )
            resolved = replace(resolved, leverage=resolved_leverage)
        except ValueError as exc:
            preview = self._preview_backtest_options(options, defaults=defaults)
            control_result = BacktestControlResult(
                status="failed",
                detail=str(exc),
                notified=False,
                strategy_name=preview.strategy_name,
                exchange=preview.exchange,
                symbol=preview.symbol,
                timeframe=preview.timeframe,
                fast_period=preview.fast_period,
                slow_period=preview.slow_period,
                starting_equity_input=self._quantize_decimal(preview.starting_equity)
                or Decimal("0"),
                candle_count=0,
                required_candles=self._required_candles_for_options(preview),
                rules=preview.rules,
                trading_mode=preview.trading_mode,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="backtest",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "strategy_name": control_result.strategy_name,
                        "exchange": control_result.exchange,
                        "symbol": control_result.symbol,
                        "timeframe": control_result.timeframe,
                        "fast_period": control_result.fast_period,
                        "slow_period": control_result.slow_period,
                        "starting_equity_input": control_result.starting_equity_input,
                        "candle_count": control_result.candle_count,
                        "required_candles": control_result.required_candles,
                        "rule_builder": control_result.rules is not None,
                        "notified": control_result.notified,
                    },
                )
            if record_history:
                self._backtest_runs.record_run(source=source, result=control_result)
            return control_result
        required_candles = self._required_candles_for_options(resolved)
        sync_limit = _compute_backtest_sync_limit(resolved.timeframe, required_candles)

        with self._session_factory() as session:
            try:
                MarketDataSyncService(
                    session, build_market_data_exchange_client(self._settings)
                ).sync_candles_paginated(
                    exchange=resolved.exchange,
                    symbol=resolved.symbol,
                    timeframe=resolved.timeframe,
                    total_limit=sync_limit,
                )
                session.commit()
            except Exception as exc:
                from app.core.logger import get_logger as _get_logger

                _get_logger(__name__).warning(
                    "backtest_auto_sync_failed exchange=%s symbol=%s timeframe=%s error=%s",
                    resolved.exchange,
                    resolved.symbol,
                    resolved.timeframe,
                    exc,
                )

        # HTF confirmation: resolve which HTF timeframe and period to use
        effective_htf_timeframe: str | None = resolved.multi_tf_timeframe or (
            self._settings.multi_tf_confirmation_timeframe
            if self._settings.multi_tf_confirmation_enabled
            else None
        )
        effective_htf_period: int = resolved.multi_tf_period or (
            self._settings.multi_tf_confirmation_period
            if self._settings.multi_tf_confirmation_enabled
            else 21
        )
        htf_candles: list[Candle] = []
        if effective_htf_timeframe:
            htf_sync_limit = _compute_backtest_sync_limit(
                effective_htf_timeframe, effective_htf_period + 30
            )
            with self._session_factory() as session:
                try:
                    MarketDataSyncService(
                        session, build_market_data_exchange_client(self._settings)
                    ).sync_candles_paginated(
                        exchange=resolved.exchange,
                        symbol=resolved.symbol,
                        timeframe=effective_htf_timeframe,
                        total_limit=htf_sync_limit,
                    )
                    session.commit()
                except Exception as exc:
                    from app.core.logger import get_logger as _get_logger

                    _get_logger(__name__).warning(
                        "backtest_htf_sync_failed exchange=%s symbol=%s timeframe=%s error=%s",
                        resolved.exchange,
                        resolved.symbol,
                        effective_htf_timeframe,
                        exc,
                    )
            with self._session_factory() as session:
                htf_records = MarketDataService(session).list_historical_candles(
                    exchange=resolved.exchange,
                    symbol=resolved.symbol,
                    timeframe=effective_htf_timeframe,
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

        with self._session_factory() as session:
            records = MarketDataService(session).list_historical_candles(
                exchange=resolved.exchange,
                symbol=resolved.symbol,
                timeframe=resolved.timeframe,
            )
            candle_count = len(records)

            # OOS-only: skip the training portion of candles
            if resolved.oos_only and records:
                try:
                    mt = resolved.model_type or "xgboost"
                    mp = resolved.xgb_model_path or default_model_path(
                        symbol=resolved.symbol,
                        timeframe=resolved.timeframe,
                        model_type=mt,
                    )
                    loaded_meta = load_model(mp)
                    oos_start = loaded_meta.metadata.oos_start_index
                    if oos_start > 0 and oos_start < len(records):
                        records = records[oos_start:]
                        candle_count = len(records)
                except Exception:
                    pass  # if model not found, run on all candles

            if not records:
                backtest_result = None
                walk_forward_result = None
                status = "skipped"
                detail = "no_candles"
            elif candle_count < required_candles:
                backtest_result = None
                walk_forward_result = None
                status = "skipped"
                detail = "not_enough_candles"
            else:
                backtest_result = self._run_backtest_from_records(
                    records,
                    options=resolved,
                    htf_candles=htf_candles,
                    htf_period=effective_htf_period,
                )
                walk_forward_result = (
                    self._run_walk_forward_from_records(
                        records,
                        options=resolved,
                        htf_candles=htf_candles,
                        htf_period=effective_htf_period,
                    )
                    if resolved.walk_forward_split_ratio is not None
                    else None
                )
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
            control_result = BacktestControlResult(
                status=status,
                detail=detail,
                notified=notified,
                strategy_name=resolved.strategy_name,
                exchange=resolved.exchange,
                symbol=resolved.symbol,
                timeframe=resolved.timeframe,
                fast_period=resolved.fast_period,
                slow_period=resolved.slow_period,
                starting_equity_input=self._quantize_decimal(resolved.starting_equity)
                or Decimal("0"),
                candle_count=candle_count,
                required_candles=required_candles,
                rules=resolved.rules,
                trading_mode=resolved.trading_mode,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="backtest",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "strategy_name": control_result.strategy_name,
                        "exchange": control_result.exchange,
                        "symbol": control_result.symbol,
                        "timeframe": control_result.timeframe,
                        "fast_period": control_result.fast_period,
                        "slow_period": control_result.slow_period,
                        "starting_equity_input": control_result.starting_equity_input,
                        "candle_count": control_result.candle_count,
                        "required_candles": control_result.required_candles,
                        "rule_builder": control_result.rules is not None,
                        "notified": control_result.notified,
                    },
                )
            if record_history:
                self._backtest_runs.record_run(source=source, result=control_result)
            return control_result

        notified = False
        if notify:
            notified = self._notifications.notify_backtest_completed(
                self._settings,
                backtest_result,
            )
        control_result = BacktestControlResult(
            status=status,
            detail=detail,
            notified=notified,
            strategy_name=resolved.strategy_name,
            exchange=resolved.exchange,
            symbol=resolved.symbol,
            timeframe=resolved.timeframe,
            fast_period=resolved.fast_period,
            slow_period=resolved.slow_period,
            starting_equity_input=self._quantize_decimal(resolved.starting_equity) or Decimal("0"),
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
            total_fees_paid=self._quantize_decimal(backtest_result.total_fees_paid),
            slippage_pct=self._quantize_decimal(backtest_result.slippage_pct),
            fee_pct=self._quantize_decimal(backtest_result.fee_pct),
            walk_forward=self._build_walk_forward_control_result(walk_forward_result),
            rules=resolved.rules,
            adx_period=resolved.adx_period,
            adx_threshold=resolved.adx_threshold,
            leverage=resolved_leverage,
            margin_mode=resolved.margin_mode,
            liquidation_count=backtest_result.liquidation_count,
            stop_loss_count=backtest_result.stop_loss_count,
            trading_mode=resolved.trading_mode,
            executions=tuple(
                BacktestExecutionResult(
                    action=execution.action,
                    price=self._quantize_decimal(execution.price) or Decimal("0"),
                    fill_price=self._quantize_decimal(execution.fill_price) or Decimal("0"),
                    quantity=self._quantize_decimal(execution.quantity) or Decimal("0"),
                    fee=self._quantize_decimal(execution.fee) or Decimal("0"),
                    realized_pnl=self._quantize_decimal(execution.realized_pnl) or Decimal("0"),
                    reason=execution.reason,
                    candle_open_time=execution.candle_open_time,
                    liquidation_price=self._quantize_decimal(execution.liquidation_price),
                    was_liquidated=execution.was_liquidated,
                )
                for execution in backtest_result.executions
            ),
            candles=tuple(
                BacktestCandleResult(
                    open_time=c.open_time,
                    open_price=self._quantize_decimal(c.open_price) or Decimal("0"),
                    high_price=self._quantize_decimal(c.high_price) or Decimal("0"),
                    low_price=self._quantize_decimal(c.low_price) or Decimal("0"),
                    close_price=self._quantize_decimal(c.close_price) or Decimal("0"),
                    volume=self._quantize_decimal(c.volume) or Decimal("0"),
                )
                for c in backtest_result.candles
            ),
        )
        if audit:
            self._audit.record_control_result(
                control_type="backtest",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "strategy_name": control_result.strategy_name,
                    "exchange": control_result.exchange,
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "fast_period": control_result.fast_period,
                    "slow_period": control_result.slow_period,
                    "starting_equity_input": control_result.starting_equity_input,
                    "candle_count": control_result.candle_count,
                    "required_candles": control_result.required_candles,
                    "rule_builder": control_result.rules is not None,
                    "starting_equity": control_result.starting_equity,
                    "ending_equity": control_result.ending_equity,
                    "realized_pnl": control_result.realized_pnl,
                    "total_return_pct": control_result.total_return_pct,
                    "max_drawdown_pct": control_result.max_drawdown_pct,
                    "total_trades": control_result.total_trades,
                    "winning_trades": control_result.winning_trades,
                    "losing_trades": control_result.losing_trades,
                    "execution_count": len(control_result.executions),
                    "notified": control_result.notified,
                },
            )
        if record_history:
            self._backtest_runs.record_run(source=source, result=control_result)
        return control_result

    def run_live_reconcile(
        self,
        *,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveReconcileControlResult:
        try:
            with self._session_factory() as session:
                results = LiveFillReconciliationService(
                    session,
                    client=build_live_order_exchange_client(self._settings),
                ).reconcile_recent_live_orders()
        except Exception:
            control_result = LiveReconcileControlResult(
                status="failed",
                detail="live reconciliation failed",
                reconciled_count=0,
                filled_count=0,
                review_required_count=0,
                notified=False,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="live_reconcile",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "reconciled_count": control_result.reconciled_count,
                        "filled_count": control_result.filled_count,
                        "review_required_count": control_result.review_required_count,
                    },
                )
            return control_result

        reconciled_count = len(results)
        filled_count = sum(1 for result in results if result.trade_created)
        review_required_count = sum(1 for result in results if result.requires_operator_review)
        detail = "no live orders to reconcile"
        if reconciled_count > 0:
            detail = "live orders reconciled"
        if review_required_count > 0:
            detail = "live orders require operator review"
        control_result = LiveReconcileControlResult(
            status="completed",
            detail=detail,
            reconciled_count=reconciled_count,
            filled_count=filled_count,
            review_required_count=review_required_count,
            notified=False,
        )
        if audit:
            self._audit.record_control_result(
                control_type="live_reconcile",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "reconciled_count": control_result.reconciled_count,
                    "filled_count": control_result.filled_count,
                    "review_required_count": control_result.review_required_count,
                },
            )
        return control_result

    def run_live_halt(
        self,
        *,
        halted: bool,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveHaltControlResult:
        if not halted and self._settings.live_trading_enabled:
            with self._session_factory() as session:
                readiness = LiveReadinessService(session, self._settings).build_report()
                if not readiness.ready:
                    control_result = LiveHaltControlResult(
                        status="failed",
                        detail="cannot resume live trading: readiness checks failed",
                        live_trading_halted=True,
                        changed=False,
                    )
                    if audit:
                        self._audit.record_control_result(
                            control_type="live_halt",
                            source=source,
                            status=control_result.status,
                            detail=control_result.detail,
                            settings=self._settings,
                            payload={
                                "live_trading_halted": control_result.live_trading_halted,
                                "changed": control_result.changed,
                                "reason": "live_readiness_failed",
                                "blocking_reasons": readiness.blocking_reasons,
                            },
                        )
                    return control_result

        with self._session_factory() as session:
            control_update = LiveOperatorControlService(
                session,
                self._settings,
            ).set_live_trading_halted(
                halted=halted,
                updated_by=source,
            )
            session.commit()

        detail = "live entry halted" if halted else "live entry resumed"
        if not control_update.changed:
            detail = "live entry halt state unchanged"

        control_result = LiveHaltControlResult(
            status="completed",
            detail=detail,
            live_trading_halted=control_update.current_halted,
            changed=control_update.changed,
            notified=False,
        )
        if audit:
            self._audit.record_control_result(
                control_type="live_halt",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "previous_halted": control_update.previous_halted,
                    "live_trading_halted": control_result.live_trading_halted,
                    "changed": control_result.changed,
                    "updated_by": control_update.updated_by,
                },
            )
        return control_result

    def get_live_readiness(self) -> LiveReadinessControlResult:
        with self._session_factory() as session:
            report = LiveReadinessService(session, self._settings).build_report()
        return LiveReadinessControlResult(
            status="completed",
            detail="live readiness evaluated",
            ready=report.ready,
            checks=tuple(
                LiveReadinessCheckResult(
                    name=check.name,
                    passed=check.passed,
                    severity=check.severity,
                    detail=check.detail,
                )
                for check in report.checks
            ),
            blocking_reasons=tuple(report.blocking_reasons),
        )

    def get_operator_config(self) -> OperatorConfigControlResult:
        config = self._get_effective_operator_config()
        return OperatorConfigControlResult(
            status="completed",
            detail="operator runtime config loaded",
            strategy_name=config.strategy_name,
            exchange=config.exchange,
            symbol=config.symbol,
            timeframe=config.timeframe,
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            trading_mode=config.trading_mode,
            source=config.source,
        )

    def get_symbol_rules(self) -> SymbolRulesControlResult:
        config = self._get_effective_operator_config()
        with self._session_factory() as session:
            result = SymbolRulesService(session).get_rules_result(
                exchange=self._settings.exchange_name,
                symbol=config.symbol,
            )
        if result is None:
            return SymbolRulesControlResult(
                status="not_found",
                detail="no symbol rules stored; run refresh to fetch from exchange",
                exchange=self._settings.exchange_name,
                symbol=config.symbol,
            )
        return SymbolRulesControlResult(
            status="completed",
            detail="symbol rules loaded from database",
            exchange=result.exchange,
            symbol=result.symbol,
            min_qty=result.min_qty,
            max_qty=result.max_qty,
            step_size=result.step_size,
            min_notional=result.min_notional,
            tick_size=result.tick_size,
            fetched_at=result.fetched_at,
            source=result.source,
        )

    def refresh_symbol_rules(self, *, source: str = "internal") -> SymbolRulesControlResult:
        config = self._get_effective_operator_config()
        try:
            with self._session_factory() as session:
                result = SymbolRulesService(session).refresh_rules(
                    exchange_client=build_market_data_exchange_client(self._settings),
                    exchange=self._settings.exchange_name,
                    symbol=config.symbol,
                )
        except Exception as exc:
            return SymbolRulesControlResult(
                status="failed",
                detail=f"failed to refresh symbol rules: {exc}",
                exchange=self._settings.exchange_name,
                symbol=config.symbol,
            )
        return SymbolRulesControlResult(
            status="completed",
            detail="symbol rules refreshed from exchange",
            exchange=result.exchange,
            symbol=result.symbol,
            min_qty=result.min_qty,
            max_qty=result.max_qty,
            step_size=result.step_size,
            min_notional=result.min_notional,
            tick_size=result.tick_size,
            fetched_at=result.fetched_at,
            source=result.source,
        )

    def run_update_operator_config(
        self,
        *,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        fast_period: int,
        slow_period: int,
        trading_mode: str,
        source: str = "internal",
        audit: bool = True,
    ) -> OperatorConfigControlResult:
        try:
            with self._session_factory() as session:
                update = OperatorRuntimeConfigService(
                    session,
                    self._settings,
                ).set_config(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    fast_period=fast_period,
                    slow_period=slow_period,
                    trading_mode=trading_mode,
                    updated_by=source,
                )
                session.commit()
        except ValueError as exc:
            current = self.get_operator_config()
            return OperatorConfigControlResult(
                status="failed",
                detail=str(exc),
                strategy_name=strategy_name.strip().lower() or current.strategy_name,
                exchange=self._settings.exchange_name,
                symbol=symbol.strip() or current.symbol,
                timeframe=timeframe.strip() or current.timeframe,
                fast_period=fast_period,
                slow_period=slow_period,
                trading_mode=trading_mode,
                source=current.source,
            )

        control_result = OperatorConfigControlResult(
            status="completed",
            detail=(
                "operator runtime config updated"
                if update.changed
                else "operator runtime config unchanged"
            ),
            strategy_name=update.current.strategy_name,
            exchange=update.current.exchange,
            symbol=update.current.symbol,
            timeframe=update.current.timeframe,
            fast_period=update.current.fast_period,
            slow_period=update.current.slow_period,
            trading_mode=update.current.trading_mode,
            source=update.current.source,
            changed=update.changed,
        )
        if audit:
            self._audit.record_control_result(
                control_type="operator_config",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "strategy_name": control_result.strategy_name,
                    "exchange": control_result.exchange,
                    "symbol": control_result.symbol,
                    "timeframe": control_result.timeframe,
                    "fast_period": control_result.fast_period,
                    "slow_period": control_result.slow_period,
                    "config_source": control_result.source,
                    "changed": control_result.changed,
                },
            )
        return control_result

    def run_live_cancel(
        self,
        *,
        order_id: int | None = None,
        client_order_id: str | None = None,
        exchange_order_id: str | None = None,
        source: str = "internal",
        audit: bool = True,
    ) -> LiveCancelControlResult:
        provided_identifiers = [
            value is not None for value in (order_id, client_order_id, exchange_order_id)
        ]
        if sum(provided_identifiers) != 1:
            control_result = LiveCancelControlResult(
                status="failed",
                detail="exactly one live order identifier is required",
                order_id=order_id,
                client_order_id=client_order_id,
                exchange_order_id=exchange_order_id,
                order_status=None,
            )
            if audit:
                self._audit.record_control_result(
                    control_type="live_cancel",
                    source=source,
                    status=control_result.status,
                    detail=control_result.detail,
                    settings=self._settings,
                    payload={
                        "order_id": control_result.order_id,
                        "client_order_id": control_result.client_order_id,
                        "exchange_order_id": control_result.exchange_order_id,
                        "order_status": control_result.order_status,
                    },
                )
            return control_result

        with self._session_factory() as session:
            orders = OrderRepository(session)
            if order_id is not None:
                order = orders.get_by_id(order_id)
            elif client_order_id is not None:
                order = orders.get_by_client_order_id(client_order_id)
            else:
                order = orders.get_by_exchange_order_id(str(exchange_order_id))

            if order is None or order.mode != "live":
                control_result = LiveCancelControlResult(
                    status="failed",
                    detail="live order not found",
                    order_id=order_id,
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id,
                    order_status=None,
                )
            elif order.status not in CANCELABLE_LIVE_ORDER_STATUSES:
                control_result = LiveCancelControlResult(
                    status="skipped",
                    detail="live order is not cancelable in its current status",
                    order_id=order.id,
                    client_order_id=order.client_order_id,
                    exchange_order_id=order.exchange_order_id,
                    order_status=order.status,
                )
            else:
                try:
                    cancellation = build_live_order_exchange_client(self._settings).cancel_order(
                        symbol=order.symbol,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                    )
                    resolution = resolve_cancellation_state(cancellation.status)
                    transition_live_order(order, next_status=resolution.status)
                    if cancellation.exchange_order_id:
                        order.exchange_order_id = cancellation.exchange_order_id
                    session.commit()
                    control_result = LiveCancelControlResult(
                        status="completed",
                        detail=resolution.detail,
                        order_id=order.id,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        order_status=order.status,
                    )
                except Exception:
                    control_result = LiveCancelControlResult(
                        status="failed",
                        detail="live order cancel failed",
                        order_id=order.id,
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        order_status=order.status,
                    )

        if audit:
            self._audit.record_control_result(
                control_type="live_cancel",
                source=source,
                status=control_result.status,
                detail=control_result.detail,
                settings=self._settings,
                payload={
                    "order_id": control_result.order_id,
                    "client_order_id": control_result.client_order_id,
                    "exchange_order_id": control_result.exchange_order_id,
                    "order_status": control_result.order_status,
                },
            )
        return control_result

    def _run_backtest_from_records(
        self,
        records: Sequence[CandleRecord],
        *,
        options: BacktestRunOptions,
        htf_candles: Sequence[Candle] | None = None,
        htf_period: int = 21,
    ) -> BacktestResult:
        slippage_pct = (
            options.slippage_pct
            if options.slippage_pct is not None
            else Decimal(str(self._settings.backtest_slippage_pct))
        )
        fee_pct = (
            options.fee_pct
            if options.fee_pct is not None
            else Decimal(str(self._settings.backtest_fee_pct))
        )
        return BacktestService(
            strategy=self._build_backtest_strategy(options),
            risk_service=self._build_risk_service(),
            starting_equity=options.starting_equity,
            slippage_pct=slippage_pct,
            fee_pct=fee_pct,
            trading_mode=options.trading_mode,
            leverage=options.leverage or 1,
            margin_mode=options.margin_mode,
            stop_loss_atr_multiplier=Decimal(str(self._settings.stop_loss_atr_multiplier)),
            stop_loss_atr_period=self._settings.stop_loss_atr_period,
            trailing_stop_enabled=self._settings.trailing_stop_enabled,
            volatility_sizing_enabled=self._settings.volatility_sizing_enabled,
            volatility_sizing_atr_period=self._settings.volatility_sizing_atr_period,
            htf_candles=htf_candles or [],
            htf_period=htf_period,
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

    def _run_walk_forward_from_records(
        self,
        records: Sequence[CandleRecord],
        *,
        options: BacktestRunOptions,
        htf_candles: Sequence[Candle] | None = None,
        htf_period: int = 21,
    ) -> WalkForwardResult:
        slippage_pct = (
            options.slippage_pct
            if options.slippage_pct is not None
            else Decimal(str(self._settings.backtest_slippage_pct))
        )
        fee_pct = (
            options.fee_pct
            if options.fee_pct is not None
            else Decimal(str(self._settings.backtest_fee_pct))
        )
        candles = [
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
        return BacktestService(
            strategy=self._build_backtest_strategy(options),
            risk_service=self._build_risk_service(),
            starting_equity=options.starting_equity,
            slippage_pct=slippage_pct,
            fee_pct=fee_pct,
            trading_mode=options.trading_mode,
            leverage=options.leverage or 1,
            margin_mode=options.margin_mode,
            stop_loss_atr_multiplier=Decimal(str(self._settings.stop_loss_atr_multiplier)),
            stop_loss_atr_period=self._settings.stop_loss_atr_period,
            trailing_stop_enabled=self._settings.trailing_stop_enabled,
            volatility_sizing_enabled=self._settings.volatility_sizing_enabled,
            volatility_sizing_atr_period=self._settings.volatility_sizing_atr_period,
            htf_candles=htf_candles or [],
            htf_period=htf_period,
        ).run_walk_forward(
            candles,
            split_ratio=options.walk_forward_split_ratio or Decimal("0.7"),
            overfitting_threshold_pct=Decimal(
                str(self._settings.backtest_overfitting_threshold_pct)
            ),
        )

    def _build_walk_forward_control_result(
        self,
        wf: WalkForwardResult | None,
    ) -> WalkForwardControlResult | None:
        if wf is None:
            return None
        q = self._quantize_decimal
        return WalkForwardControlResult(
            split_ratio=q(wf.split_ratio) or Decimal("0"),
            in_sample_candles=wf.in_sample_candles,
            out_of_sample_candles=wf.out_of_sample_candles,
            in_sample_total_return_pct=q(wf.in_sample.total_return_pct) or Decimal("0"),
            in_sample_max_drawdown_pct=q(wf.in_sample.max_drawdown_pct) or Decimal("0"),
            in_sample_total_trades=wf.in_sample.total_trades,
            in_sample_winning_trades=wf.in_sample.winning_trades,
            in_sample_losing_trades=wf.in_sample.losing_trades,
            out_of_sample_total_return_pct=q(wf.out_of_sample.total_return_pct) or Decimal("0"),
            out_of_sample_max_drawdown_pct=q(wf.out_of_sample.max_drawdown_pct) or Decimal("0"),
            out_of_sample_total_trades=wf.out_of_sample.total_trades,
            out_of_sample_winning_trades=wf.out_of_sample.winning_trades,
            out_of_sample_losing_trades=wf.out_of_sample.losing_trades,
            return_degradation_pct=q(wf.return_degradation_pct) or Decimal("0"),
            overfitting_warning=wf.overfitting_warning,
            overfitting_threshold_pct=q(wf.overfitting_threshold_pct) or Decimal("0"),
        )

    def _resolve_backtest_options(
        self,
        options: BacktestRunOptions | None,
        *,
        defaults: OperatorRuntimeConfig,
    ) -> BacktestRunOptions:
        active = options or BacktestRunOptions()
        strategy_name = active.strategy_name.strip().lower()
        exchange = (active.exchange or defaults.exchange).strip()
        symbol = (active.symbol or defaults.symbol).strip()
        timeframe = (active.timeframe or defaults.timeframe).strip()
        starting_equity = active.starting_equity or Decimal(
            str(self._settings.paper_account_equity)
        )
        if not exchange or not symbol or not timeframe:
            raise ValueError("exchange, symbol, and timeframe are required for backtest")
        if starting_equity <= Decimal("0"):
            raise ValueError("starting equity must be positive")
        if strategy_name == BACKTEST_STRATEGY_EMA_CROSSOVER:
            fast_period = active.fast_period or defaults.fast_period
            slow_period = active.slow_period or defaults.slow_period
            if fast_period <= 0 or slow_period <= 0:
                raise ValueError("backtest periods must be positive")
            if fast_period >= slow_period:
                raise ValueError("fast period must be smaller than slow period")
            return BacktestRunOptions(
                strategy_name=strategy_name,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                fast_period=fast_period,
                slow_period=slow_period,
                starting_equity=starting_equity,
                slippage_pct=active.slippage_pct,
                fee_pct=active.fee_pct,
                walk_forward_split_ratio=active.walk_forward_split_ratio,
                rsi_period=active.rsi_period,
                rsi_overbought=active.rsi_overbought,
                rsi_oversold=active.rsi_oversold,
                volume_ma_period=active.volume_ma_period,
                multi_tf_timeframe=active.multi_tf_timeframe,
                multi_tf_period=active.multi_tf_period,
                trading_mode=active.trading_mode,
                leverage=active.leverage,
                margin_mode=active.margin_mode,
            )
        if strategy_name == BACKTEST_STRATEGY_RULE_BUILDER:
            rules = active.rules or self._default_rule_builder_config(defaults)
            rules.validate()
            return BacktestRunOptions(
                strategy_name=strategy_name,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                starting_equity=starting_equity,
                slippage_pct=active.slippage_pct,
                fee_pct=active.fee_pct,
                walk_forward_split_ratio=active.walk_forward_split_ratio,
                rules=rules,
                multi_tf_timeframe=active.multi_tf_timeframe,
                multi_tf_period=active.multi_tf_period,
                trading_mode=active.trading_mode,
                leverage=active.leverage,
                margin_mode=active.margin_mode,
            )
        # New strategies: resolve with their own param fields
        base_opts = BacktestRunOptions(
            strategy_name=strategy_name,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            starting_equity=starting_equity,
            slippage_pct=active.slippage_pct,
            fee_pct=active.fee_pct,
            walk_forward_split_ratio=active.walk_forward_split_ratio,
            # shared indicator params
            rsi_period=active.rsi_period,
            rsi_overbought=active.rsi_overbought,
            rsi_oversold=active.rsi_oversold,
            # MACD
            fast_period=active.fast_period,
            slow_period=active.slow_period,
            macd_signal_period=active.macd_signal_period,
            # Bollinger
            bb_period=active.bb_period,
            bb_std_dev=active.bb_std_dev,
            # Breakout
            breakout_period=active.breakout_period,
            atr_period=active.atr_period,
            atr_breakout_multiplier=active.atr_breakout_multiplier,
            atr_stop_multiplier=active.atr_stop_multiplier,
            # ADX regime filter
            adx_period=active.adx_period,
            adx_threshold=active.adx_threshold,
            # Multi-timeframe confirmation
            multi_tf_timeframe=active.multi_tf_timeframe,
            multi_tf_period=active.multi_tf_period,
            trading_mode=active.trading_mode,
            leverage=active.leverage,
            margin_mode=active.margin_mode,
            # ML model params
            xgb_model_path=active.xgb_model_path,
            xgb_buy_threshold=active.xgb_buy_threshold,
            xgb_sell_threshold=active.xgb_sell_threshold,
            model_type=active.model_type,
            oos_only=active.oos_only,
        )
        if strategy_name in _ALL_BACKTEST_STRATEGIES:
            return base_opts
        raise ValueError(f"unsupported backtest strategy: {active.strategy_name}")

    def _preview_backtest_options(
        self,
        options: BacktestRunOptions | None,
        *,
        defaults: OperatorRuntimeConfig,
    ) -> BacktestRunOptions:
        active = options or BacktestRunOptions()
        strategy_name = (active.strategy_name or BACKTEST_STRATEGY_EMA_CROSSOVER).strip().lower()
        if strategy_name == BACKTEST_STRATEGY_RULE_BUILDER:
            return BacktestRunOptions(
                strategy_name=strategy_name,
                exchange=(active.exchange or defaults.exchange).strip(),
                symbol=(active.symbol or defaults.symbol).strip(),
                timeframe=(active.timeframe or defaults.timeframe).strip(),
                starting_equity=Decimal(
                    str(active.starting_equity or self._settings.paper_account_equity)
                ),
                rules=active.rules or self._default_rule_builder_config(defaults),
            )
        return BacktestRunOptions(
            strategy_name=strategy_name,
            exchange=(active.exchange or defaults.exchange).strip(),
            symbol=(active.symbol or defaults.symbol).strip(),
            timeframe=(active.timeframe or defaults.timeframe).strip(),
            fast_period=int(active.fast_period or defaults.fast_period),
            slow_period=int(active.slow_period or defaults.slow_period),
            starting_equity=Decimal(
                str(active.starting_equity or self._settings.paper_account_equity)
            ),
        )

    @staticmethod
    def _build_backtest_strategy(options: BacktestRunOptions) -> Strategy:  # noqa: PLR0911
        sname = options.strategy_name
        if sname == BACKTEST_STRATEGY_RULE_BUILDER:
            if options.rules is None:
                raise ValueError("rule builder strategy requires rules")
            rules = _fill_ema_periods(options.rules, options.fast_period, options.slow_period)
            return RuleBuilderStrategy(rules)
        if sname == BACKTEST_STRATEGY_MACD_CROSSOVER:
            return MacdCrossoverStrategy(
                fast_period=options.fast_period or 12,
                slow_period=options.slow_period or 26,
                signal_period=options.macd_signal_period or 9,
            )
        if sname == BACKTEST_STRATEGY_MEAN_REVERSION_BOLLINGER:
            return MeanReversionBollingerStrategy(
                bb_period=options.bb_period or 20,
                bb_std_dev=options.bb_std_dev or Decimal("2"),
                rsi_period=options.rsi_period or 14,
                rsi_oversold=options.rsi_oversold or Decimal("35"),
                rsi_overbought=options.rsi_overbought or Decimal("65"),
            )
        if sname == BACKTEST_STRATEGY_RSI_MOMENTUM:
            return RsiMomentumStrategy(
                rsi_period=options.rsi_period or 14,
            )
        if sname == BACKTEST_STRATEGY_BREAKOUT_ATR:
            return BreakoutAtrStrategy(
                breakout_period=options.breakout_period or 20,
                atr_period=options.atr_period or 14,
                atr_breakout_multiplier=options.atr_breakout_multiplier or Decimal("0.5"),
                atr_stop_multiplier=options.atr_stop_multiplier or Decimal("2.0"),
            )
        if sname in (BACKTEST_STRATEGY_XGBOOST_SIGNAL, BACKTEST_STRATEGY_ML_SIGNAL):
            mt = options.model_type or "xgboost"
            model_path = options.xgb_model_path or default_model_path(
                symbol=options.symbol or "BTC/USDT",
                timeframe=options.timeframe or "1h",
                model_type=mt,
            )
            loaded = load_model(model_path)
            return MLSignalStrategy(
                model=loaded.model,
                feature_names=loaded.metadata.feature_names,
                buy_threshold=options.xgb_buy_threshold
                or Decimal(str(loaded.metadata.buy_threshold)),
                sell_threshold=options.xgb_sell_threshold
                or Decimal(str(loaded.metadata.sell_threshold)),
            )
        if sname != BACKTEST_STRATEGY_EMA_CROSSOVER:
            raise ValueError(f"unsupported backtest strategy: {sname}")
        return EmaCrossoverStrategy(
            fast_period=options.fast_period or 20,
            slow_period=options.slow_period or 50,
            rsi_period=options.rsi_period,
            rsi_overbought=options.rsi_overbought or Decimal("70"),
            rsi_oversold=options.rsi_oversold or Decimal("30"),
            volume_ma_period=options.volume_ma_period,
            adx_period=options.adx_period,
            adx_threshold=options.adx_threshold or Decimal("25"),
        )

    @staticmethod
    def _required_candles_for_options(options: BacktestRunOptions) -> int:
        return required_candles_for_backtest_options(options)

    @staticmethod
    def _default_rule_builder_config(
        defaults: OperatorRuntimeConfig,
    ) -> RuleBuilderStrategyConfig:
        return RuleBuilderStrategyConfig(
            shared_filters=StrategyRuleGroup(logic="all", conditions=()),
            buy_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bullish",
                        fast_period=defaults.fast_period,
                        slow_period=defaults.slow_period,
                    ),
                ),
            ),
            sell_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bearish",
                        fast_period=defaults.fast_period,
                        slow_period=defaults.slow_period,
                    ),
                ),
            ),
        )

    def _build_risk_service(self) -> RiskService:
        return RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal(str(self._settings.risk_per_trade_pct)),
                max_open_positions=self._settings.max_open_positions,
                max_daily_loss_pct=Decimal(str(self._settings.max_daily_loss_pct)),
                paper_trading_only=not self._settings.live_trading_enabled,
                volatility_sizing_enabled=self._settings.volatility_sizing_enabled,
            )
        )

    def _resolve_leverage(
        self,
        *,
        requested_leverage: int | None,
        symbol: str,
        trading_mode: str,
    ) -> int:
        if trading_mode.upper() != "FUTURES":
            return 1
        if requested_leverage is not None:
            if not 1 <= requested_leverage <= 125:
                raise ValueError("leverage must be between 1 and 125")
            return requested_leverage
        # None = auto: fetch from exchange
        try:
            client = build_live_order_exchange_client(self._settings, trading_mode="FUTURES")
            risk = client.fetch_position_risk(symbol=symbol)
            if isinstance(risk, list):
                for item in risk:
                    if isinstance(item, dict) and "leverage" in item:
                        return int(item["leverage"])
            elif isinstance(risk, dict) and "leverage" in risk:
                return int(risk["leverage"])
        except Exception:
            pass
        return 1

    def _get_effective_operator_config(self) -> OperatorRuntimeConfig:
        with self._session_factory() as session:
            return OperatorRuntimeConfigService(
                session,
                self._settings,
            ).get_effective_config()

    @classmethod
    def _quantize_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return value.quantize(cls._decimal_precision)
