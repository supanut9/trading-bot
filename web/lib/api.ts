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
  source: string;
  changed: boolean;
  notified: boolean;
};

export type BacktestExecutionResponse = {
  action: string;
  price: string;
  quantity: string;
  realized_pnl: string;
  reason: string;
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
};

export type BacktestControlResponse = {
  status: string;
  detail: string;
  notified: boolean;
  strategy_name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
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
  executions: BacktestExecutionResponse[];
};

export type OperatorConfigRequest = {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  fast_period: number;
  slow_period: number;
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
