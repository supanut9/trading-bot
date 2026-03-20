import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { ControlsPage } from "@/components/controls-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/controls",
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
      <ControlsPage />
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

test("hydrates defaults and runs market, worker, and live control actions", async () => {
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
            source: "db",
            changed: false,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/status")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            app: "trading-bot",
            environment: "local",
            execution_mode: "live",
            paper_trading: false,
            live_trading_enabled: true,
            live_trading_halted: false,
            live_safety_status: "ready",
            live_max_order_notional: "250.00",
            live_max_position_quantity: "0.0200",
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
            account_balance_status: "ready",
            account_balances: [],
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
            candle_count: 300,
            first_open_time: "2026-03-07T00:00:00Z",
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

    if (url.endsWith("/controls/market-sync")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(
        JSON.stringify({
          symbol: "SOL/USDT",
          timeframe: "15m",
          limit: 250,
          backfill: true,
        }),
      );
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "market data backfill completed",
            symbol: "SOL/USDT",
            timeframe: "15m",
            limit: 250,
            backfill: true,
            fetched_count: 42,
            stored_count: 35,
            latest_open_time: "2026-03-19T16:00:00Z",
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/worker-cycle")) {
      expect(init?.method).toBe("POST");
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "executed",
            detail: "signal executed in paper mode",
            signal_action: "buy",
            client_order_id: "paper-btc-1h-20260319",
            order_id: 44,
            trade_id: 88,
            position_quantity: "0.01",
            notified: true,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/live-halt")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ halted: true }));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "live entry halted",
            live_trading_halted: true,
            changed: true,
            notified: false,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/live-reconcile")) {
      expect(init?.method).toBe("POST");
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "live reconcile completed",
            reconciled_count: 2,
            filled_count: 1,
            review_required_count: 1,
            notified: true,
          }),
        ),
      );
    }

    if (url.endsWith("/controls/live-cancel")) {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBe(JSON.stringify({ order_id: 44 }));
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "live order canceled",
            order_id: 44,
            client_order_id: "paper-btc-1h-20260319",
            exchange_order_id: "789",
            order_status: "canceled",
            notified: false,
          }),
        ),
      );
    }

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByDisplayValue("BTC/USDT")).toBeInTheDocument());
  await waitFor(() => expect(screen.getByText(/Replay minimum 51/)).toBeInTheDocument());
  fireEvent.change(screen.getByDisplayValue("BTC/USDT"), {
    target: { value: "SOL/USDT" },
  });
  fireEvent.change(screen.getByDisplayValue("1h"), {
    target: { value: "15m" },
  });
  fireEvent.change(screen.getByDisplayValue("300"), {
    target: { value: "250" },
  });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Run market sync" }));

  await waitFor(() => expect(screen.getByText("market data backfill completed")).toBeInTheDocument());
  expect(screen.getByText("SOL/USDT 15m")).toBeInTheDocument();
  expect(screen.getByText("42")).toBeInTheDocument();
  expect(screen.getByText("35")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run worker cycle" }));

  await waitFor(() => expect(screen.getByText("signal executed in paper mode")).toBeInTheDocument());
  expect(screen.getByText("executed")).toBeInTheDocument();
  expect(screen.getByText("Order 44")).toBeInTheDocument();
  expect(screen.getByText("Trade 88")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Halt live entry" }));

  await waitFor(() => expect(screen.getByText("live entry halted")).toBeInTheDocument());
  expect(screen.getByText("State changed")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run live reconcile" }));

  await waitFor(() => expect(screen.getByText("live reconcile completed")).toBeInTheDocument());
  expect(screen.getByText("Reconciled 2")).toBeInTheDocument();
  expect(screen.getByText("Filled 1")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("123"), {
    target: { value: "44" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Cancel live order" }));

  await waitFor(() => expect(screen.getByText("live order canceled")).toBeInTheDocument());
  expect(screen.getByText("Status canceled · order 44")).toBeInTheDocument();
});
