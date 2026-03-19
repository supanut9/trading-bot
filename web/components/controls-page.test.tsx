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

test("hydrates runtime defaults and runs market sync", async () => {
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

    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });

  renderWithQueryClient();

  await waitFor(() => expect(screen.getByDisplayValue("BTC/USDT")).toBeInTheDocument());
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
});
