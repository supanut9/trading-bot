import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { DashboardPage } from "@/components/dashboard-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("@/components/trading-chart", () => ({
  TradingChart: () => <div data-testid="trading-chart-mock" />,
}));

const fetchMock = vi.fn();

function renderWithQueryClient(): void {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  fetchMock.mockReset();
});

test("renders dashboard data from backend endpoints", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo) => {
    const url = input.toString();
    if (url.endsWith("/status")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            app: "trading-bot",
            environment: "local",
            execution_mode: "paper",
            paper_trading: true,
            live_trading_enabled: false,
            live_trading_halted: false,
            live_safety_status: "paper_only",
            live_max_order_notional: null,
            live_max_position_quantity: null,
            exchange: "binance",
            strategy_name: "ema_crossover",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: 20,
            slow_period: 50,
            operator_config_source: "env",
            database_url: "sqlite:///./trading_bot.db",
            database_status: "ready",
            latest_price_status: "ready",
            latest_price: "101250.25",
            account_balance_status: "not_available",
            account_balances: [],
          }),
        ),
      );
    }
    if (url.endsWith("/performance/summary")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            summaries: [
              {
                mode: "paper",
                total_realized_pnl: "320.55",
                total_unrealized_pnl: "12.30",
                total_fees: "5.10",
                net_pnl: "327.75",
                trade_count: 14,
                closed_trade_count: 8,
                winning_trades: 5,
                losing_trades: 3,
                win_rate_pct: "62.5",
                average_win: "95.50",
                average_loss: "-48.10",
                profit_factor: "1.98",
                expectancy: "23.40",
                max_drawdown: "75.00",
                open_position_count: 1,
              },
            ],
            equity_curve: [
              {
                mode: "paper",
                recorded_at: "2026-03-19T00:00:00Z",
                net_pnl: "0",
                drawdown: "0",
              },
              {
                mode: "paper",
                recorded_at: "2026-03-19T01:00:00Z",
                net_pnl: "327.75",
                drawdown: "12.00",
              },
            ],
            daily_rows: [],
          }),
        ),
      );
    }
    if (url.includes("/positions")) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              exchange: "binance",
              symbol: "BTC/USDT",
              side: "long",
              mode: "paper",
              quantity: "0.0100",
              average_entry_price: "100000",
              realized_pnl: "100.50",
              unrealized_pnl: "22.10",
            },
          ]),
        ),
      );
    }
    return Promise.resolve(
      new Response(
        JSON.stringify([
          {
            id: 7,
            order_id: 11,
            exchange: "binance",
            symbol: "BTC/USDT",
            side: "buy",
            quantity: "0.0100",
            price: "100100",
            fee_amount: "0.1",
            fee_asset: "USDT",
          },
        ]),
      ),
    );
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByText("Paper Trading Situation Room")).toBeInTheDocument());
  await waitFor(() => expect(screen.getByText("#7")).toBeInTheDocument());
  expect(screen.getAllByText("BTC/USDT").length).toBeGreaterThan(0);
  expect(screen.getByText("#7")).toBeInTheDocument();
});

test("shows panel state when one feed fails", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo) => {
    const url = input.toString();
    if (url.endsWith("/positions")) {
      return Promise.resolve(new Response("boom", { status: 500 }));
    }
    if (url.endsWith("/status")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            app: "trading-bot",
            environment: "local",
            execution_mode: "paper",
            paper_trading: true,
            live_trading_enabled: false,
            live_trading_halted: false,
            live_safety_status: "paper_only",
            live_max_order_notional: null,
            live_max_position_quantity: null,
            exchange: "binance",
            strategy_name: "ema_crossover",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: 20,
            slow_period: 50,
            operator_config_source: "env",
            database_url: "sqlite:///./trading_bot.db",
            database_status: "ready",
            latest_price_status: "ready",
            latest_price: "101250.25",
            account_balance_status: "not_available",
            account_balances: [],
          }),
        ),
      );
    }
    if (url.endsWith("/performance/summary")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            summaries: [],
            equity_curve: [],
            daily_rows: [],
          }),
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify([])));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByText("Position feed unavailable")).toBeInTheDocument());
  expect(screen.getByText("Trade rows appear here after paper fills or reconciled live fills are recorded.")).toBeInTheDocument();
});
