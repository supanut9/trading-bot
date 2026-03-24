"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type LineData,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import type { BacktestControlResponse } from "@/lib/api";

type CandleData = {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
};

const timeToSeconds = (isoStr: string) =>
  Math.floor(new Date(isoStr).getTime() / 1000) as Time;

function calculateEma(
  closes: number[],
  period: number,
): { index: number; value: number }[] {
  const multiplier = 2 / (period + 1);
  let ema = closes.slice(0, period).reduce((s, v) => s + v, 0) / period;
  const result: { index: number; value: number }[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) continue;
    if (i === period - 1) {
      result.push({ index: i, value: ema });
      continue;
    }
    ema = (closes[i] - ema) * multiplier + ema;
    result.push({ index: i, value: ema });
  }
  return result;
}

function calculateSma(closes: number[], period: number): (number | null)[] {
  return closes.map((_, i) => {
    if (i < period - 1) return null;
    return closes.slice(i - period + 1, i + 1).reduce((s, v) => s + v, 0) / period;
  });
}

function calculateBollinger(closes: number[], period: number, stdDevMultiplier: number) {
  const smas = calculateSma(closes, period);
  return smas.map((sma, i) => {
    if (sma === null) return null;
    const slice = closes.slice(i - period + 1, i + 1);
    const variance = slice.reduce((s, v) => s + (v - sma) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    return { upper: sma + stdDevMultiplier * std, middle: sma, lower: sma - stdDevMultiplier * std };
  });
}

function calculateAdx(
  highs: number[],
  lows: number[],
  closes: number[],
  period: number,
): { index: number; value: number }[] {
  const minBars = 2 * period + 1;
  if (highs.length < minBars || lows.length < minBars || closes.length < minBars) {
    return [];
  }

  const trueRanges: number[] = [];
  const plusDm: number[] = [];
  const minusDm: number[] = [];

  for (let index = 1; index < highs.length; index += 1) {
    const upMove = highs[index] - highs[index - 1];
    const downMove = lows[index - 1] - lows[index];
    plusDm.push(upMove > downMove && upMove > 0 ? upMove : 0);
    minusDm.push(downMove > upMove && downMove > 0 ? downMove : 0);
    trueRanges.push(
      Math.max(
        highs[index] - lows[index],
        Math.abs(highs[index] - closes[index - 1]),
        Math.abs(lows[index] - closes[index - 1]),
      ),
    );
  }

  let atr = trueRanges.slice(0, period).reduce((sum, value) => sum + value, 0);
  let plus = plusDm.slice(0, period).reduce((sum, value) => sum + value, 0);
  let minus = minusDm.slice(0, period).reduce((sum, value) => sum + value, 0);

  const dxValues: { index: number; value: number }[] = [];
  for (let index = period; index < trueRanges.length; index += 1) {
    if (index > period) {
      atr = atr - atr / period + trueRanges[index];
      plus = plus - plus / period + plusDm[index];
      minus = minus - minus / period + minusDm[index];
    }
    if (atr === 0) {
      dxValues.push({ index: index + 1, value: 0 });
      continue;
    }
    const plusDi = (plus / atr) * 100;
    const minusDi = (minus / atr) * 100;
    const denominator = plusDi + minusDi;
    const dx = denominator === 0 ? 0 : (Math.abs(plusDi - minusDi) / denominator) * 100;
    dxValues.push({ index: index + 1, value: dx });
  }

  if (dxValues.length < period) {
    return [];
  }

  let adx = dxValues.slice(0, period).reduce((sum, item) => sum + item.value, 0) / period;
  const series: { index: number; value: number }[] = [
    { index: dxValues[period - 1].index, value: adx },
  ];
  for (let index = period; index < dxValues.length; index += 1) {
    adx = ((adx * (period - 1)) + dxValues[index].value) / period;
    series.push({ index: dxValues[index].index, value: adx });
  }
  return series;
}

export function BacktestChart({ result }: { result: BacktestControlResponse }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const adxContainerRef = useRef<HTMLDivElement>(null);
  const strategy = result.strategy_name;
  const hasAdxPane =
    strategy === "ema_adx_trend" || strategy === "ema_adx_trend_volume";

  useEffect(() => {
    if (!containerRef.current || result.candles.length === 0) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "#334155" },
      timeScale: {
        borderColor: "#334155",
        timeVisible: true,
        visible: !hasAdxPane,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    const candleData: CandleData[] = result.candles.map((c) => ({
      time: timeToSeconds(c.open_time),
      open: Number(c.open_price),
      high: Number(c.high_price),
      low: Number(c.low_price),
      close: Number(c.close_price),
    }));
    candleSeries.setData(candleData);

    const markers: SeriesMarker<Time>[] = result.executions
      .filter((e) => e.candle_open_time)
      .map((e) => ({
        time: timeToSeconds(e.candle_open_time),
        position: e.action === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
        color: e.action === "buy" ? "#22c55e" : "#ef4444",
        shape: e.action === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
        text: e.action === "buy" ? "B" : "S",
        size: 1,
      }));
    createSeriesMarkers(candleSeries, markers);

    const closes = result.candles.map((c) => Number(c.close_price));
    const times = result.candles.map((c) => timeToSeconds(c.open_time));

    if (
      strategy === "ema_crossover" ||
      strategy === "ema_adx_trend" ||
      strategy === "ema_adx_trend_volume" ||
      strategy === "macd_crossover" ||
      strategy === "rule_builder"
    ) {
      const fastP = result.fast_period ?? 20;
      const slowP = result.slow_period ?? 50;
      const fastEma = calculateEma(closes, fastP);
      const slowEma = calculateEma(closes, slowP);

      const fastSeries = chart.addSeries(LineSeries, {
        color: "#38bdf8",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      fastSeries.setData(fastEma.map(({ index, value }) => ({ time: times[index], value })));

      const slowSeries = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      slowSeries.setData(slowEma.map(({ index, value }) => ({ time: times[index], value })));

      if (strategy === "ema_adx_trend" || strategy === "ema_adx_trend_volume") {
        const trendEma = calculateEma(closes, 100);
        const trendSeries = chart.addSeries(LineSeries, {
          color: "#34d399",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        trendSeries.setData(trendEma.map(({ index, value }) => ({ time: times[index], value })));
      }
    }

    if (strategy === "mean_reversion_bollinger") {
      const period = result.bb_period ?? 20;
      const stdMul = Number(result.bb_std_dev ?? "2");
      const bands = calculateBollinger(closes, period, stdMul);

      const upperSeries = chart.addSeries(LineSeries, {
        color: "#fb7185",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: 2,
      });
      const midSeries = chart.addSeries(LineSeries, {
        color: "#94a3b8",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: 2,
      });
      const lowerSeries = chart.addSeries(LineSeries, {
        color: "#34d399",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: 2,
      });

      const upperData: LineData<Time>[] = [];
      const midData: LineData<Time>[] = [];
      const lowerData: LineData<Time>[] = [];
      bands.forEach((b, i) => {
        if (!b) return;
        upperData.push({ time: times[i], value: b.upper });
        midData.push({ time: times[i], value: b.middle });
        lowerData.push({ time: times[i], value: b.lower });
      });
      upperSeries.setData(upperData);
      midSeries.setData(midData);
      lowerSeries.setData(lowerData);
    }

    if (strategy === "breakout_atr") {
      const period = result.breakout_period ?? 20;
      const channelData = result.candles.map((_, i) => {
        if (i < period - 1) return null;
        const slice = result.candles.slice(i - period + 1, i + 1);
        return {
          upper: Math.max(...slice.map((c) => Number(c.high_price))),
          lower: Math.min(...slice.map((c) => Number(c.low_price))),
        };
      });

      const upperSeries = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: 2,
      });
      const lowerSeries = chart.addSeries(LineSeries, {
        color: "#fb7185",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        lineStyle: 2,
      });
      const upperData: LineData<Time>[] = [];
      const lowerData: LineData<Time>[] = [];
      channelData.forEach((b, i) => {
        if (!b) return;
        upperData.push({ time: times[i], value: b.upper });
        lowerData.push({ time: times[i], value: b.lower });
      });
      upperSeries.setData(upperData);
      lowerSeries.setData(lowerData);
    }

    let adxChart: ReturnType<typeof createChart> | null = null;
    if (hasAdxPane && adxContainerRef.current) {
      const highs = result.candles.map((c) => Number(c.high_price));
      const lows = result.candles.map((c) => Number(c.low_price));
      const adxPeriod = result.adx_period ?? 14;
      const adxThreshold = Number(result.adx_threshold ?? "20");
      const adxSeriesData = calculateAdx(highs, lows, closes, adxPeriod);

      adxChart = createChart(adxContainerRef.current, {
        autoSize: true,
        height: 140,
        layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        crosshair: { mode: 1 },
        rightPriceScale: {
          borderColor: "#334155",
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: { borderColor: "#334155", timeVisible: true, visible: true },
      });

      const adxLineSeries = adxChart.addSeries(LineSeries, {
        color: "#a78bfa",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      adxLineSeries.setData(
        adxSeriesData.map(({ index, value }) => ({ time: times[index], value })),
      );

      const thresholdSeries = adxChart.addSeries(LineSeries, {
        color: "#f97316",
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      thresholdSeries.setData(times.map((time) => ({ time, value: adxThreshold })));

      let syncingFromMain = false;
      let syncingFromAdx = false;
      chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (syncingFromAdx || range === null) {
          return;
        }
        syncingFromMain = true;
        adxChart?.timeScale().setVisibleLogicalRange(range);
        syncingFromMain = false;
      });
      adxChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (syncingFromMain || range === null) {
          return;
        }
        syncingFromAdx = true;
        chart.timeScale().setVisibleLogicalRange(range);
        syncingFromAdx = false;
      });
      adxChart.timeScale().fitContent();
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      adxChart?.remove();
    };
  }, [hasAdxPane, result, strategy]);

  if (result.candles.length === 0) {
    return (
      <div className="flex min-h-56 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No candle data available for this backtest.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-300">
            Price Chart · {result.symbol} · {result.timeframe}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {result.candles.length} candles · {result.executions.length} executions
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-slate-400">
          {(strategy === "ema_crossover" ||
            strategy === "ema_adx_trend" ||
            strategy === "ema_adx_trend_volume" ||
            strategy === "macd_crossover") && (
            <>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-sky-400" />
                Fast EMA ({result.fast_period ?? 20})
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-amber-400" />
                Slow EMA ({result.slow_period ?? 50})
              </span>
              {strategy === "ema_adx_trend" || strategy === "ema_adx_trend_volume" ? (
                <>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-4 rounded bg-emerald-400" />
                    Trend EMA (100)
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-4 rounded bg-violet-400" />
                    ADX ({result.adx_period ?? 14})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-4 rounded bg-orange-400" />
                    ADX Threshold ({result.adx_threshold ?? "20"})
                  </span>
                </>
              ) : null}
            </>
          )}
          {strategy === "rule_builder" && result.fast_period && result.slow_period && (
            <>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-sky-400" />
                Fast EMA ({result.fast_period})
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-amber-400" />
                Slow EMA ({result.slow_period})
              </span>
            </>
          )}
          {strategy === "mean_reversion_bollinger" && (
            <>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-rose-400" />
                Upper BB
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-slate-300" />
                SMA
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-emerald-400" />
                Lower BB
              </span>
            </>
          )}
          {strategy === "breakout_atr" && (
            <>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-amber-400" />
                Resistance
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-1.5 w-4 rounded bg-rose-400" />
                Support
              </span>
            </>
          )}
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full bg-emerald-400" />
            Buy
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full bg-rose-400" />
            Sell
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="h-[420px] w-full overflow-hidden rounded-[1.8rem] border border-white/10 bg-[#080c11]"
      />
      {hasAdxPane ? (
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500">
            ADX Pane · synced to the price chart
          </p>
          <div
            ref={adxContainerRef}
            className="h-[140px] w-full overflow-hidden rounded-[1.4rem] border border-white/10 bg-[#080c11]"
          />
        </div>
      ) : null}
    </div>
  );
}
