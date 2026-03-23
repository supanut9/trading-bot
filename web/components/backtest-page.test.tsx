import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { BacktestPage } from "@/components/backtest-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/backtest",
}));

vi.mock("@/components/backtest-chart", () => ({
  BacktestChart: () => <div data-testid="backtest-chart-mock" />,
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

function submitBacktestForm(): void {
  const button = screen.getByRole("button", { name: "Run backtest" });
  const form = button.closest("form");
  if (!form) {
    throw new Error("Backtest form not found");
  }
  fireEvent.submit(form);
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

    if (url.includes("/reports/backtest-runs")) {
      return Promise.resolve(new Response(JSON.stringify({ run_count: 0, runs: [] })));
    }

    if (url.includes("/market-data/coverage")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            candle_count: 80,
            first_open_time: "2026-03-10T00:00:00Z",
            latest_open_time: "2026-03-19T15:00:00Z",
            latest_close_time: "2026-03-19T16:00:00Z",
            required_candles: 27,
            additional_candles_needed: 0,
            satisfies_required_candles: true,
            freshness_status: "fresh",
            readiness_status: "ready",
            detail: "stored history satisfies the selected replay shape",
          }),
        ),
      );
    }

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
            trading_mode: "SPOT",
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        strategy_name: "ema_crossover",
        symbol: "ETH/USDT",
        timeframe: "4h",
        starting_equity: 15000,
        trading_mode: "SPOT",
        slippage_pct: "0.0005",
        fee_pct: "0.001",
        spread_pct: "0",
        signal_latency_bars: 0,
        allowed_weekdays_utc: [],
        allowed_hours_utc: [],
        allow_partial_fills: false,
        fast_period: 12,
        slow_period: 26,
      });
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
            benchmark_realized_pnl: "180.00000000",
            benchmark_return_pct: "1.20000000",
            benchmark_excess_return_pct: "0.94000000",
            max_drawdown_pct: "1.25000000",
            total_trades: 4,
            winning_trades: 2,
            losing_trades: 0,
            total_fees_paid: "30.00000000",
            slippage_pct: "0.00050000",
            fee_pct: "0.00100000",
            spread_pct: "0.00000000",
            signal_latency_bars: 0,
            assumption_summary:
              "slippage_pct=0.0005, fee_pct=0.001, spread_pct=0, signal_latency_bars=0, allowed_weekdays_utc=[], allowed_hours_utc=[], max_volume_fill_pct=None, allow_partial_fills=False",
            allowed_weekdays_utc: [],
            allowed_hours_utc: [],
            max_volume_fill_pct: null,
            allow_partial_fills: false,
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
  await waitFor(() => expect(screen.getByText(/Replay minimum 27/)).toBeInTheDocument());
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
  submitBacktestForm();

  await waitFor(() => expect(screen.getByText("backtest completed")).toBeInTheDocument());
  expect(screen.getAllByText("ETH/USDT 4h").length).toBeGreaterThan(0);
  expect(screen.getByText("Notification sent")).toBeInTheDocument();
  expect(screen.getByText("EMA 12/26")).toBeInTheDocument();
  expect(screen.getByText("Slippage 0.0005%")).toBeInTheDocument();
  expect(screen.getByText("All UTC weekdays")).toBeInTheDocument();
  expect(screen.getByText("Buy and Hold")).toBeInTheDocument();
  expect(screen.getByText("Excess Return")).toBeInTheDocument();
  expect(screen.getAllByText(/\+1\.2/).length).toBeGreaterThan(0);
});

test("submits rule-builder preset payload", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.includes("/reports/backtest-runs")) {
      return Promise.resolve(new Response(JSON.stringify({ run_count: 0, runs: [] })));
    }

    if (url.includes("/market-data/coverage")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            candle_count: 20,
            first_open_time: "2026-03-10T00:00:00Z",
            latest_open_time: "2026-03-10T19:00:00Z",
            latest_close_time: "2026-03-10T20:00:00Z",
            required_candles: 51,
            additional_candles_needed: 31,
            satisfies_required_candles: false,
            freshness_status: "stale",
            readiness_status: "not_ready",
            detail: "need 31 more candles to satisfy replay minimum",
          }),
        ),
      );
    }

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
            trading_mode: "SPOT",
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        strategy_name: "rule_builder",
        symbol: "BTC/USDT",
        timeframe: "1h",
        starting_equity: 10000,
        trading_mode: "SPOT",
        slippage_pct: "0.0005",
        fee_pct: "0.001",
        spread_pct: "0",
        signal_latency_bars: 0,
        allowed_weekdays_utc: [],
        allowed_hours_utc: [],
        allow_partial_fills: false,
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
      });
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
            total_fees_paid: null,
            slippage_pct: "0.00050000",
            fee_pct: "0.00100000",
            spread_pct: "0.00000000",
            signal_latency_bars: 0,
            assumption_summary:
              "slippage_pct=0.0005, fee_pct=0.001, spread_pct=0, signal_latency_bars=0, allowed_weekdays_utc=[], allowed_hours_utc=[], max_volume_fill_pct=None, allow_partial_fills=False",
            allowed_weekdays_utc: [],
            allowed_hours_utc: [],
            max_volume_fill_pct: null,
            allow_partial_fills: false,
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
  submitBacktestForm();

  await waitFor(() => expect(screen.getByText("not_enough_candles")).toBeInTheDocument());
  expect(screen.getAllByText("rule_builder").length).toBeGreaterThan(0);
  expect(screen.getByText("EMA 20/50 bullish cross")).toBeInTheDocument();
});

test("submits edited rule-builder conditions", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.includes("/reports/backtest-runs")) {
      return Promise.resolve(new Response(JSON.stringify({ run_count: 0, runs: [] })));
    }

    if (url.includes("/market-data/coverage")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            candle_count: 120,
            first_open_time: "2026-03-01T00:00:00Z",
            latest_open_time: "2026-03-19T15:00:00Z",
            latest_close_time: "2026-03-19T16:00:00Z",
            required_candles: 51,
            additional_candles_needed: 0,
            satisfies_required_candles: true,
            freshness_status: "fresh",
            readiness_status: "ready",
            detail: "stored history satisfies the selected replay shape",
          }),
        ),
      );
    }

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
            trading_mode: "SPOT",
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        strategy_name: "rule_builder",
        symbol: "BTC/USDT",
        timeframe: "1h",
        starting_equity: 10000,
        trading_mode: "SPOT",
        slippage_pct: "0.0005",
        fee_pct: "0.001",
        spread_pct: "0",
        signal_latency_bars: 0,
        allowed_weekdays_utc: [],
        allowed_hours_utc: [],
        allow_partial_fills: false,
        rules: {
          shared_filters: {
            logic: "all",
            conditions: [
              {
                indicator: "price_vs_ema",
                operator: "below",
                period: 30,
              },
            ],
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
                threshold: "60",
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
      });
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "backtest completed",
            notified: false,
            strategy_name: "rule_builder",
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            fast_period: null,
            slow_period: null,
            starting_equity_input: "10000.00000000",
            candle_count: 120,
            required_candles: 51,
            starting_equity: "10000.00000000",
            ending_equity: "10125.00000000",
            realized_pnl: "125.00000000",
            total_return_pct: "1.25000000",
            max_drawdown_pct: "0.80000000",
            total_trades: 2,
            winning_trades: 1,
            losing_trades: 0,
            total_fees_paid: "10.00000000",
            slippage_pct: "0.00050000",
            fee_pct: "0.00100000",
            spread_pct: "0.00000000",
            signal_latency_bars: 0,
            assumption_summary:
              "slippage_pct=0.0005, fee_pct=0.001, spread_pct=0, signal_latency_bars=0, allowed_weekdays_utc=[], allowed_hours_utc=[], max_volume_fill_pct=None, allow_partial_fills=False",
            allowed_weekdays_utc: [],
            allowed_hours_utc: [],
            max_volume_fill_pct: null,
            allow_partial_fills: false,
            rules: {
              shared_filters: {
                logic: "all",
                conditions: [
                  {
                    indicator: "price_vs_ema",
                    operator: "below",
                    period: 30,
                  },
                ],
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
                    threshold: "60",
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

  fireEvent.click(screen.getAllByRole("button", { name: "Add condition" })[0]);
  fireEvent.change(screen.getByLabelText("Shared filters condition 1 indicator"), {
    target: { value: "price_vs_ema" },
  });
  fireEvent.change(screen.getByLabelText("Shared filters condition 1 operator"), {
    target: { value: "below" },
  });
  fireEvent.change(screen.getByLabelText("Shared filters condition 1 period"), {
    target: { value: "30" },
  });
  fireEvent.change(screen.getByLabelText("Buy rules condition 2 threshold"), {
    target: { value: "60" },
  });
  submitBacktestForm();

  await waitFor(() => expect(screen.getByText("backtest completed")).toBeInTheDocument());
  expect(screen.getByText("Estimated minimum candles: 51")).toBeInTheDocument();
});

test("submits explicit friction assumptions and renders summary badges", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.includes("/reports/backtest-runs")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            run_count: 1,
            runs: [
              {
                id: 41,
                created_at: "2026-03-22T03:40:00Z",
                source: "api.control",
                status: "completed",
                detail: "backtest completed",
                strategy_name: "ema_crossover",
                exchange: "binance",
                symbol: "SOL/USDT",
                timeframe: "15m",
                trading_mode: "SPOT",
                fast_period: 8,
                slow_period: 21,
                starting_equity_input: "12000.00000000",
                candle_count: 480,
                required_candles: 22,
                starting_equity: "12000.00000000",
                ending_equity: "12180.00000000",
                realized_pnl: "180.00000000",
                total_return_pct: "1.50000000",
                max_drawdown_pct: "0.90000000",
                total_trades: 6,
                winning_trades: 4,
                losing_trades: 2,
                slippage_pct: "0.00100000",
                fee_pct: "0.00100000",
                spread_pct: "0.00200000",
                signal_latency_bars: 1,
                assumption_summary:
                  "slippage_pct=0.001, fee_pct=0.001, spread_pct=0.002, signal_latency_bars=1, allowed_weekdays_utc=[1, 3], allowed_hours_utc=[8, 12], max_volume_fill_pct=0.25, allow_partial_fills=True",
                allowed_weekdays_utc: [1, 3],
                allowed_hours_utc: [8, 12],
                max_volume_fill_pct: "0.25000000",
                allow_partial_fills: true,
                leverage: null,
                margin_mode: null,
                liquidation_count: 0,
                rules: null,
              },
            ],
          }),
        ),
      );
    }

    if (url.includes("/market-data/coverage")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            candle_count: 180,
            first_open_time: "2026-03-01T00:00:00Z",
            latest_open_time: "2026-03-19T20:00:00Z",
            latest_close_time: "2026-03-20T00:00:00Z",
            required_candles: 27,
            additional_candles_needed: 0,
            satisfies_required_candles: true,
            freshness_status: "fresh",
            readiness_status: "ready",
            detail: "stored history satisfies the selected replay shape",
          }),
        ),
      );
    }

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
            trading_mode: "SPOT",
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/backtest")) {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        strategy_name: "ema_crossover",
        symbol: "BTC/USDT",
        timeframe: "1h",
        starting_equity: 10000,
        trading_mode: "SPOT",
        slippage_pct: "0.001",
        fee_pct: "0.001",
        spread_pct: "0.002",
        signal_latency_bars: 1,
        allowed_weekdays_utc: [1, 3],
        allowed_hours_utc: [8, 12],
        max_volume_fill_pct: "0.25",
        allow_partial_fills: true,
        fast_period: 20,
        slow_period: 50,
      });
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "backtest completed",
            notified: false,
            strategy_name: "ema_crossover",
            exchange: "binance",
            symbol: "BTC/USDT",
            timeframe: "1h",
            trading_mode: "SPOT",
            fast_period: 20,
            slow_period: 50,
            starting_equity_input: "10000.00000000",
            candle_count: 180,
            required_candles: 27,
            starting_equity: "10000.00000000",
            ending_equity: "10110.00000000",
            realized_pnl: "110.00000000",
            total_return_pct: "1.10000000",
            max_drawdown_pct: "0.80000000",
            total_trades: 3,
            winning_trades: 2,
            losing_trades: 1,
            total_fees_paid: "15.00000000",
            slippage_pct: "0.00100000",
            fee_pct: "0.00100000",
            spread_pct: "0.00200000",
            signal_latency_bars: 1,
            assumption_summary:
              "slippage_pct=0.001, fee_pct=0.001, spread_pct=0.002, signal_latency_bars=1, allowed_weekdays_utc=[1, 3], allowed_hours_utc=[8, 12], max_volume_fill_pct=0.25, allow_partial_fills=True",
            allowed_weekdays_utc: [1, 3],
            allowed_hours_utc: [8, 12],
            max_volume_fill_pct: "0.25000000",
            allow_partial_fills: true,
            rules: null,
            executions: [],
            candles: [],
          }),
        ),
      );
    }

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByDisplayValue("BTC/USDT")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Slippage %"), { target: { value: "0.001" } });
  fireEvent.change(screen.getByLabelText("Spread %"), { target: { value: "0.002" } });
  fireEvent.change(screen.getByLabelText("Latency Bars"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("UTC Weekdays"), { target: { value: "1,3" } });
  fireEvent.change(screen.getByLabelText("UTC Hours"), { target: { value: "8,12" } });
  fireEvent.change(screen.getByLabelText("Max Volume Fill %"), { target: { value: "0.25" } });
  fireEvent.click(screen.getByLabelText(/Allow deterministic partial fills/i));
  submitBacktestForm();

  await waitFor(() => expect(screen.getByText("backtest completed")).toBeInTheDocument());
  expect(screen.getAllByText("UTC weekdays 1, 3").length).toBeGreaterThan(0);
  expect(screen.getAllByText("UTC hours 8, 12").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Max volume fill 25%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Partial fills allowed").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/allowed_weekdays_utc=\[1, 3\]/).length).toBeGreaterThan(0);
  expect(screen.getByText("SOL/USDT 15m")).toBeInTheDocument();
});

test("loads a recent run back into the form", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo) => {
    const url = input.toString();

    if (url.includes("/reports/backtest-runs")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            run_count: 1,
            runs: [
              {
                id: 9,
                created_at: "2026-03-20T03:40:00Z",
                source: "api.control",
                status: "completed",
                detail: "backtest completed",
                strategy_name: "rule_builder",
                exchange: "binance",
                symbol: "ETH/USDT",
                timeframe: "4h",
                fast_period: null,
                slow_period: null,
                starting_equity_input: "25000.00000000",
                candle_count: 180,
                required_candles: 51,
                starting_equity: "25000.00000000",
                ending_equity: "25500.00000000",
                realized_pnl: "500.00000000",
                total_return_pct: "2.00000000",
                max_drawdown_pct: "0.75000000",
                total_trades: 3,
                winning_trades: 2,
                losing_trades: 1,
                slippage_pct: "0.00100000",
                fee_pct: "0.00100000",
                spread_pct: "0.00200000",
                signal_latency_bars: 1,
                assumption_summary:
                  "slippage_pct=0.001, fee_pct=0.001, spread_pct=0.002, signal_latency_bars=1, allowed_weekdays_utc=[1, 3], allowed_hours_utc=[8, 12], max_volume_fill_pct=0.25, allow_partial_fills=True",
                allowed_weekdays_utc: [1, 3],
                allowed_hours_utc: [8, 12],
                max_volume_fill_pct: "0.25000000",
                allow_partial_fills: true,
                rules: {
                  shared_filters: { logic: "all", conditions: [] },
                  buy_rules: {
                    logic: "all",
                    conditions: [
                      {
                        indicator: "ema_cross",
                        operator: "bullish",
                        fast_period: 12,
                        slow_period: 26,
                      },
                    ],
                  },
                  sell_rules: {
                    logic: "all",
                    conditions: [
                      {
                        indicator: "ema_cross",
                        operator: "bearish",
                        fast_period: 12,
                        slow_period: 26,
                      },
                    ],
                  },
                },
              },
            ],
          }),
        ),
      );
    }

    if (url.includes("/market-data/coverage")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            exchange: "binance",
            symbol: "ETH/USDT",
            timeframe: "4h",
            candle_count: 180,
            first_open_time: "2026-02-01T00:00:00Z",
            latest_open_time: "2026-03-19T20:00:00Z",
            latest_close_time: "2026-03-20T00:00:00Z",
            required_candles: 27,
            additional_candles_needed: 0,
            satisfies_required_candles: true,
            freshness_status: "fresh",
            readiness_status: "ready",
            detail: "stored history satisfies the selected replay shape",
          }),
        ),
      );
    }

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
            trading_mode: "SPOT",
            source: "runtime_config",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByRole("button", { name: "Load run" })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: "Load run" }));

  await waitFor(() => expect(screen.getByDisplayValue("ETH/USDT")).toBeInTheDocument());
  expect(screen.getByDisplayValue("4h")).toBeInTheDocument();
  expect(screen.getByLabelText("Starting Equity")).toHaveValue(25000);
  expect(screen.getByLabelText("Fast EMA")).toHaveValue(12);
  expect(screen.getByLabelText("Slow EMA")).toHaveValue(26);
  expect(screen.getByLabelText("UTC Weekdays")).toHaveValue("1, 3");
  expect(screen.getByLabelText("UTC Hours")).toHaveValue("8, 12");
  expect(screen.getByLabelText("Max Volume Fill %")).toHaveValue(0.25);
  expect(screen.getByLabelText(/Allow deterministic partial fills/i)).toBeChecked();
  expect(screen.getAllByDisplayValue("rule_builder").length).toBeGreaterThan(0);
});
