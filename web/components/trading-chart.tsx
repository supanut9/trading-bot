"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  SeriesMarker,
  Time,
  type CandlestickData,
  type LineData,
} from "lightweight-charts";
import { TradeResponse } from "@/lib/api";

type ChartProps = {
  symbol: string;
  timeframe: string;
  trades?: TradeResponse[];
  fast_period?: number;
  slow_period?: number;
};

type CandleData = CandlestickData<Time>;
type BinanceKline = [number, string, string, string, string, ...unknown[]];
type BinanceKlineMessage = {
  k: {
    t: number;
    o: string;
    h: string;
    l: string;
    c: string;
  };
};

const TZ_OFFSET_SECONDS = 7 * 3600; // UTC+7 Thailand

function calculateEma(data: CandleData[], period: number): LineData<Time>[] {
  const multiplier = 2 / (period + 1);
  let ema =
    data.slice(0, period).reduce((sum, candle) => sum + candle.close, 0) / period;

  const emaData: LineData<Time>[] = [];

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      // Not enough data to calculate EMA, skip
      continue;
    }
    if (i === period - 1) {
      // First EMA is the SMA
      emaData.push({ time: data[i].time, value: ema });
    } else {
      ema = (data[i].close - ema) * multiplier + ema;
      emaData.push({ time: data[i].time, value: ema });
    }
  }

  return emaData;
}

export function TradingChart({
  symbol,
  timeframe,
  trades = [],
  fast_period,
  slow_period,
}: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markerSeriesRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const fastEmaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const slowEmaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const chartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Remove any slash for the binance API format (e.g. BTC/USDT -> BTCUSDT)
    const binanceSymbol = symbol.toUpperCase().replace("/", "");

    // Map standard timeframes to Binance format
    const binanceTimeframe = timeframe.replace("m", "m").replace("h", "h").replace("d", "d");

    // 1. Initialize the Chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8", // slate-400
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.05)" },
        horzLines: { color: "rgba(255, 255, 255, 0.05)" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      autoSize: false,
    });

    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981", // emerald-500
      downColor: "#ef4444", // red-500
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    seriesRef.current = candlestickSeries;
    markerSeriesRef.current = createSeriesMarkers(candlestickSeries, []);

    // Add EMA line series if periods are provided
    if (fast_period) {
      fastEmaSeriesRef.current = chart.addSeries(LineSeries, {
        color: "#38bdf8", // sky-400
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (slow_period) {
      slowEmaSeriesRef.current = chart.addSeries(LineSeries, {
        color: "#f87171", // red-400
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // 2. Load Initial Data
    let ws: WebSocket | null = null;
    let isSubscribed = true;
    let historicData: CandleData[] = [];

    async function loadData() {
      try {
        const response = await fetch(
          `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=${binanceTimeframe}&limit=500`
        );
        if (!response.ok) throw new Error("Failed to fetch historical candles");
        const json = (await response.json()) as BinanceKline[];

        // format: [OpenTime, Open, High, Low, Close, Volume, CloseTime...]
        historicData = json.map((kline) => ({
          time: (kline[0] / 1000 + TZ_OFFSET_SECONDS) as Time,
          open: parseFloat(kline[1]),
          high: parseFloat(kline[2]),
          low: parseFloat(kline[3]),
          close: parseFloat(kline[4]),
        }));

        if (isSubscribed) {
          candlestickSeries.setData(historicData);

          // Calculate and set EMA data
          if (fast_period && fastEmaSeriesRef.current) {
            const fastEmaData = calculateEma(historicData, fast_period);
            fastEmaSeriesRef.current.setData(fastEmaData);
          }
          if (slow_period && slowEmaSeriesRef.current) {
            const slowEmaData = calculateEma(historicData, slow_period);
            slowEmaSeriesRef.current.setData(slowEmaData);
          }

          // 3. Mount WebSocket for Live Candle Updates
          ws = new WebSocket(
            `wss://stream.binance.com:9443/ws/${binanceSymbol.toLowerCase()}@kline_${binanceTimeframe}`
          );

          ws.onmessage = (event) => {
            const message = JSON.parse(event.data) as BinanceKlineMessage;
            const kline = message.k;
            const liveCandle: CandleData = {
              time: (kline.t / 1000 + TZ_OFFSET_SECONDS) as Time,
              open: parseFloat(kline.o),
              high: parseFloat(kline.h),
              low: parseFloat(kline.l),
              close: parseFloat(kline.c),
            };
            candlestickSeries.update(liveCandle);

            // Update EMAs with the new candle
            if (fast_period && fastEmaSeriesRef.current) {
              const lastFastEma =
                fastEmaSeriesRef.current.data().at(-1) as LineData<Time> | undefined;
              if (lastFastEma) {
                const multiplier = 2 / (fast_period + 1);
                const newEmaValue = (liveCandle.close - lastFastEma.value) * multiplier + lastFastEma.value;
                fastEmaSeriesRef.current.update({
                  time: liveCandle.time,
                  value: newEmaValue,
                });
              }
            }
            if (slow_period && slowEmaSeriesRef.current) {
              const lastSlowEma =
                slowEmaSeriesRef.current.data().at(-1) as LineData<Time> | undefined;
              if (lastSlowEma) {
                const multiplier = 2 / (slow_period + 1);
                const newEmaValue =
                  (liveCandle.close - lastSlowEma.value) * multiplier + lastSlowEma.value;
                slowEmaSeriesRef.current.update({
                  time: liveCandle.time,
                  value: newEmaValue,
                });
              }
            }
          };
        }
      } catch (err) {
        if (isSubscribed) {
          setError(err instanceof Error ? err.message : "Unknown error loading chart");
        }
      }
    }

    loadData();

    // Resize observer to keep chart responsive
    const resizeObserver = new ResizeObserver((entries) => {
      if (chartContainerRef.current && entries.length > 0) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartContainerRef.current);

    return () => {
      isSubscribed = false;
      resizeObserver.disconnect();
      if (ws) ws.close();
      chart.remove();
    };
  }, [symbol, timeframe, fast_period, slow_period]);

  // 4. Update the markers whenever trades change
  useEffect(() => {
    if (!markerSeriesRef.current || !trades) return;

    // Convert trades to SeriesMarkers
    // We sort they by time first
    const markers: SeriesMarker<Time>[] = trades
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .map((trade) => {
        const isBuy = trade.side.toLowerCase() === "buy";
        return {
          time: (new Date(trade.created_at).getTime() / 1000 + TZ_OFFSET_SECONDS) as Time,
          position: isBuy ? "belowBar" : "aboveBar",
          color: isBuy ? "#10b981" : "#ef4444", // emerald vs red
          shape: isBuy ? "arrowUp" : "arrowDown",
          text: `${isBuy ? "BUY" : "SELL"} @ ${trade.price}`,
        };
      });

    markerSeriesRef.current.setMarkers(markers);
  }, [trades]);

  if (error) {
    return (
      <div className="flex h-96 w-full items-center justify-center rounded-2xl border border-dashed border-rose-500/20 bg-rose-500/5 text-sm text-rose-300">
        {error}
      </div>
    );
  }

  return <div ref={chartContainerRef} className="h-[400px] w-full" />;
}
