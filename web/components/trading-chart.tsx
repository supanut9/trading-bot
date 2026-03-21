"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ISeriesApi, SeriesMarker, Time } from "lightweight-charts";
import { TradeResponse } from "@/lib/api";

type ChartProps = {
  symbol: string;
  timeframe: string;
  trades?: TradeResponse[];
};

export function TradingChart({ symbol, timeframe, trades = [] }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
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
      autoSize: true, // Requires lw-charts 4.x/5.x built-in autosize support if it works, else resize observer
    });

    chartRef.current = chart;

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#10b981", // emerald-500
      downColor: "#ef4444", // red-500
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    seriesRef.current = candlestickSeries;

    // 2. Load Initial Data
    let ws: WebSocket | null = null;
    let isSubscribed = true;

    async function loadData() {
      try {
        const response = await fetch(
          `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=${binanceTimeframe}&limit=500`
        );
        if (!response.ok) throw new Error("Failed to fetch historical candles");
        const json = await response.json();

        // format: [OpenTime, Open, High, Low, Close, Volume, CloseTime...]
        const data = json.map((kline: any) => ({
          time: (kline[0] / 1000) as Time,
          open: parseFloat(kline[1]),
          high: parseFloat(kline[2]),
          low: parseFloat(kline[3]),
          close: parseFloat(kline[4]),
        }));

        if (isSubscribed) {
          candlestickSeries.setData(data);

          // 3. Mount WebSocket for Live Candle Updates
          ws = new WebSocket(
            `wss://stream.binance.com:9443/ws/${binanceSymbol.toLowerCase()}@kline_${binanceTimeframe}`
          );

          ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            const kline = message.k;
            const liveCandle = {
              time: (kline.t / 1000) as Time,
              open: parseFloat(kline.o),
              high: parseFloat(kline.h),
              low: parseFloat(kline.l),
              close: parseFloat(kline.c),
            };
            candlestickSeries.update(liveCandle);
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
  }, [symbol, timeframe]);

  // 4. Update the markers whenever trades change
  useEffect(() => {
    if (!seriesRef.current || !trades) return;

    // Convert trades to SeriesMarkers
    // We sort they by time first
    const markers: SeriesMarker<Time>[] = trades
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      .map((trade) => {
        const isBuy = trade.side.toLowerCase() === "buy";
        return {
          time: (new Date(trade.created_at).getTime() / 1000) as Time,
          position: isBuy ? "belowBar" : "aboveBar",
          color: isBuy ? "#10b981" : "#ef4444", // emerald vs red
          shape: isBuy ? "arrowUp" : "arrowDown",
          text: `${isBuy ? "BUY" : "SELL"} @ ${trade.price}`,
        };
      });

    seriesRef.current.setMarkers(markers);
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
