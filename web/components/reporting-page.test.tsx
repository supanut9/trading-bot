import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { ReportingPage } from "@/components/reporting-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/reports",
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
      <ReportingPage />
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

test("renders reporting analytics, recovery data, and export links", async () => {
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
            operator_config_source: "db",
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

    if (url.includes("/reports/recovery")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            live_trading_enabled: true,
            live_trading_halted: true,
            live_safety_status: "halted",
            stale_threshold_minutes: 60,
            stale_live_orders: [
              {
                id: 44,
                symbol: "BTC/USDT",
                side: "buy",
                status: "open",
                client_order_id: "live-order-44",
                exchange_order_id: "789",
                updated_at: "2026-03-19T00:30:00Z",
                age_minutes: 90,
              },
            ],
            unresolved_orders: [
              {
                id: 44,
                symbol: "BTC/USDT",
                side: "buy",
                status: "review_required",
                client_order_id: "live-order-44",
                exchange_order_id: "789",
                quantity: "0.01000000",
                price: "100000.00",
                updated_at: "2026-03-19T00:30:00Z",
                requires_operator_review: true,
                next_action: "inspect_exchange_state",
              },
            ],
            recovery_events: [
              {
                created_at: "2026-03-19T01:00:00Z",
                event_type: "live_cancel",
                source: "api.control",
                status: "completed",
                detail: "live order canceled",
                context: "order_id=44 client_order_id=live-order-44 order_status=canceled",
              },
            ],
            unresolved_live_orders: 1,
            recovery_event_count: 1,
            latest_recovery_event_at: "2026-03-19T01:00:00Z",
            latest_recovery_event_type: "live_cancel",
            latest_recovery_event_status: "completed",
            latest_recovery_event_context:
              "order_id=44 client_order_id=live-order-44 order_status=canceled",
            filters: {
              order_status: null,
              requires_review: null,
              event_type: null,
              search: null,
            },
          }),
        ),
      );
    }

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
          daily_rows: [
            {
              mode: "paper",
              trade_date: "2026-03-19",
              trade_count: 4,
              closed_trade_count: 2,
              winning_trades: 1,
              losing_trades: 1,
              realized_pnl: "40.00",
              fees: "1.20",
              net_pnl: "38.80",
            },
          ],
        }),
      ),
    );
  });

  renderWithQueryClient();

  await waitFor(() =>
    expect(screen.getByText("Performance And Recovery Ledger")).toBeInTheDocument(),
  );
  expect(screen.getByText("Daily performance")).toBeInTheDocument();
  expect(screen.getByText("Recovery Overview")).toBeInTheDocument();
  expect(screen.getByText("Recovery Queue")).toBeInTheDocument();
  expect(screen.getByText("Recovery Timeline")).toBeInTheDocument();
  expect(screen.getAllByText("Live recovery")).toHaveLength(2);
  expect(screen.getByText("Daily Rollup")).toBeInTheDocument();
});
