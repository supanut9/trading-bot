"use client";

import { useEffect, useRef, useState } from "react";

export type TickerState =
  | { status: "connecting" }
  | { status: "live"; price: string; change24hPct: string }
  | { status: "error"; message: string };

/**
 * Connects to the Binance miniTicker WebSocket stream for a given symbol.
 * symbol should be in "BTC/USDT" format — it is normalised to "btcusdt" internally.
 * Automatically reconnects on unexpected close.
 */
export function useBinanceTicker(symbol: string | undefined): TickerState {
  const [state, setState] = useState<TickerState>({ status: "connecting" });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!symbol) return;

    const streamSymbol = symbol.replace("/", "").toLowerCase();
    const url = `wss://stream.binance.com:9443/ws/${streamSymbol}@miniTicker`;

    let active = true;

    function connect() {
      if (!active) return;

      setState({ status: "connecting" });
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as {
            c: string; // close price
            o: string; // open price (24h)
          };
          const close = parseFloat(data.c);
          const open = parseFloat(data.o);
          const changePct = open !== 0 ? ((close - open) / open) * 100 : 0;
          setState({
            status: "live",
            price: data.c,
            change24hPct: changePct.toFixed(2),
          });
        } catch {
          // ignore malformed frames
        }
      };

      ws.onerror = () => {
        setState({ status: "error", message: "WebSocket error" });
      };

      ws.onclose = (event) => {
        if (!active) return;
        if (event.wasClean) {
          setState({ status: "error", message: "Stream closed" });
        } else {
          // unexpected close — reconnect after 2s
          reconnectTimerRef.current = setTimeout(connect, 2000);
        }
      };
    }

    connect();

    return () => {
      active = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [symbol]);

  return state;
}
