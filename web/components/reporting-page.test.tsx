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
            runtime_promotion_stage: "shadow",
            runtime_promotion_blockers: [],
            runtime_promotion_next_prerequisite: null,
            account_balance_status: "not_available",
            account_balances: [],
          }),
        ),
      );
    }

    if (url.includes("/reports/performance-review")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            live_metrics: null,
            shadow_metrics: {
              trade_count: 12,
              win_rate_pct: "58.0",
              expectancy: "14.0",
              total_return_pct: "6.5",
              max_drawdown_pct: "8.0",
              total_net_pnl: "125.0",
            },
            oos_baseline: {
              backtest_run_id: 91,
              run_date: "2026-03-19T00:00:00Z",
              oos_return_pct: "5.0",
              oos_drawdown_pct: "9.0",
              oos_total_trades: 42,
              in_sample_return_pct: "7.5",
              modeled_slippage_pct: "0.30",
              overfitting_warning: false,
            },
            health_indicators: {
              slippage_vs_model_pct: null,
              shadow_vs_oos_expectancy_drift: "30.0",
              live_vs_shadow_win_rate_drift: null,
              consecutive_losses: 0,
              signal_frequency_per_week: null,
            },
            root_cause: {
              primary_driver: "insufficient_live_data",
              regime_assessment: "insufficient_live_sample",
              summary: "Live evidence is still too thin for a strong edge-decay call.",
              operator_focus: ["Keep collecting shadow and live review evidence."],
            },
            latest_decision: null,
            recommendation: "keep_running",
            recommendation_reasons: ["No live trades yet; keep collecting sample data."],
            review_period_days: 30,
            generated_at: "2026-03-20T00:00:00Z",
          }),
        ),
      );
    }

    if (url.includes("/performance/iteration-plan")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            recommendation: "pause_and_rework",
            recommendation_reasons: ["Shadow drift remains above the accepted range."],
            all_steps_clear: false,
            generated_at: "2026-03-20T00:00:00Z",
            exchange: "binance",
            symbol: "BTC/USDT",
            review_period_days: 30,
            steps: [
              {
                name: "record_operator_decision",
                status: "required",
                description: "Record a fresh operator review decision before acting on the plan.",
                evidence: "current_runtime_stage=shadow; no persisted review decision",
              },
              {
                name: "adjust_runtime_promotion",
                status: "passed",
                description: "Runtime promotion stage is already at a safe pre-live posture.",
                evidence: "current_runtime_stage=shadow",
              },
            ],
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

    if (url.includes("/reports/notifications")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            delivery_count: 2,
            failed_count: 1,
            latest_delivery_at: "2026-03-19T02:00:00Z",
            latest_delivery_status: "failed",
            latest_delivery_channel: "webhook",
            latest_related_event_type: "worker_cycle",
            filters: {
              status: null,
              channel: null,
              related_event_type: null,
            },
            events: [
              {
                id: 77,
                created_at: "2026-03-19T02:00:00Z",
                event_type: "notification_delivery",
                source: "notification.webhook",
                status: "failed",
                detail: "delivery failed",
                exchange: "binance",
                symbol: "BTC/USDT",
                timeframe: "1h",
                channel: "webhook",
                related_event_type: "worker_cycle",
                correlation_id: "corr-123",
                payload_json: "{\"channel\":\"webhook\"}",
              },
            ],
          }),
        ),
      );
    }

    if (url.includes("/reports/audit")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            event_count: 1,
            filters: {
              event_type: null,
              status: null,
              source: null,
              search: null,
            },
            events: [
              {
                id: 99,
                created_at: "2026-03-19T03:00:00Z",
                event_type: "worker_cycle",
                source: "api.control",
                status: "completed",
                detail: "worker completed",
                exchange: "binance",
                symbol: "BTC/USDT",
                timeframe: "1h",
                channel: null,
                related_event_type: null,
                correlation_id: "corr-789",
                payload_json: "{\"signal_action\":\"buy\"}",
              },
            ],
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
  expect(screen.getByText("Notification Delivery")).toBeInTheDocument();
  expect(screen.getByText("Audit Feed")).toBeInTheDocument();
  expect(screen.getByText("Live recovery")).toBeInTheDocument();
  expect(screen.getByText("Notification delivery")).toBeInTheDocument();
  expect(screen.getByText("Audit feed")).toBeInTheDocument();
  expect(screen.getByText("Daily Rollup")).toBeInTheDocument();
  expect(screen.getByText("Performance Review")).toBeInTheDocument();
  expect(screen.getByText("Strategy Iteration Plan")).toBeInTheDocument();
});
