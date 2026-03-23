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

test("hydrates defaults and runs worker and live control actions", async () => {
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
            live_recovery_summary: {
              posture: "clear",
              dominant_recovery_state: "resolved",
              next_action: "none",
              summary: "No unresolved live recovery work remains.",
              unresolved_order_count: 0,
              awaiting_exchange_count: 0,
              partial_fill_in_flight_count: 0,
              stale_open_order_count: 0,
              stale_partial_fill_count: 0,
              manual_review_required_count: 0,
              requires_operator_review_count: 0,
              stale_order_count: 0,
            },
            account_balance_status: "ready",
            account_balances: [],
          }),
        ),
      );
    }

    if (url.endsWith("/controls/qualification")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            all_passed: false,
            gates: [],
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
            live_recovery_summary: {
              posture: "manual_review_required",
              dominant_recovery_state: "manual_review_required",
              next_action: "inspect_exchange_state",
              summary: "1 unresolved live order requires manual exchange-state review",
              unresolved_order_count: 1,
              awaiting_exchange_count: 0,
              partial_fill_in_flight_count: 0,
              stale_open_order_count: 0,
              stale_partial_fill_count: 0,
              manual_review_required_count: 1,
              requires_operator_review_count: 1,
              stale_order_count: 0,
            },
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
            recovery_summary: "orders=2 filled=1 review_required=1",
            live_recovery_summary: {
              posture: "stale_orders",
              dominant_recovery_state: "stale_open_order",
              next_action: "reconcile_or_cancel",
              summary: "1 stale live order requires reconcile or cancel review",
              unresolved_order_count: 1,
              awaiting_exchange_count: 0,
              partial_fill_in_flight_count: 0,
              stale_open_order_count: 1,
              stale_partial_fill_count: 0,
              manual_review_required_count: 0,
              requires_operator_review_count: 0,
              stale_order_count: 1,
            },
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

  // Wait for operator config to load (strategy name appears in the runtime strip)
  await waitFor(() => expect(screen.getByText("ema_crossover")).toBeInTheDocument());
  expect(screen.getByText("Posture clear")).toBeInTheDocument();
  expect(screen.getByText("No unresolved live recovery work remains.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run worker cycle" }));

  await waitFor(() => expect(screen.getByText("signal executed in paper mode")).toBeInTheDocument());
  expect(screen.getByText("executed")).toBeInTheDocument();
  expect(screen.getByText("Order 44")).toBeInTheDocument();
  expect(screen.getByText("Trade 88")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Halt live entry" }));

  await waitFor(() => expect(screen.getByText("live entry halted")).toBeInTheDocument());
  expect(screen.getByText("State changed")).toBeInTheDocument();
  expect(screen.getByText("Posture manual_review_required")).toBeInTheDocument();
  expect(
    screen.getByText("1 unresolved live order requires manual exchange-state review"),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run live reconcile" }));

  await waitFor(() => expect(screen.getByText("live reconcile completed")).toBeInTheDocument());
  expect(screen.getByText("Reconciled 2")).toBeInTheDocument();
  expect(screen.getByText("Filled 1")).toBeInTheDocument();
  expect(screen.getByText("Posture stale_orders")).toBeInTheDocument();
  expect(
    screen.getByText("1 stale live order requires reconcile or cancel review"),
  ).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("123"), {
    target: { value: "44" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Cancel live order" }));

  await waitFor(() => expect(screen.getByText("live order canceled")).toBeInTheDocument());
  expect(screen.getByText("Status canceled · order 44")).toBeInTheDocument();
});
