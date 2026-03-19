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
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getOperatorConfig,
  getStatus,
  runLiveCancel,
  runLiveHalt,
  runLiveReconcile,
  runMarketSync,
  runWorkerCycle,
  type LiveCancelControlResponse,
  type LiveHaltControlResponse,
  type LiveReconcileControlResponse,
  type MarketSyncControlResponse,
  type OperatorConfigResponse,
  type StatusResponse,
  type WorkerControlResponse,
} from "@/lib/api";
import { formatDecimal, formatTimestamp } from "@/lib/format";

type MarketSyncFormState = {
  symbol: string;
  timeframe: string;
  limit: string;
  backfill: boolean;
};

type CancelIdentifierType = "order_id" | "client_order_id" | "exchange_order_id";

type LiveCancelFormState = {
  identifierType: CancelIdentifierType;
  value: string;
};

const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"];

function RuntimeConfigStrip({
  operatorConfig,
  status,
}: {
  operatorConfig: OperatorConfigResponse;
  status: StatusResponse | undefined;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-5">
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
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Live Posture</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {status?.live_safety_status ?? "n/a"}
        </p>
        <p className="mt-2 text-sm text-slate-400">
          {status?.live_trading_enabled
            ? status.live_trading_halted
              ? "Live enabled, entry halted"
              : "Live enabled, entry open"
            : "Paper-trading-first"}
        </p>
      </div>
      <div className="rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">Control Scope</p>
        <p className="mt-3 text-xl font-semibold tracking-tight text-white">Explicit actions</p>
        <p className="mt-2 text-sm text-slate-300">
          Live controls remain operator-triggered and bounded to current backend policies.
        </p>
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: MarketSyncControlResponse | null }) {
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

function WorkerCycleResultPanel({ result }: { result: WorkerControlResponse | null }) {
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
              Signal {result.signal_action ?? "none"}{" "}
              {result.client_order_id ? `· ${result.client_order_id}` : ""}
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

function LiveHaltResultPanel({ result }: { result: LiveHaltControlResponse | null }) {
  if (!result) {
    return (
      <div className="flex min-h-32 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No live halt action submitted yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-white">{result.detail}</p>
            <p className="mt-2 text-sm text-slate-400">
              Entry state {result.live_trading_halted ? "halted" : "resumed"}
            </p>
          </div>
          <Badge variant={result.live_trading_halted ? "warning" : "success"}>
            {result.status}
          </Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Badge variant={result.changed ? "success" : "neutral"}>
          {result.changed ? "State changed" : "State unchanged"}
        </Badge>
        <Badge variant={result.notified ? "success" : "neutral"}>
          {result.notified ? "Notification sent" : "No notification"}
        </Badge>
      </div>
    </div>
  );
}

function LiveReconcileResultPanel({
  result,
}: {
  result: LiveReconcileControlResponse | null;
}) {
  if (!result) {
    return (
      <div className="flex min-h-32 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No live reconcile run yet.
      </div>
    );
  }

  const variant = result.status === "completed" ? "success" : "danger";

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-white">{result.detail}</p>
            <p className="mt-2 text-sm text-slate-400">
              Filled {result.filled_count} · review required {result.review_required_count}
            </p>
          </div>
          <Badge variant={variant}>{result.status}</Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Badge variant="neutral">Reconciled {result.reconciled_count}</Badge>
        <Badge variant="neutral">Filled {result.filled_count}</Badge>
        <Badge variant="warning">Review {result.review_required_count}</Badge>
        <Badge variant={result.notified ? "success" : "neutral"}>
          {result.notified ? "Notification sent" : "No notification"}
        </Badge>
      </div>
    </div>
  );
}

function LiveCancelResultPanel({ result }: { result: LiveCancelControlResponse | null }) {
  if (!result) {
    return (
      <div className="flex min-h-32 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No live cancel action submitted yet.
      </div>
    );
  }

  const variant = result.status === "completed" ? "success" : "danger";

  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-white">{result.detail}</p>
            <p className="mt-2 text-sm text-slate-400">
              Status {result.order_status ?? "unknown"} · order {result.order_id ?? "n/a"}
            </p>
          </div>
          <Badge variant={variant}>{result.status}</Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        <Badge variant="neutral">Client {result.client_order_id ?? "n/a"}</Badge>
        <Badge variant="neutral">Exchange {result.exchange_order_id ?? "n/a"}</Badge>
        <Badge variant={result.notified ? "success" : "neutral"}>
          {result.notified ? "Notification sent" : "No notification"}
        </Badge>
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
  const [cancelForm, setCancelForm] = useState<LiveCancelFormState>({
    identifierType: "order_id",
    value: "",
  });
  const [hasHydratedDefaults, setHasHydratedDefaults] = useState(false);

  const operatorConfigQuery = useQuery({
    queryKey: ["operator-config"],
    queryFn: getOperatorConfig,
  });

  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: getStatus,
  });

  async function invalidateOperationalQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["status"] }),
      queryClient.invalidateQueries({ queryKey: ["positions"] }),
      queryClient.invalidateQueries({ queryKey: ["trades"] }),
      queryClient.invalidateQueries({ queryKey: ["performance"] }),
    ]);
  }

  const marketSyncMutation = useMutation({
    mutationFn: runMarketSync,
    onSuccess: invalidateOperationalQueries,
  });

  const workerCycleMutation = useMutation({
    mutationFn: runWorkerCycle,
    onSuccess: invalidateOperationalQueries,
  });

  const liveHaltMutation = useMutation({
    mutationFn: runLiveHalt,
    onSuccess: invalidateOperationalQueries,
  });

  const liveReconcileMutation = useMutation({
    mutationFn: runLiveReconcile,
    onSuccess: invalidateOperationalQueries,
  });

  const liveCancelMutation = useMutation({
    mutationFn: runLiveCancel,
    onSuccess: async () => {
      setCancelForm((current) => ({ ...current, value: "" }));
      await invalidateOperationalQueries();
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

  function handleMarketSyncSubmit(event: FormEvent<HTMLFormElement>) {
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

  function handleLiveCancelSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = cancelForm.value.trim();
    if (!trimmed) {
      return;
    }

    if (cancelForm.identifierType === "order_id") {
      const orderId = Number(trimmed);
      if (!Number.isInteger(orderId) || orderId <= 0) {
        return;
      }
      liveCancelMutation.mutate({ order_id: orderId });
      return;
    }

    if (cancelForm.identifierType === "client_order_id") {
      liveCancelMutation.mutate({ client_order_id: trimmed });
      return;
    }

    liveCancelMutation.mutate({ exchange_order_id: trimmed });
  }

  const status = statusQuery.data;

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(18,17,12,0.94),rgba(14,22,27,0.78))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-amber-200/80">
                Feature Live Ops UI
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Market Intake And Recovery Deck
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Run bounded worker and market-data actions, then use explicit live recovery
                controls without moving execution policy into the browser.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="warning">Write actions</Badge>
              <Badge variant="info">Live safety aware</Badge>
              <Badge variant="neutral">API-backed</Badge>
            </div>
          </div>
        </header>

        {operatorConfigQuery.isLoading || statusQuery.isLoading ? (
          <div className="grid gap-4 lg:grid-cols-5">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : operatorConfigQuery.data ? (
          <RuntimeConfigStrip operatorConfig={operatorConfigQuery.data} status={status} />
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
                  This action may execute a paper trade or submit a bounded live order only if the
                  backend strategy, risk checks, and live posture allow it.
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
                    Choose the market slice to fetch, then store only new candles or backfill a
                    wider history window.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-amber-300/10 p-3 text-amber-100">
                  <CandlestickChart className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <form className="space-y-5" onSubmit={handleMarketSyncSubmit}>
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

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Live Recovery Controls</CardTitle>
                  <CardDescription>
                    Explicit reconcile, halt, and cancel actions for live-capable incidents.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-rose-400/10 p-3 text-rose-200">
                  <ShieldAlert className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.08] p-4 text-sm text-rose-100">
                  These controls remain manual and explicit. The browser does not infer
                  identifiers, retry fills, or add cancel heuristics on its own.
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <div className="space-y-4 rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-white">Live Entry Halt</p>
                        <p className="mt-2 text-sm text-slate-400">
                          Persist the current live-entry halt state used by status and worker
                          execution.
                        </p>
                      </div>
                      <Badge variant={status?.live_trading_halted ? "warning" : "success"}>
                        {status?.live_trading_halted ? "Halted" : "Open"}
                      </Badge>
                    </div>

                    {liveHaltMutation.error instanceof Error ? (
                      <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                        {liveHaltMutation.error.message}
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-3">
                      <button
                        className="inline-flex items-center gap-2 rounded-2xl bg-amber-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                        disabled={liveHaltMutation.isPending}
                        onClick={() => liveHaltMutation.mutate({ halted: true })}
                        type="button"
                      >
                        {liveHaltMutation.isPending ? (
                          <RefreshCcw className="h-4 w-4 animate-spin" />
                        ) : (
                          <ShieldAlert className="h-4 w-4" />
                        )}
                        Halt live entry
                      </button>
                      <button
                        className="inline-flex items-center gap-2 rounded-2xl border border-emerald-300/30 bg-emerald-300/10 px-4 py-3 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-300/15 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-slate-700 disabled:text-slate-300"
                        disabled={liveHaltMutation.isPending}
                        onClick={() => liveHaltMutation.mutate({ halted: false })}
                        type="button"
                      >
                        {liveHaltMutation.isPending ? (
                          <RefreshCcw className="h-4 w-4 animate-spin" />
                        ) : (
                          <ShieldCheck className="h-4 w-4" />
                        )}
                        Resume live entry
                      </button>
                    </div>

                    <LiveHaltResultPanel result={liveHaltMutation.data ?? null} />
                  </div>

                  <div className="space-y-4 rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-white">Live Reconcile</p>
                        <p className="mt-2 text-sm text-slate-400">
                          Pull exchange order state into the local runtime before deciding on a
                          follow-up action.
                        </p>
                      </div>
                      <Badge variant="info">
                        Max order {status?.live_max_order_notional ? formatDecimal(status.live_max_order_notional) : "n/a"}
                      </Badge>
                    </div>

                    {liveReconcileMutation.error instanceof Error ? (
                      <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                        {liveReconcileMutation.error.message}
                      </div>
                    ) : null}

                    <button
                      className="inline-flex items-center gap-2 rounded-2xl bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                      disabled={liveReconcileMutation.isPending}
                      onClick={() => liveReconcileMutation.mutate()}
                      type="button"
                    >
                      {liveReconcileMutation.isPending ? (
                        <RefreshCcw className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCcw className="h-4 w-4" />
                      )}
                      Run live reconcile
                    </button>

                    <LiveReconcileResultPanel result={liveReconcileMutation.data ?? null} />
                  </div>
                </div>

                <div className="space-y-4 rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">Manual Live Cancel</p>
                      <p className="mt-2 text-sm text-slate-400">
                        Cancel one live order at a time using exactly one explicit identifier.
                      </p>
                    </div>
                    <Badge variant="warning">Single identifier</Badge>
                  </div>

                  <form className="space-y-4" onSubmit={handleLiveCancelSubmit}>
                    <div className="grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
                      <label className="space-y-2">
                        <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          Identifier Type
                        </span>
                        <select
                          className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                          onChange={(event) =>
                            setCancelForm({
                              identifierType: event.target.value as CancelIdentifierType,
                              value: "",
                            })
                          }
                          value={cancelForm.identifierType}
                        >
                          <option value="order_id">Order ID</option>
                          <option value="client_order_id">Client Order ID</option>
                          <option value="exchange_order_id">Exchange Order ID</option>
                        </select>
                      </label>

                      <label className="space-y-2">
                        <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          Identifier Value
                        </span>
                        <input
                          className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                          inputMode={cancelForm.identifierType === "order_id" ? "numeric" : "text"}
                          onChange={(event) =>
                            setCancelForm((current) => ({
                              ...current,
                              value: event.target.value,
                            }))
                          }
                          placeholder={cancelForm.identifierType === "order_id" ? "123" : "live-order-id"}
                          required
                          value={cancelForm.value}
                        />
                      </label>
                    </div>

                    {liveCancelMutation.error instanceof Error ? (
                      <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                        {liveCancelMutation.error.message}
                      </div>
                    ) : null}

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        className="inline-flex items-center gap-2 rounded-2xl bg-rose-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-rose-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                        disabled={liveCancelMutation.isPending}
                        type="submit"
                      >
                        {liveCancelMutation.isPending ? (
                          <RefreshCcw className="h-4 w-4 animate-spin" />
                        ) : (
                          <XCircle className="h-4 w-4" />
                        )}
                        Cancel live order
                      </button>
                      <p className="text-sm text-slate-400">
                        Cancel requests are explicit and do not guess alternate identifiers.
                      </p>
                    </div>
                  </form>

                  <LiveCancelResultPanel result={liveCancelMutation.data ?? null} />
                </div>
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
                <div className="rounded-2xl border border-amber-300/15 bg-amber-300/5 p-4">
                  <p className="font-medium text-white">Live safety remains backend-owned</p>
                  <p className="mt-2">
                    The browser surfaces current posture and explicit controls, but duplicate-order
                    checks, size limits, and fail-closed behavior remain in Python.
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
