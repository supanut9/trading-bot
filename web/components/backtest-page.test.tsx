import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { BacktestPage } from "@/components/backtest-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/backtest",
}));

const fetchMock = vi.fn();

function renderWithQueryClient(): void {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <BacktestPage />
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

test("hydrates defaults and runs ema backtest", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.endsWith("/controls/operator-config")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "operator runtime config loaded",
            strategy_name: "ema_crossover",
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: 20,
            slow_period: 50,
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          strategy_name: "ema_crossover",
          symbol: "ETH/USDT",
          timeframe: "4h",
          starting_equity: 15000,
          fast_period: 12,
          slow_period: 26,
        }),
      );
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "backtest completed",
            notified: true,
            strategy_name: "ema_crossover",
            exchange: "binance",
            symbol: "ETH/USDT",
            timeframe: "4h",
            fast_period: 12,
            slow_period: 26,
            starting_equity_input: "15000.00000000",
            candle_count: 300,
            required_candles: 27,
            starting_equity: "15000.00000000",
            ending_equity: "15320.50000000",
            realized_pnl: "320.50000000",
            total_return_pct: "2.14000000",
            max_drawdown_pct: "1.25000000",
            total_trades: 4,
            winning_trades: 2,
            losing_trades: 0,
            rules: null,
            executions: [
              {
                action: "buy",
                price: "100000.00",
                quantity: "0.01000000",
                realized_pnl: "0",
                reason: "EMA bullish cross",
              },
              {
                action: "sell",
                price: "103205.00",
                quantity: "0.01000000",
                realized_pnl: "320.50000000",
                reason: "EMA bearish cross",
              },
            ],
          }),
        ),
      );
    }

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByDisplayValue("BTC/USDT")).toBeInTheDocument());
  fireEvent.change(screen.getByDisplayValue("BTC/USDT"), {
    target: { value: "ETH/USDT" },
  });
  fireEvent.change(screen.getByDisplayValue("1h"), {
    target: { value: "4h" },
  });
  fireEvent.change(screen.getByDisplayValue("10000"), {
    target: { value: "15000" },
  });
  fireEvent.change(screen.getByDisplayValue("20"), {
    target: { value: "12" },
  });
  fireEvent.change(screen.getByDisplayValue("50"), {
    target: { value: "26" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  await waitFor(() => expect(screen.getByText("backtest completed")).toBeInTheDocument());
  expect(screen.getAllByText("ETH/USDT 4h").length).toBeGreaterThan(0);
  expect(screen.getByText("Notification sent")).toBeInTheDocument();
  expect(screen.getByText("EMA 12/26")).toBeInTheDocument();
});

test("submits rule-builder preset payload", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.endsWith("/controls/operator-config")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "operator runtime config loaded",
            strategy_name: "ema_crossover",
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: 20,
            slow_period: 50,
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          strategy_name: "rule_builder",
          symbol: "BTC/USDT",
          timeframe: "1h",
          starting_equity: 10000,
          rules: {
            shared_filters: {
              logic: "all",
              conditions: [],
            },
            buy_rules: {
              logic: "all",
              conditions: [
                {
                  indicator: "ema_cross",
                  operator: "bullish",
                  fast_period: 20,
                  slow_period: 50,
                },
                {
                  indicator: "rsi_threshold",
                  operator: "above",
                  period: 14,
                  threshold: "55",
                },
              ],
            },
            sell_rules: {
              logic: "all",
              conditions: [
                {
                  indicator: "ema_cross",
                  operator: "bearish",
                  fast_period: 20,
                  slow_period: 50,
                },
                {
                  indicator: "rsi_threshold",
                  operator: "below",
                  period: 14,
                  threshold: "45",
                },
              ],
            },
          },
        }),
      );
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "skipped",
            detail: "not_enough_candles",
            notified: false,
            strategy_name: "rule_builder",
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: null,
            slow_period: null,
            starting_equity_input: "10000.00000000",
            candle_count: 20,
            required_candles: 51,
            starting_equity: null,
            ending_equity: null,
            realized_pnl: null,
            total_return_pct: null,
            max_drawdown_pct: null,
            total_trades: null,
            winning_trades: null,
            losing_trades: null,
            rules: {
              shared_filters: {
                logic: "all",
                conditions: [],
              },
              buy_rules: {
                logic: "all",
                conditions: [
                  {
                    indicator: "ema_cross",
                    operator: "bullish",
                    fast_period: 20,
                    slow_period: 50,
                  },
                ],
              },
              sell_rules: {
                logic: "all",
                conditions: [
                  {
                    indicator: "ema_cross",
                    operator: "bearish",
                    fast_period: 20,
                    slow_period: 50,
                  },
                ],
              },
            },
            executions: [],
          }),
        ),
      );
    }

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByDisplayValue("ema_crossover")).toBeInTheDocument());
  fireEvent.change(screen.getByDisplayValue("ema_crossover"), {
    target: { value: "rule_builder" },
  });
  fireEvent.change(screen.getByDisplayValue("EMA Crossover Mirror"), {
    target: { value: "ema_rsi_confirmation" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run backtest" }));

  await waitFor(() => expect(screen.getByText("not_enough_candles")).toBeInTheDocument());
  expect(screen.getAllByText("rule_builder").length).toBeGreaterThan(0);
  expect(screen.getByText("EMA 20/50 bullish cross")).toBeInTheDocument();
});
