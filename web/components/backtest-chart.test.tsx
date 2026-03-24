import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import { BacktestChart } from "@/components/backtest-chart";
import type { BacktestControlResponse } from "@/lib/api";

vi.mock("lightweight-charts", () => {
  const series = { setData: vi.fn() };
  return {
    CandlestickSeries: {},
    LineSeries: {},
    createSeriesMarkers: vi.fn(),
    createChart: vi.fn(() => ({
      addSeries: vi.fn(() => series),
      remove: vi.fn(),
      timeScale: vi.fn(() => ({
        fitContent: vi.fn(),
        subscribeVisibleLogicalRangeChange: vi.fn(),
        setVisibleLogicalRange: vi.fn(),
      })),
    })),
  };
});

afterEach(() => {
  cleanup();
});

function buildResult(strategyName: string): BacktestControlResponse {
  return {
    status: "completed",
    detail: "backtest completed",
    notified: false,
    strategy_name: strategyName,
    exchange: "binance",
    symbol: "BTC/USDT",
    timeframe: "1h",
    trading_mode: "SPOT",
    fast_period: 20,
    slow_period: 50,
    starting_equity_input: "10000.00000000",
    candle_count: 120,
    required_candles: 101,
    starting_equity: "10000.00000000",
    ending_equity: "10100.00000000",
    realized_pnl: "100.00000000",
    total_return_pct: "1.00000000",
    benchmark_realized_pnl: "50.00000000",
    benchmark_return_pct: "0.50000000",
    benchmark_excess_return_pct: "0.50000000",
    max_drawdown_pct: "0.25000000",
    total_trades: 2,
    winning_trades: 1,
    losing_trades: 1,
    total_fees_paid: "5.00000000",
    slippage_pct: "0.00050000",
    fee_pct: "0.00100000",
    spread_pct: "0.00000000",
    signal_latency_bars: 0,
    assumption_summary: "",
    allowed_weekdays_utc: [],
    allowed_hours_utc: [],
    max_volume_fill_pct: null,
    allow_partial_fills: false,
    rules: null,
    bb_period: null,
    bb_std_dev: null,
    breakout_period: null,
    atr_period: null,
    atr_breakout_multiplier: null,
    atr_stop_multiplier: null,
    adx_period: 14,
    adx_threshold: "20",
    leverage: null,
    margin_mode: "ISOLATED",
    liquidation_count: 0,
    stop_loss_count: 0,
    executions: [],
    candles: Array.from({ length: 120 }, (_, index) => ({
      open_time: new Date(Date.UTC(2026, 0, 1, index)).toISOString(),
      close_time: new Date(Date.UTC(2026, 0, 1, index + 1)).toISOString(),
      open_price: "100.0",
      high_price: "101.0",
      low_price: "99.0",
      close_price: `${100 + index * 0.5}`,
      volume: "1.0",
    })),
  };
}

test("shows adx legend and pane for ema_adx_trend", () => {
  render(<BacktestChart result={buildResult("ema_adx_trend")} />);

  expect(screen.getByText("ADX (14)")).toBeInTheDocument();
  expect(screen.getByText("ADX Threshold (20)")).toBeInTheDocument();
  expect(screen.getByText("ADX Pane · synced to the price chart")).toBeInTheDocument();
});

test("shows adx legend and pane for ema_adx_trend_volume", () => {
  render(<BacktestChart result={buildResult("ema_adx_trend_volume")} />);

  expect(screen.getByText("ADX (14)")).toBeInTheDocument();
  expect(screen.getByText("ADX Threshold (20)")).toBeInTheDocument();
  expect(screen.getByText("ADX Pane · synced to the price chart")).toBeInTheDocument();
});

test("does not show adx pane for ema_crossover", () => {
  render(<BacktestChart result={buildResult("ema_crossover")} />);

  expect(screen.queryByText("ADX Pane · synced to the price chart")).not.toBeInTheDocument();
});
