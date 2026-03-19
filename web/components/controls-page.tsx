"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpFromLine,
  CandlestickChart,
  Database,
  Play,
  RefreshCcw,
  Settings2,
} from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getOperatorConfig,
  runMarketSync,
  runWorkerCycle,
  type MarketSyncControlResponse,
  type OperatorConfigResponse,
  type WorkerControlResponse,
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

type MarketSyncFormState = {
  symbol: string;
  timeframe: string;
  limit: string;
  backfill: boolean;
};

const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"];

function RuntimeConfigStrip({
  operatorConfig,
}: {
  operatorConfig: OperatorConfigResponse;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Active Market</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {operatorConfig.symbol}
        </p>
        <p className="mt-2 text-sm text-slate-400">{operatorConfig.exchange.toUpperCase()}</p>
      </div>
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Runtime Frame</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {operatorConfig.timeframe}
        </p>
        <p className="mt-2 text-sm text-slate-400">Source {operatorConfig.source}</p>
      </div>
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Strategy</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {operatorConfig.strategy_name}
        </p>
        <p className="mt-2 text-sm text-slate-400">
          EMA {operatorConfig.fast_period}/{operatorConfig.slow_period}
        </p>
      </div>
      <div className="rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">Sync Scope</p>
        <p className="mt-3 text-xl font-semibold tracking-tight text-white">Per-run override</p>
        <p className="mt-2 text-sm text-slate-300">
          Market Sync can target a different symbol and timeframe without changing persisted
          runtime defaults.
        </p>
      </div>
    </div>
  );
}

function ResultPanel({
  result,
}: {
  result: MarketSyncControlResponse | null;
}) {
  if (!result) {
    return (
      <div className="flex min-h-60 flex-col items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
        <ArrowUpFromLine className="h-6 w-6 text-cyan-200" />
        <p className="mt-4 text-sm font-medium text-white">No sync run yet</p>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          Submit a market sync to inspect fetched candles, stored rows, and the latest closed
          candle timestamp.
        </p>
      </div>
    );
  }

  const resultVariant =
    result.status === "failed" ? "danger" : result.backfill ? "warning" : "success";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Last Result</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
            {result.symbol} {result.timeframe}
          </h3>
          <p className="mt-2 text-sm text-slate-300">{result.detail}</p>
        </div>
        <div className="flex gap-2">
          <Badge variant={resultVariant}>{result.status}</Badge>
          <Badge variant="neutral">{result.backfill ? "Backfill" : "Append"}</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Fetched</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {result.fetched_count}
          </p>
          <p className="mt-2 text-sm text-slate-400">Candles returned from the exchange adapter.</p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Stored</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {result.stored_count}
          </p>
          <p className="mt-2 text-sm text-slate-400">Rows written or upserted into candle storage.</p>
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="info">Limit {result.limit}</Badge>
          <Badge variant="neutral">
            Latest {result.latest_open_time ? formatTimestamp(result.latest_open_time) : "n/a"}
          </Badge>
          <Badge variant={result.notified ? "success" : "neutral"}>
            {result.notified ? "Notification sent" : "No notification"}
          </Badge>
        </div>
      </div>
    </div>
  );
}

export function ControlsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<MarketSyncFormState>({
    symbol: "",
    timeframe: "",
    limit: "300",
    backfill: false,
  });
  const [hasHydratedDefaults, setHasHydratedDefaults] = useState(false);

  const operatorConfigQuery = useQuery({
    queryKey: ["operator-config"],
    queryFn: getOperatorConfig,
  });

  const marketSyncMutation = useMutation({
    mutationFn: runMarketSync,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["status"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] }),
        queryClient.invalidateQueries({ queryKey: ["trades"] }),
        queryClient.invalidateQueries({ queryKey: ["performance"] }),
      ]);
    },
  });

  const workerCycleMutation = useMutation({
    mutationFn: runWorkerCycle,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["status"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] }),
        queryClient.invalidateQueries({ queryKey: ["trades"] }),
        queryClient.invalidateQueries({ queryKey: ["performance"] }),
      ]);
    },
  });

  useEffect(() => {
    if (!operatorConfigQuery.data || hasHydratedDefaults) {
      return;
    }

    setForm((current) => ({
      ...current,
      symbol: operatorConfigQuery.data.symbol,
      timeframe: operatorConfigQuery.data.timeframe,
    }));
    setHasHydratedDefaults(true);
  }, [hasHydratedDefaults, operatorConfigQuery.data]);

  function updateField<Key extends keyof MarketSyncFormState>(
    key: Key,
    value: MarketSyncFormState[Key],
  ) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedLimit = Number(form.limit);
    if (!Number.isFinite(normalizedLimit) || normalizedLimit <= 0) {
      return;
    }

    marketSyncMutation.mutate({
      symbol: form.symbol.trim(),
      timeframe: form.timeframe.trim(),
      limit: normalizedLimit,
      backfill: form.backfill,
    });
  }

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(18,17,12,0.94),rgba(14,22,27,0.78))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-amber-200/80">
                Feature Operator Market Sync Controls
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Market Intake Control Deck
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Run targeted candle sync jobs for a selected market window without reusing the old
                backend console or silently mutating runtime defaults.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="warning">Write action</Badge>
              <Badge variant="info">Explicit market selection</Badge>
              <Badge variant="neutral">Append or backfill</Badge>
            </div>
          </div>
        </header>

        {operatorConfigQuery.isLoading ? (
          <div className="grid gap-4 lg:grid-cols-4">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : operatorConfigQuery.data ? (
          <RuntimeConfigStrip operatorConfig={operatorConfigQuery.data} />
        ) : (
          <div className="rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 py-10 text-center">
            <AlertTriangle className="mx-auto h-6 w-6 text-amber-300" />
            <p className="mt-4 text-sm font-medium text-white">Runtime defaults unavailable</p>
            <p className="mt-2 text-sm text-slate-400">
              The controls page could not load current operator defaults.
            </p>
          </div>
        )}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(380px,0.9fr)]">
          <div className="space-y-5">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Run Worker Cycle</CardTitle>
                  <CardDescription>
                    Trigger one bounded worker pass using the current runtime defaults and stored
                    candles.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-emerald-300/10 p-3 text-emerald-100">
                  <Play className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
                  This action may execute a paper trade if the current strategy emits a valid signal
                  and risk checks pass.
                </div>

                {workerCycleMutation.error instanceof Error ? (
                  <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                    {workerCycleMutation.error.message}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-2xl bg-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                    disabled={workerCycleMutation.isPending}
                    onClick={() => workerCycleMutation.mutate()}
                    type="button"
                  >
                    {workerCycleMutation.isPending ? (
                      <RefreshCcw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    {workerCycleMutation.isPending ? "Running worker" : "Run worker cycle"}
                  </button>
                  <p className="text-sm text-slate-400">
                    Uses the persisted runtime defaults currently shown above.
                  </p>
                </div>

                <WorkerCycleResultPanel result={workerCycleMutation.data ?? null} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Run Market Sync</CardTitle>
                  <CardDescription>
                    Choose the market slice to fetch, then store only new candles or backfill a wider
                    history window.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-amber-300/10 p-3 text-amber-100">
                  <CandlestickChart className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Symbol
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("symbol", event.target.value)}
                      placeholder="BTC/USDT"
                      required
                      value={form.symbol}
                    />
                  </label>

                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Timeframe
                    </span>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("timeframe", event.target.value)}
                      value={form.timeframe}
                    >
                      <option disabled value="">
                        Select timeframe
                      </option>
                      {timeframeOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Candle Limit
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      max={1000}
                      min={1}
                      onChange={(event) => updateField("limit", event.target.value)}
                      required
                      type="number"
                      value={form.limit}
                    />
                  </label>

                  <div className="rounded-[1.6rem] border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-1 rounded-xl bg-white/5 p-2 text-slate-200">
                        <Database className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-white">Backfill mode</p>
                            <p className="mt-1 text-sm text-slate-400">
                              Append stores only newer candles. Backfill upserts the full fetched
                              window to fill older gaps too.
                            </p>
                          </div>
                          <label className="inline-flex cursor-pointer items-center gap-2">
                            <input
                              checked={form.backfill}
                              className="h-4 w-4 rounded border-white/20 bg-[#09121a] text-cyan-300 focus:ring-cyan-300/30"
                              onChange={(event) => updateField("backfill", event.target.checked)}
                              type="checkbox"
                            />
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {marketSyncMutation.error instanceof Error ? (
                  <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                    {marketSyncMutation.error.message}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                    disabled={marketSyncMutation.isPending}
                    type="submit"
                  >
                    {marketSyncMutation.isPending ? (
                      <RefreshCcw className="h-4 w-4 animate-spin" />
                    ) : (
                      <ArrowUpFromLine className="h-4 w-4" />
                    )}
                    {marketSyncMutation.isPending ? "Syncing candles" : "Run market sync"}
                  </button>
                  <p className="text-sm text-slate-400">
                    This fetches candle data only. It does not place orders or run the worker.
                  </p>
                </div>
                </form>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Operator Guidance</CardTitle>
                  <CardDescription>
                    Keep the sync action predictable and separate from trading decisions.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
                  <Settings2 className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Append</p>
                  <p className="mt-2">
                    Use the default append mode for normal updates. The sync targets the newest
                    candles and avoids re-importing an already stored range.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Backfill</p>
                  <p className="mt-2">
                    Use backfill when you need deeper history for replay analysis or when a market
                    gap should be filled explicitly.
                  </p>
                </div>
                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/5 p-4">
                  <p className="font-medium text-white">Runtime defaults stay unchanged</p>
                  <p className="mt-2">
                    This form overrides market inputs for the sync run only. Change operator
                    defaults separately if you want the worker and status surfaces to switch too.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Last Sync Outcome</CardTitle>
                  <CardDescription>
                    Result details from the most recent sync submitted from this UI session.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                  <Database className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent>
                <ResultPanel result={marketSyncMutation.data ?? null} />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </OperatorShell>
  );
}

function WorkerCycleResultPanel({
  result,
}: {
  result: WorkerControlResponse | null;
}) {
  if (!result) {
    return (
      <div className="flex min-h-40 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No worker-cycle run yet.
      </div>
    );
  }

  const variant =
    result.status === "executed"
      ? "success"
      : result.status === "failed"
        ? "danger"
        : result.status === "skipped"
          ? "warning"
          : "info";

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-white">{result.detail}</p>
            <p className="mt-2 text-sm text-slate-400">
              Signal {result.signal_action ?? "none"} {result.client_order_id ? `· ${result.client_order_id}` : ""}
            </p>
          </div>
          <Badge variant={variant}>{result.status}</Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Badge variant="neutral">Order {result.order_id ?? "n/a"}</Badge>
        <Badge variant="neutral">Trade {result.trade_id ?? "n/a"}</Badge>
        <Badge variant={result.notified ? "success" : "neutral"}>
          {result.notified ? "Notification sent" : "No notification"}
        </Badge>
      </div>
    </div>
  );
}
