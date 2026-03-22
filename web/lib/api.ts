export type StatusResponse = {
  app: string;
  environment: string;
  execution_mode: string;
  paper_trading: boolean;
  live_trading_enabled: boolean;
  live_trading_halted: boolean;
  live_safety_status: string;
  live_max_order_notional: string | null;
  live_max_position_quantity: string | null;
  exchange: string;
  strategy_name: string;
  symbol: string;
  timeframe: string;
  fast_period: number;
  slow_period: number;
  trading_mode: string;
  operator_config_source: string;
  database_url: string;
  database_status: string;
  latest_price_status: string;
  latest_price: string | null;
  account_balance_status: string;
  account_balances: Array<{
    asset: string;
    free: string;
    locked: string;
  }>;
};

export type PerformanceAnalyticsResponse = {
  summaries: Array<{
    mode: string;
    total_realized_pnl: string;
    total_unrealized_pnl: string;
    total_fees: string;
    net_pnl: string;
    trade_count: number;
    closed_trade_count: number;
    winning_trades: number;
    losing_trades: number;
    win_rate_pct: string | null;
    average_win: string | null;
    average_loss: string | null;
    profit_factor: string | null;
    expectancy: string | null;
    max_drawdown: string;
    open_position_count: number;
  }>;
  equity_curve: Array<{
    mode: string;
    recorded_at: string;
    net_pnl: string;
    drawdown: string;
  }>;
  daily_rows: Array<{
    mode: string;
    trade_date: string;
    trade_count: number;
    closed_trade_count: number;
    winning_trades: number;
    losing_trades: number;
    realized_pnl: string;
    fees: string;
    net_pnl: string;
  }>;
};

export type PositionResponse = {
  exchange: string;
  symbol: string;
  side: string;
  mode: string;
  quantity: string;
  average_entry_price: string | null;
  realized_pnl: string;
  unrealized_pnl: string;
};

export type TradeResponse = {
  id: number;
  order_id: number | null;
  exchange: string;
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  fee_amount: string | null;
  fee_asset: string | null;
  created_at: string;
};

export type OperatorConfigResponse = {
  status: string;
  detail: string;
  strategy_name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  fast_period: number;
  slow_period: number;
  trading_mode: string;
  source: string;
  changed: boolean;
  notified: boolean;
};

export type MarketDataCoverageResponse = {
  exchange: string;
  symbol: string;
  timeframe: string;
  candle_count: number;
  first_open_time: string | null;
  latest_open_time: string | null;
  latest_close_time: string | null;
  required_candles: number;
  additional_candles_needed: number;
  satisfies_required_candles: boolean;
  freshness_status: string;
  readiness_status: string;
  detail: string;
};

export type BacktestExecutionResponse = {
  action: string;
  price: string;
  fill_price: string;
  quantity: string;
  realized_pnl: string;
  reason: string;
  candle_open_time: string;
  liquidation_price: string | null;
  was_liquidated: boolean;
};

export type BacktestCandleResponse = {
  open_time: string;
  open_price: string;
  high_price: string;
  low_price: string;
  close_price: string;
  volume: string;
};

export type StrategyRuleConditionRequest = {
  indicator: "ema_cross" | "price_vs_ema" | "rsi_threshold";
  operator: "bullish" | "bearish" | "above" | "below";
  fast_period?: number;
  slow_period?: number;
  period?: number;
  threshold?: string;
};

export type StrategyRuleGroupRequest = {
  logic: "all" | "any";
  conditions: StrategyRuleConditionRequest[];
};

export type StrategyRuleBuilderRequest = {
  shared_filters: StrategyRuleGroupRequest;
  buy_rules: StrategyRuleGroupRequest;
  sell_rules: StrategyRuleGroupRequest;
};

export type BacktestControlRequest = {
  strategy_name?: string;
  exchange?: string;
  symbol?: string;
  timeframe?: string;
  fast_period?: number;
  slow_period?: number;
  starting_equity?: number;
  rules?: StrategyRuleBuilderRequest;
  rsi_period?: number;
  rsi_overbought?: string;
  rsi_oversold?: string;
  volume_ma_period?: number;
  macd_signal_period?: number;
  bb_period?: number;
  bb_std_dev?: string;
  breakout_period?: number;
  atr_period?: number;
  atr_breakout_multiplier?: string;
  atr_stop_multiplier?: string;
  adx_period?: number;
  adx_threshold?: string;
  xgb_buy_threshold?: number;
  xgb_sell_threshold?: number;
  model_type?: string;
  oos_only?: boolean;
  trading_mode?: string;
  leverage?: number | null;
  margin_mode?: string;
};

export type BacktestControlResponse = {
  status: string;
  detail: string;
  notified: boolean;
  strategy_name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  trading_mode: string;
  fast_period: number | null;
  slow_period: number | null;
  starting_equity_input: string;
  candle_count: number;
  required_candles: number;
  starting_equity: string | null;
  ending_equity: string | null;
  realized_pnl: string | null;
  total_return_pct: string | null;
  max_drawdown_pct: string | null;
  total_trades: number | null;
  winning_trades: number | null;
  losing_trades: number | null;
  rules: StrategyRuleBuilderRequest | null;
  bb_period: number | null;
  bb_std_dev: string | null;
  breakout_period: number | null;
  atr_period: number | null;
  atr_breakout_multiplier: string | null;
  atr_stop_multiplier: string | null;
  adx_period: number | null;
  adx_threshold: string | null;
  leverage: number | null;
  margin_mode: string;
  liquidation_count: number;
  stop_loss_count: number;
  executions: BacktestExecutionResponse[];
  candles: BacktestCandleResponse[];
};

export type BacktestRunResponse = {
  id: number;
  created_at: string;
  source: string;
  status: string;
  detail: string;
  strategy_name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  trading_mode: string;
  fast_period: number | null;
  slow_period: number | null;
  starting_equity_input: string;
  candle_count: number;
  required_candles: number;
  starting_equity: string | null;
  ending_equity: string | null;
  realized_pnl: string | null;
  total_return_pct: string | null;
  max_drawdown_pct: string | null;
  total_trades: number | null;
  winning_trades: number | null;
  losing_trades: number | null;
  leverage: number | null;
  margin_mode: string | null;
  liquidation_count: number | null;
  rules: StrategyRuleBuilderRequest | null;
};

export type BacktestRunHistoryResponse = {
  run_count: number;
  runs: BacktestRunResponse[];
};

export type OperatorConfigRequest = {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  fast_period: number;
  slow_period: number;
  trading_mode: string;
};

export type MarketSyncControlRequest = {
  symbol?: string;
  timeframe?: string;
  limit?: number;
  backfill?: boolean;
};

export type MarketSyncControlResponse = {
  status: string;
  detail: string;
  symbol: string;
  timeframe: string;
  limit: number;
  backfill: boolean;
  fetched_count: number;
  stored_count: number;
  latest_open_time: string | null;
  notified: boolean;
};

export type WorkerControlResponse = {
  status: string;
  detail: string;
  signal_action: string | null;
  client_order_id: string | null;
  order_id: number | null;
  trade_id: number | null;
  position_quantity: string | null;
  notified: boolean;
};

export type LiveReconcileControlResponse = {
  status: string;
  detail: string;
  reconciled_count: number;
  filled_count: number;
  review_required_count: number;
  notified: boolean;
};

export type LiveHaltControlRequest = {
  halted: boolean;
};

export type LiveHaltControlResponse = {
  status: string;
  detail: string;
  live_trading_halted: boolean;
  changed: boolean;
  notified: boolean;
};

export type LiveCancelControlRequest = {
  order_id?: number;
  client_order_id?: string;
  exchange_order_id?: string;
};

export type LiveCancelControlResponse = {
  status: string;
  detail: string;
  order_id: number | null;
  client_order_id: string | null;
  exchange_order_id: string | null;
  order_status: string | null;
  notified: boolean;
};

export type QualificationGateResponse = {
  name: string;
  passed: boolean;
  reason: string;
  evidence: Record<string, unknown> | null;
};

export type QualificationReportResponse = {
  exchange: string;
  symbol: string;
  all_passed: boolean;
  gates: QualificationGateResponse[];
};

export type RecoveryReportFilters = {
  order_status: string | null;
  requires_review: boolean | null;
  event_type: string | null;
  search: string | null;
};

export type StaleLiveOrderResponse = {
  id: number;
  symbol: string;
  side: string;
  status: string;
  client_order_id: string | null;
  exchange_order_id: string | null;
  updated_at: string;
  age_minutes: number;
};

export type RecoveryOrderResponse = {
  id: number;
  symbol: string;
  side: string;
  status: string;
  client_order_id: string | null;
  exchange_order_id: string | null;
  quantity: string;
  price: string | null;
  updated_at: string;
  requires_operator_review: boolean;
  next_action: string;
};

export type RecoveryEventResponse = {
  created_at: string;
  event_type: string;
  source: string;
  status: string;
  detail: string;
  context: string;
};

export type RecoveryDashboardResponse = {
  live_trading_enabled: boolean;
  live_trading_halted: boolean;
  live_safety_status: string;
  stale_threshold_minutes: number;
  stale_live_orders: StaleLiveOrderResponse[];
  unresolved_orders: RecoveryOrderResponse[];
  recovery_events: RecoveryEventResponse[];
  unresolved_live_orders: number;
  recovery_event_count: number;
  latest_recovery_event_at: string | null;
  latest_recovery_event_type: string | null;
  latest_recovery_event_status: string | null;
  latest_recovery_event_context: string | null;
  filters: RecoveryReportFilters;
};

export type NotificationReportFilters = {
  status: string | null;
  channel: string | null;
  related_event_type: string | null;
};

export type AuditEventResponse = {
  id: number;
  created_at: string;
  event_type: string;
  source: string;
  status: string;
  detail: string;
  exchange: string | null;
  symbol: string | null;
  timeframe: string | null;
  channel: string | null;
  related_event_type: string | null;
  correlation_id: string | null;
  payload_json: string | null;
};

export type NotificationDashboardResponse = {
  delivery_count: number;
  failed_count: number;
  latest_delivery_at: string | null;
  latest_delivery_status: string | null;
  latest_delivery_channel: string | null;
  latest_related_event_type: string | null;
  filters: NotificationReportFilters;
  events: AuditEventResponse[];
};

export type AuditReportFilters = {
  event_type: string | null;
  status: string | null;
  source: string | null;
  search: string | null;
};

export type AuditDashboardResponse = {
  event_count: number;
  filters: AuditReportFilters;
  events: AuditEventResponse[];
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/status");
}

export function getPerformanceSummary(): Promise<PerformanceAnalyticsResponse> {
  return request<PerformanceAnalyticsResponse>("/performance/summary");
}

export function getRecoveryDashboard(params?: {
  recovery_order_status?: string;
  recovery_requires_review?: boolean;
  recovery_event_type?: string;
  recovery_search?: string;
}): Promise<RecoveryDashboardResponse> {
  const searchParams = new URLSearchParams();
  if (params?.recovery_order_status) {
    searchParams.set("recovery_order_status", params.recovery_order_status);
  }
  if (params?.recovery_requires_review !== undefined) {
    searchParams.set("recovery_requires_review", String(params.recovery_requires_review));
  }
  if (params?.recovery_event_type) {
    searchParams.set("recovery_event_type", params.recovery_event_type);
  }
  if (params?.recovery_search) {
    searchParams.set("recovery_search", params.recovery_search);
  }
  const suffix = searchParams.toString();
  return request<RecoveryDashboardResponse>(`/reports/recovery${suffix ? `?${suffix}` : ""}`);
}

export function getNotificationDashboard(params?: {
  notification_status?: string;
  notification_channel?: string;
  notification_related_event_type?: string;
}): Promise<NotificationDashboardResponse> {
  const searchParams = new URLSearchParams();
  if (params?.notification_status) {
    searchParams.set("notification_status", params.notification_status);
  }
  if (params?.notification_channel) {
    searchParams.set("notification_channel", params.notification_channel);
  }
  if (params?.notification_related_event_type) {
    searchParams.set("notification_related_event_type", params.notification_related_event_type);
  }
  const suffix = searchParams.toString();
  return request<NotificationDashboardResponse>(
    `/reports/notifications${suffix ? `?${suffix}` : ""}`,
  );
}

export function getAuditDashboard(params?: {
  audit_event_type?: string;
  audit_status?: string;
  audit_source?: string;
  audit_search?: string;
}): Promise<AuditDashboardResponse> {
  const searchParams = new URLSearchParams();
  if (params?.audit_event_type) {
    searchParams.set("audit_event_type", params.audit_event_type);
  }
  if (params?.audit_status) {
    searchParams.set("audit_status", params.audit_status);
  }
  if (params?.audit_source) {
    searchParams.set("audit_source", params.audit_source);
  }
  if (params?.audit_search) {
    searchParams.set("audit_search", params.audit_search);
  }
  const suffix = searchParams.toString();
  return request<AuditDashboardResponse>(`/reports/audit${suffix ? `?${suffix}` : ""}`);
}

export function getPositions(): Promise<PositionResponse[]> {
  return request<PositionResponse[]>("/positions");
}

export function getTrades(limit = 8): Promise<TradeResponse[]> {
  return request<TradeResponse[]>(`/trades?limit=${limit}`);
}

export function getOperatorConfig(): Promise<OperatorConfigResponse> {
  return request<OperatorConfigResponse>("/controls/operator-config");
}

export function getBacktestRuns(limit = 12): Promise<BacktestRunHistoryResponse> {
  return request<BacktestRunHistoryResponse>(`/reports/backtest-runs?limit=${limit}`);
}

export function getMarketDataCoverage(params?: {
  strategy_name?: string;
  exchange?: string;
  symbol?: string;
  timeframe?: string;
  fast_period?: number;
  slow_period?: number;
  rules?: StrategyRuleBuilderRequest;
  trading_mode?: string;
}): Promise<MarketDataCoverageResponse> {
  const searchParams = new URLSearchParams();
  if (params?.strategy_name) {
    searchParams.set("strategy_name", params.strategy_name);
  }
  if (params?.exchange) {
    searchParams.set("exchange", params.exchange);
  }
  if (params?.symbol) {
    searchParams.set("symbol", params.symbol);
  }
  if (params?.timeframe) {
    searchParams.set("timeframe", params.timeframe);
  }
  if (params?.fast_period !== undefined) {
    searchParams.set("fast_period", String(params.fast_period));
  }
  if (params?.slow_period !== undefined) {
    searchParams.set("slow_period", String(params.slow_period));
  }
  if (params?.rules) {
    searchParams.set("rules_json", JSON.stringify(params.rules));
  }
  if (params?.trading_mode) {
    searchParams.set("trading_mode", params.trading_mode);
  }
  const suffix = searchParams.toString();
  return request<MarketDataCoverageResponse>(
    `/market-data/coverage${suffix ? `?${suffix}` : ""}`,
  );
}

export function updateOperatorConfig(
  payload: OperatorConfigRequest,
): Promise<OperatorConfigResponse> {
  return request<OperatorConfigResponse>("/controls/operator-config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runMarketSync(
  payload: MarketSyncControlRequest,
): Promise<MarketSyncControlResponse> {
  return request<MarketSyncControlResponse>("/controls/market-sync", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runWorkerCycle(): Promise<WorkerControlResponse> {
  return request<WorkerControlResponse>("/controls/worker-cycle", {
    method: "POST",
  });
}

export function runLiveReconcile(): Promise<LiveReconcileControlResponse> {
  return request<LiveReconcileControlResponse>("/controls/live-reconcile", {
    method: "POST",
  });
}

export function runLiveHalt(
  payload: LiveHaltControlRequest,
): Promise<LiveHaltControlResponse> {
  return request<LiveHaltControlResponse>("/controls/live-halt", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runLiveCancel(
  payload: LiveCancelControlRequest,
): Promise<LiveCancelControlResponse> {
  return request<LiveCancelControlResponse>("/controls/live-cancel", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runBacktest(
  payload: BacktestControlRequest,
): Promise<BacktestControlResponse> {
  return request<BacktestControlResponse>("/controls/backtest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getQualification(): Promise<QualificationReportResponse> {
  return request<QualificationReportResponse>("/controls/qualification");
}

export type TrainModelRequest = {
  symbol: string;
  timeframe: string;
  exchange: string;
  model_type: string;
  label_type: string;
  label_horizon: number;
  label_threshold: number;
  feature_names: string[];
  candle_limit: number;
  n_estimators: number;
  max_depth: number;
  learning_rate: number;
  split_ratio: number;
  buy_threshold: number;
  sell_threshold: number;
};

export type FeatureImportance = {
  feature: string;
  importance: number;
};

export type TrainModelResponse = {
  status: string;
  symbol: string;
  timeframe: string;
  model_type: string;
  model_path: string;
  label_type: string;
  label_horizon: number;
  label_threshold: number;
  feature_names: string[];
  oos_start_index: number;
  sample_count: number;
  train_count: number;
  test_count: number;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  roc_auc: number | null;
  feature_importances: FeatureImportance[];
  detail: string;
};

export type ModelStatusItem = {
  symbol: string;
  timeframe: string;
  model_type: string;
  model_path: string;
  exists: boolean;
  file_size_kb: number | null;
  label_type: string | null;
  label_horizon: number | null;
  label_threshold: number | null;
  feature_names: string[] | null;
  buy_threshold: number | null;
  sell_threshold: number | null;
  sample_count: number | null;
  train_count: number | null;
  test_count: number | null;
  oos_start_index: number | null;
  accuracy: number | null;
  roc_auc: number | null;
};

export type ModelStatusResponse = {
  models: ModelStatusItem[];
};

export function trainModel(payload: TrainModelRequest): Promise<TrainModelResponse> {
  return request<TrainModelResponse>("/controls/train-model", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getModelStatus(): Promise<ModelStatusResponse> {
  return request<ModelStatusResponse>("/controls/model-status");
}

export type LiveModeMetricsResponse = {
  trade_count: number;
  win_rate_pct: string | null;
  expectancy: string | null;
  max_drawdown_pct: string | null;
  total_net_pnl: string;
  total_fees_paid: string;
  avg_slippage_pct: string | null;
  slippage_sample_count: number;
};

export type ShadowModeMetricsResponse = {
  trade_count: number;
  win_rate_pct: string | null;
  expectancy: string | null;
  max_drawdown_pct: string | null;
  total_net_pnl: string;
};

export type OOSBaselineResponse = {
  backtest_run_id: number;
  run_date: string;
  oos_return_pct: string;
  oos_drawdown_pct: string;
  oos_total_trades: number;
  in_sample_return_pct: string;
  overfitting_warning: boolean;
};

export type StrategyHealthIndicatorsResponse = {
  slippage_vs_model_pct: string | null;
  shadow_vs_oos_expectancy_drift: string | null;
  live_vs_shadow_win_rate_drift: string | null;
  consecutive_losses: number;
  signal_frequency_per_week: string | null;
};

export type LivePerformanceReviewResponse = {
  live_metrics: LiveModeMetricsResponse | null;
  shadow_metrics: ShadowModeMetricsResponse;
  oos_baseline: OOSBaselineResponse | null;
  health_indicators: StrategyHealthIndicatorsResponse;
  recommendation: string;
  recommendation_reasons: string[];
  review_period_days: number;
  generated_at: string;
};

export function getPerformanceReview(
  review_period_days = 30,
): Promise<LivePerformanceReviewResponse> {
  return request<LivePerformanceReviewResponse>(
    `/reports/performance-review?review_period_days=${review_period_days}`,
  );
}
