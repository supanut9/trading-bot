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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
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
