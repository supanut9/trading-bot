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
