import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

import { RuntimePage } from "@/components/runtime-page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/runtime",
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
      <RuntimePage />
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

test("hydrates and updates runtime defaults", async () => {
  fetchMock.mockImplementation((input: URL | RequestInfo, init?: RequestInit) => {
    const url = input.toString();

    if (url.endsWith("/controls/operator-config") && !init?.method) {
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

    if (url.endsWith("/controls/operator-config") && init?.method === "POST") {
      expect(init.body).toBe(
        JSON.stringify({
          strategy_name: "ema_crossover",
          symbol: "ETH/USDT",
          timeframe: "4h",
          fast_period: 12,
          slow_period: 26,
        }),
      );
      return Promise.resolve(
        new Response(
          JSON.stringify({
            status: "completed",
            detail: "operator runtime config updated",
            strategy_name: "ema_crossover",
            exchange: "binance",
            symbol: "ETH/USDT",
            timeframe: "4h",
            fast_period: 12,
            slow_period: 26,
            source: "db",
            changed: true,
            notified: false,
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
  fireEvent.change(screen.getByDisplayValue("20"), {
    target: { value: "12" },
  });
  fireEvent.change(screen.getByDisplayValue("50"), {
    target: { value: "26" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save runtime defaults" }));

  await waitFor(() => expect(screen.getByText("operator runtime config updated")).toBeInTheDocument());
  expect(screen.getByText("Changed")).toBeInTheDocument();
});
