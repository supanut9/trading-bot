from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountBalanceResponse(BaseModel):
    asset: str
    free: Decimal
    locked: Decimal


class RecoverySummaryResponse(BaseModel):
    posture: str
    dominant_recovery_state: str
    next_action: str
    summary: str
    unresolved_order_count: int
    awaiting_exchange_count: int
    partial_fill_in_flight_count: int
    stale_open_order_count: int
    stale_partial_fill_count: int
    manual_review_required_count: int
    requires_operator_review_count: int
    stale_order_count: int

    model_config = ConfigDict(from_attributes=True)


class StatusResponse(BaseModel):
    app: str
    environment: str
    execution_mode: str
    paper_trading: bool
    live_trading_enabled: bool
    live_trading_halted: bool
    live_safety_status: str
    runtime_promotion_stage: str
    runtime_promotion_blockers: list[str] = Field(default_factory=list)
    live_readiness_status: str | None = None
    live_readiness_blocking_reasons: list[str] = Field(default_factory=list)
    live_max_order_notional: Decimal | None = None
    live_max_position_quantity: Decimal | None = None
    live_max_total_exposure_notional: Decimal | None = None
    live_max_symbol_exposure_notional: Decimal | None = None
    live_max_symbol_concentration_pct: Decimal | None = None
    live_max_concurrent_positions: int | None = None
    exchange: str
    strategy_name: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    operator_config_source: str
    trading_mode: str | None = None
    database_url: str
    database_status: str
    latest_price_status: str
    latest_price: Decimal | None = None
    latest_performance_review_decision: "PerformanceReviewDecisionResponse | None" = None
    live_recovery_summary: RecoverySummaryResponse | None = None
    account_balance_status: str
    account_balances: list[AccountBalanceResponse] = Field(default_factory=list)


class PositionResponse(BaseModel):
    exchange: str
    symbol: str
    side: str
    mode: str
    quantity: Decimal
    average_entry_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal

    model_config = ConfigDict(from_attributes=True)


class TradeResponse(BaseModel):
    id: int
    order_id: int | None
    exchange: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee_amount: Decimal | None
    fee_asset: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PerformanceSummaryResponse(BaseModel):
    mode: str
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None = None
    average_win: Decimal | None = None
    average_loss: Decimal | None = None
    profit_factor: Decimal | None = None
    expectancy: Decimal | None = None
    max_drawdown: Decimal
    open_position_count: int

    model_config = ConfigDict(from_attributes=True)


class PerformanceEquityCurvePointResponse(BaseModel):
    mode: str
    recorded_at: datetime
    net_pnl: Decimal
    drawdown: Decimal

    model_config = ConfigDict(from_attributes=True)


class PerformanceDailyRowResponse(BaseModel):
    mode: str
    trade_date: date
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    realized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal

    model_config = ConfigDict(from_attributes=True)


class PerformanceAnalyticsResponse(BaseModel):
    summaries: list[PerformanceSummaryResponse]
    equity_curve: list[PerformanceEquityCurvePointResponse]
    daily_rows: list[PerformanceDailyRowResponse]

    model_config = ConfigDict(from_attributes=True)


class CandleWriteRequest(BaseModel):
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

    @field_validator("open_time", "close_time")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class CandleBatchIngestionRequest(BaseModel):
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    candles: list[CandleWriteRequest] = Field(min_length=1)


class CandleBatchIngestionResponse(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    stored_count: int
    latest_open_time: datetime


class MarketDataCoverageResponse(BaseModel):
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    first_open_time: datetime | None = None
    latest_open_time: datetime | None = None
    latest_close_time: datetime | None = None
    required_candles: int
    additional_candles_needed: int
    satisfies_required_candles: bool
    freshness_status: str
    readiness_status: str
    detail: str

    model_config = ConfigDict(from_attributes=True)

    @field_validator("first_open_time", "latest_open_time", "latest_close_time")
    @classmethod
    def normalize_optional_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class DemoScenarioLoadResponse(BaseModel):
    scenario: str
    detail: str
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    stored_count: int
    latest_open_time: datetime
    expected_signal_action: str | None = None


class WorkerControlResponse(BaseModel):
    status: str
    detail: str
    risk_reason: str | None = None
    signal_action: str | None = None
    client_order_id: str | None = None
    order_id: int | None = None
    trade_id: int | None = None
    position_quantity: Decimal | None = None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class WalkForwardResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class BacktestControlResponse(BaseModel):
    status: str
    detail: str
    notified: bool
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    trading_mode: str = "SPOT"
    fast_period: int | None = None
    slow_period: int | None = None
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
    spread_pct: Decimal | None = None
    signal_latency_bars: int = 0
    assumption_summary: str = ""
    allowed_weekdays_utc: list[int] = Field(default_factory=list)
    allowed_hours_utc: list[int] = Field(default_factory=list)
    max_volume_fill_pct: Decimal | None = None
    allow_partial_fills: bool = False
    rsi_period: int | None = None
    rsi_overbought: Decimal | None = None
    rsi_oversold: Decimal | None = None
    volume_ma_period: int | None = None
    macd_signal_period: int | None = None
    bb_period: int | None = None
    bb_std_dev: Decimal | None = None
    breakout_period: int | None = None
    atr_period: int | None = None
    atr_breakout_multiplier: Decimal | None = None
    atr_stop_multiplier: Decimal | None = None
    adx_period: int | None = None
    adx_threshold: Decimal | None = None
    walk_forward: WalkForwardResponse | None = None
    rules: "StrategyRuleBuilderRequest | None" = None
    leverage: int | None = None
    margin_mode: str = "ISOLATED"
    liquidation_count: int = 0
    stop_loss_count: int = 0
    executions: list["BacktestExecutionResponse"] = Field(default_factory=list)
    candles: list["BacktestCandleResponse"] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BacktestCandleResponse(BaseModel):
    open_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal

    model_config = ConfigDict(from_attributes=True)


class BacktestExecutionResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class BacktestRunResponse(BaseModel):
    id: int
    created_at: datetime
    source: str
    status: str
    detail: str
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int | None = None
    slow_period: int | None = None
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
    rsi_period: int | None = None
    rsi_overbought: Decimal | None = None
    rsi_oversold: Decimal | None = None
    volume_ma_period: int | None = None
    macd_signal_period: int | None = None
    bb_period: int | None = None
    bb_std_dev: Decimal | None = None
    breakout_period: int | None = None
    atr_period: int | None = None
    atr_breakout_multiplier: Decimal | None = None
    atr_stop_multiplier: Decimal | None = None
    adx_period: int | None = None
    adx_threshold: Decimal | None = None
    leverage: int | None = None
    margin_mode: str | None = None
    liquidation_count: int | None = None
    slippage_pct: Decimal | None = None
    fee_pct: Decimal | None = None
    spread_pct: Decimal | None = None
    signal_latency_bars: int = 0
    assumption_summary: str = ""
    allowed_weekdays_utc: list[int] = Field(default_factory=list)
    allowed_hours_utc: list[int] = Field(default_factory=list)
    max_volume_fill_pct: Decimal | None = None
    allow_partial_fills: bool = False
    rules: "StrategyRuleBuilderRequest | None" = None


class BacktestRunHistoryResponse(BaseModel):
    run_count: int
    runs: list[BacktestRunResponse]


class BacktestControlRequest(BaseModel):
    strategy_name: str = "ema_crossover"
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    fast_period: int | None = None
    slow_period: int | None = None
    starting_equity: Decimal | None = None
    slippage_pct: Decimal | None = None
    fee_pct: Decimal | None = None
    spread_pct: Decimal | None = None
    signal_latency_bars: int | None = None
    allowed_weekdays_utc: list[int] | None = None
    allowed_hours_utc: list[int] | None = None
    max_volume_fill_pct: Decimal | None = None
    allow_partial_fills: bool = False
    walk_forward_split_ratio: Decimal | None = None
    rules: "StrategyRuleBuilderRequest | None" = None
    rsi_period: int | None = None
    rsi_overbought: Decimal | None = None
    rsi_oversold: Decimal | None = None
    volume_ma_period: int | None = None
    macd_signal_period: int | None = None
    bb_period: int | None = None
    bb_std_dev: Decimal | None = None
    breakout_period: int | None = None
    atr_period: int | None = None
    atr_breakout_multiplier: Decimal | None = None
    atr_stop_multiplier: Decimal | None = None
    adx_period: int | None = None
    adx_threshold: Decimal | None = None
    multi_tf_timeframe: str | None = None
    multi_tf_period: int | None = None
    trading_mode: str = "SPOT"
    leverage: int | None = None  # None = auto-fetch; ignored for SPOT
    margin_mode: str = "ISOLATED"  # "ISOLATED" or "CROSS"
    xgb_model_path: str | None = None
    xgb_buy_threshold: float | None = None
    xgb_sell_threshold: float | None = None
    oos_only: bool = False
    model_type: str | None = None


class TrainModelRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    exchange: str = "binance"
    model_type: str = "xgboost"
    label_type: str = "forward_return"
    label_horizon: int = Field(default=5, ge=1, le=50)
    label_threshold: float = Field(default=0.003, ge=0.0, le=0.1)
    feature_names: list[str] | None = None
    candle_limit: int = Field(default=10000, ge=100, le=50000)
    n_estimators: int = Field(default=200, ge=10, le=2000)
    max_depth: int = Field(default=4, ge=1, le=20)
    learning_rate: float = Field(default=0.1, gt=0.0, le=1.0)
    split_ratio: float = Field(default=0.7, gt=0.0, lt=1.0)
    buy_threshold: float = Field(default=0.60, gt=0.5, lt=1.0)
    sell_threshold: float = Field(default=0.40, gt=0.0, lt=0.5)


class FeatureImportanceSchema(BaseModel):
    feature: str
    importance: float


class TrainModelResponse(BaseModel):
    status: str
    symbol: str
    timeframe: str
    model_type: str = "xgboost"
    model_path: str
    label_type: str = "next_candle"
    label_horizon: int = 1
    label_threshold: float = 0.0
    feature_names: list[str] = []
    sample_count: int
    train_count: int
    test_count: int
    oos_start_index: int = 0
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    roc_auc: float | None = None
    feature_importances: list[FeatureImportanceSchema] = []
    detail: str = ""


class ModelStatusItem(BaseModel):
    symbol: str
    timeframe: str
    model_type: str
    model_path: str
    exists: bool
    file_size_kb: float | None = None
    # sidecar metadata (None if no .meta.json)
    label_type: str | None = None
    label_horizon: int | None = None
    label_threshold: float | None = None
    feature_names: list[str] | None = None
    buy_threshold: float | None = None
    sell_threshold: float | None = None
    sample_count: int | None = None
    train_count: int | None = None
    test_count: int | None = None
    oos_start_index: int | None = None
    accuracy: float | None = None
    roc_auc: float | None = None


class ModelStatusResponse(BaseModel):
    models: list[ModelStatusItem]


class StrategyRuleConditionRequest(BaseModel):
    indicator: Literal["ema_cross", "price_vs_ema", "rsi_threshold"]
    operator: Literal["bullish", "bearish", "above", "below"]
    fast_period: int | None = None
    slow_period: int | None = None
    period: int | None = None
    threshold: Decimal | None = None


class StrategyRuleGroupRequest(BaseModel):
    logic: Literal["all", "any"] = "all"
    conditions: list[StrategyRuleConditionRequest] = Field(default_factory=list)


class StrategyRuleBuilderRequest(BaseModel):
    shared_filters: StrategyRuleGroupRequest = Field(default_factory=StrategyRuleGroupRequest)
    buy_rules: StrategyRuleGroupRequest = Field(default_factory=StrategyRuleGroupRequest)
    sell_rules: StrategyRuleGroupRequest = Field(default_factory=StrategyRuleGroupRequest)


class OperatorConfigResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class OperatorConfigRequest(BaseModel):
    strategy_name: str = "ema_crossover"
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    trading_mode: str = "SPOT"


class MarketSyncControlResponse(BaseModel):
    status: str
    detail: str
    symbol: str
    timeframe: str
    limit: int
    backfill: bool = False
    fetched_count: int
    stored_count: int
    latest_open_time: datetime | None = None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class MarketSyncControlRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    limit: int | None = Field(default=None, ge=1, le=50000)
    backfill: bool = False


class LiveReconcileControlResponse(BaseModel):
    status: str
    detail: str
    reconciled_count: int
    filled_count: int
    review_required_count: int
    recovery_summary: str = "-"
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class LiveHaltControlRequest(BaseModel):
    halted: bool


class LiveHaltControlResponse(BaseModel):
    status: str
    detail: str
    live_trading_halted: bool
    changed: bool
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class LiveCancelControlRequest(BaseModel):
    order_id: int | None = None
    client_order_id: str | None = None
    exchange_order_id: str | None = None


class LiveCancelControlResponse(BaseModel):
    status: str
    detail: str
    order_id: int | None
    client_order_id: str | None
    exchange_order_id: str | None
    order_status: str | None
    notified: bool

    model_config = ConfigDict(from_attributes=True)


class RecoveryReportFiltersResponse(BaseModel):
    order_status: str | None = None
    requires_review: bool | None = None
    event_type: str | None = None
    search: str | None = None


class StaleLiveOrderResponse(BaseModel):
    id: int
    symbol: str
    side: str
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    updated_at: datetime
    age_minutes: int

    model_config = ConfigDict(from_attributes=True)


class RecoveryOrderResponse(BaseModel):
    id: int
    symbol: str
    side: str
    status: str
    client_order_id: str | None
    exchange_order_id: str | None
    quantity: Decimal
    price: Decimal | None
    updated_at: datetime
    requires_operator_review: bool
    recovery_state: str
    next_action: str


class RecoveryEventResponse(BaseModel):
    created_at: datetime
    event_type: str
    source: str
    status: str
    detail: str
    context: str

    model_config = ConfigDict(from_attributes=True)


class RecoveryDashboardResponse(BaseModel):
    live_trading_enabled: bool
    live_trading_halted: bool
    live_safety_status: str
    stale_threshold_minutes: int
    summary: RecoverySummaryResponse
    stale_live_orders: list[StaleLiveOrderResponse]
    unresolved_orders: list[RecoveryOrderResponse]
    recovery_events: list[RecoveryEventResponse]
    unresolved_live_orders: int
    recovery_event_count: int
    latest_recovery_event_at: str | None = None
    latest_recovery_event_type: str | None = None
    latest_recovery_event_status: str | None = None
    latest_recovery_event_context: str | None = None
    filters: RecoveryReportFiltersResponse


class NotificationReportFiltersResponse(BaseModel):
    status: str | None = None
    channel: str | None = None
    related_event_type: str | None = None


class AuditEventResponse(BaseModel):
    id: int
    created_at: datetime
    event_type: str
    source: str
    status: str
    detail: str
    exchange: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    channel: str | None = None
    related_event_type: str | None = None
    correlation_id: str | None = None
    payload_json: str | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationDashboardResponse(BaseModel):
    delivery_count: int
    failed_count: int
    latest_delivery_at: str | None = None
    latest_delivery_status: str | None = None
    latest_delivery_channel: str | None = None
    latest_related_event_type: str | None = None
    filters: NotificationReportFiltersResponse
    events: list[AuditEventResponse]


class AuditReportFiltersResponse(BaseModel):
    event_type: str | None = None
    status: str | None = None
    source: str | None = None
    search: str | None = None


class AuditDashboardResponse(BaseModel):
    event_count: int
    filters: AuditReportFiltersResponse
    events: list[AuditEventResponse]


class SymbolRulesControlResponse(BaseModel):
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

    model_config = ConfigDict(from_attributes=True)


class LiveReadinessCheckResponse(BaseModel):
    name: str
    passed: bool
    severity: str
    detail: str

    model_config = ConfigDict(from_attributes=True)


class LiveReadinessControlResponse(BaseModel):
    status: str
    detail: str
    ready: bool
    checks: list[LiveReadinessCheckResponse] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RuntimePromotionControlRequest(BaseModel):
    stage: Literal["paper", "shadow", "qualified", "canary", "live"]


class RuntimePromotionControlResponse(BaseModel):
    status: str
    detail: str
    stage: str
    changed: bool
    blockers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PerformanceReviewDecisionRequest(BaseModel):
    operator_decision: Literal["keep_running", "reduce_risk", "pause_and_rework", "halt"]
    rationale: str = Field(min_length=1)
    review_period_days: int = Field(default=30, ge=1, le=365)


class PerformanceReviewDecisionResponse(BaseModel):
    recommendation: str
    operator_decision: str
    rationale: str
    review_period_days: int
    root_cause_driver: str
    root_cause_regime: str
    review_generated_at: datetime
    decided_at: datetime
    decided_by: str
    age_days: int
    stale: bool

    model_config = ConfigDict(from_attributes=True)


class ShadowTradeResponse(BaseModel):
    id: int
    side: str
    entry_price: Decimal
    simulated_fill_price: Decimal
    simulated_exit_fill_price: Decimal | None
    quantity: Decimal
    entry_fee: Decimal
    exit_fee: Decimal | None
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    status: str
    client_order_id: str | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ShadowBlockedSignalResponse(BaseModel):
    id: int
    signal_action: str
    signal_reason: str | None
    block_reason: str
    block_source: str
    price: Decimal | None
    client_order_id: str | None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ShadowQualityReportResponse(BaseModel):
    exchange: str
    symbol: str
    total_shadow_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal
    total_fees_paid: Decimal
    blocked_signal_count: int
    oos_win_rate_pct: Decimal | None
    oos_max_drawdown_pct: Decimal | None
    oos_total_return_pct: Decimal | None
    recent_blocked_signals: list[ShadowBlockedSignalResponse]
    recent_trades: list[ShadowTradeResponse]

    model_config = ConfigDict(from_attributes=True)


class QualificationGateResponse(BaseModel):
    name: str
    passed: bool
    reason: str
    evidence: str | None = None


class QualificationReportResponse(BaseModel):
    exchange: str
    symbol: str
    all_passed: bool
    gates: list[QualificationGateResponse]


class LiveModeMetricsResponse(BaseModel):
    trade_count: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal
    total_fees_paid: Decimal
    avg_slippage_pct: Decimal | None
    slippage_sample_count: int

    model_config = ConfigDict(from_attributes=True)


class ShadowModeMetricsResponse(BaseModel):
    trade_count: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal

    model_config = ConfigDict(from_attributes=True)


class OOSBaselineResponse(BaseModel):
    backtest_run_id: int
    run_date: datetime
    oos_return_pct: Decimal
    oos_drawdown_pct: Decimal
    oos_total_trades: int
    in_sample_return_pct: Decimal
    modeled_slippage_pct: Decimal | None
    overfitting_warning: bool

    model_config = ConfigDict(from_attributes=True)


class StrategyHealthIndicatorsResponse(BaseModel):
    slippage_vs_model_pct: Decimal | None
    shadow_vs_oos_expectancy_drift: Decimal | None
    live_vs_shadow_win_rate_drift: Decimal | None
    consecutive_losses: int
    signal_frequency_per_week: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class RootCauseAnalysisResponse(BaseModel):
    primary_driver: str
    regime_assessment: str
    summary: str
    operator_focus: list[str]

    model_config = ConfigDict(from_attributes=True)


class LivePerformanceReviewResponse(BaseModel):
    live_metrics: LiveModeMetricsResponse | None
    shadow_metrics: ShadowModeMetricsResponse
    oos_baseline: OOSBaselineResponse | None
    health_indicators: StrategyHealthIndicatorsResponse
    root_cause: RootCauseAnalysisResponse
    latest_decision: PerformanceReviewDecisionResponse | None = None
    recommendation: str
    recommendation_reasons: list[str]
    review_period_days: int
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IterationStepResponse(BaseModel):
    name: str
    status: str
    description: str
    evidence: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StrategyIterationPlanResponse(BaseModel):
    recommendation: str
    recommendation_reasons: list[str]
    steps: list[IterationStepResponse]
    all_steps_clear: bool
    generated_at: datetime
    exchange: str
    symbol: str
    review_period_days: int

    model_config = ConfigDict(from_attributes=True)
