"use client";

import { startTransition, useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCcw, Save, Settings2, Waves } from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  getOperatorConfig,
  updateOperatorConfig,
  type OperatorConfigRequest,
  type OperatorConfigResponse,
} from "@/lib/api";
import { describeRuntimeStrategy, runtimeStrategyCatalog } from "@/lib/strategy-catalog";

type RuntimeFormState = {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  fast_period: string;
  slow_period: string;
  trading_mode: string;
};

const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"];
const tradingModeOptions = ["SPOT", "FUTURES"];

function SummaryStrip({
  config,
}: {
  config: OperatorConfigResponse;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Strategy</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {config.strategy_name}
        </p>
        <p className="mt-2 text-sm text-slate-400">Persisted operator default</p>
      </div>
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Market</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">{config.symbol}</p>
        <p className="mt-2 text-sm text-slate-400">{config.trading_mode} mode</p>
      </div>
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Timeframe</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {config.timeframe}
        </p>
        <p className="mt-2 text-sm text-slate-400">{config.exchange.toUpperCase()}</p>
      </div>
      <div className="rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">EMA Window</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {config.fast_period}/{config.slow_period}
        </p>
        <p className="mt-2 text-sm text-slate-300">
          Worker, status, and default backtest behavior resolve these values.
        </p>
      </div>
    </div>
  );
}

export function RuntimePage() {
  const [form, setForm] = useState<RuntimeFormState>({
    strategy_name: "ema_crossover",
    symbol: "",
    timeframe: "",
    fast_period: "",
    slow_period: "",
    trading_mode: "SPOT",
  });
  const [hasHydratedDefaults, setHasHydratedDefaults] = useState(false);

  const operatorConfigQuery = useQuery({
    queryKey: ["operator-config"],
    queryFn: getOperatorConfig,
  });

  const updateMutation = useMutation({
    mutationFn: updateOperatorConfig,
  });

  useEffect(() => {
    if (!operatorConfigQuery.data || hasHydratedDefaults) {
      return;
    }

    startTransition(() => {
      setForm({
        strategy_name: operatorConfigQuery.data.strategy_name,
        symbol: operatorConfigQuery.data.symbol,
        timeframe: operatorConfigQuery.data.timeframe,
        fast_period: String(operatorConfigQuery.data.fast_period),
        slow_period: String(operatorConfigQuery.data.slow_period),
        trading_mode: operatorConfigQuery.data.trading_mode,
      });
      setHasHydratedDefaults(true);
    });
  }, [hasHydratedDefaults, operatorConfigQuery.data]);

  function updateField<Key extends keyof RuntimeFormState>(key: Key, value: RuntimeFormState[Key]) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: OperatorConfigRequest = {
      strategy_name: form.strategy_name,
      symbol: form.symbol.trim(),
      timeframe: form.timeframe,
      fast_period: Number(form.fast_period),
      slow_period: Number(form.slow_period),
      trading_mode: form.trading_mode,
    };
    updateMutation.mutate(payload);
  }

  const currentConfig = updateMutation.data ?? operatorConfigQuery.data;
  const selectedStrategyDescription = describeRuntimeStrategy(form.strategy_name);

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(10,13,22,0.94),rgba(13,21,34,0.82))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-sky-200/80">
                Feature Operator Runtime Config UI
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Runtime Defaults Deck
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Persist the paper-runtime defaults used by status, worker cycles, and default
                backtest runs without touching deployment-time env files.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="info">Persisted defaults</Badge>
              <Badge variant="neutral">Paper runtime</Badge>
              <Badge variant="success">API-backed</Badge>
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
        ) : currentConfig ? (
          <SummaryStrip config={currentConfig} />
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Update Runtime Defaults</CardTitle>
                <CardDescription>
                  These values define the effective paper-runtime market and EMA periods unless a
                  more specific control request overrides them.
                </CardDescription>
              </div>
              <div className="rounded-2xl bg-sky-300/10 p-3 text-sky-100">
                <Settings2 className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Strategy
                    </span>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("strategy_name", event.target.value)}
                      value={form.strategy_name}
                    >
                      {runtimeStrategyCatalog.map((strategy) => (
                        <option key={strategy.name} value={strategy.name}>
                          {strategy.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Trading Mode
                    </span>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("trading_mode", event.target.value)}
                      value={form.trading_mode}
                    >
                      {tradingModeOptions.map((option) => (
                        <option key={option} value={option}>
                          {option} Mode
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Symbol
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("symbol", event.target.value)}
                      required
                      value={form.symbol}
                    />
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Timeframe
                    </span>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) => updateField("timeframe", event.target.value)}
                      value={form.timeframe}
                    >
                      {timeframeOptions.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      {form.strategy_name === "ema_crossover" || form.strategy_name === "ema_adx_trend" || form.strategy_name === "rule_builder" ? "Fast EMA" :
                       form.strategy_name === "macd_crossover" ? "MACD Fast" :
                       form.strategy_name === "mean_reversion_bollinger" ? "MA Window" :
                       form.strategy_name === "rsi_momentum" ? "RSI Period" :
                       form.strategy_name === "breakout_atr" ? "Breakout Window" : "Fast Period"}
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      min={1}
                      onChange={(event) => updateField("fast_period", event.target.value)}
                      required
                      type="number"
                      value={form.fast_period}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      {form.strategy_name === "ema_crossover" || form.strategy_name === "ema_adx_trend" || form.strategy_name === "rule_builder" ? "Slow EMA" :
                       form.strategy_name === "macd_crossover" ? "MACD Slow" :
                       form.strategy_name === "mean_reversion_bollinger" ? "Reserved (Unused)" :
                       form.strategy_name === "rsi_momentum" ? "EMA Window" :
                       form.strategy_name === "breakout_atr" ? "ATR Window" : "Slow Period"}
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      min={1}
                      onChange={(event) => updateField("slow_period", event.target.value)}
                      required
                      type="number"
                      value={form.slow_period}
                    />
                  </label>
                </div>

                <div className="rounded-2xl border border-amber-300/15 bg-amber-300/8 px-4 py-3 text-sm text-amber-100">
                  {selectedStrategyDescription}
                </div>

                {updateMutation.error instanceof Error ? (
                  <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                    {updateMutation.error.message}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-2xl bg-sky-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                    disabled={updateMutation.isPending}
                    type="submit"
                  >
                    {updateMutation.isPending ? (
                      <RefreshCcw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    {updateMutation.isPending ? "Saving defaults" : "Save runtime defaults"}
                  </button>
                  <p className="text-sm text-slate-400">
                    These defaults affect later worker, status, and backtest behavior.
                  </p>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Operator Guidance</CardTitle>
                  <CardDescription>
                    Keep runtime defaults stable enough that the next worker cycle is predictable.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
                  <Waves className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Shared defaults</p>
                  <p className="mt-2">
                    Worker-cycle, market-sync fallback selection, status, and default backtest runs
                    all resolve through this same persisted config.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">EMA safety</p>
                  <p className="mt-2">
                    Keep the fast period below the slow period so the default EMA strategy remains
                    valid.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Last Saved Result</CardTitle>
                  <CardDescription>
                    The most recent response from the runtime-defaults update flow.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-sky-300/10 p-3 text-sky-200">
                  <Save className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent>
                {updateMutation.data ? (
                  <div className="space-y-3">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-white">{updateMutation.data.detail}</p>
                          <p className="mt-2 text-sm text-slate-400">
                            {updateMutation.data.symbol} {updateMutation.data.timeframe} with EMA{" "}
                            {updateMutation.data.fast_period}/{updateMutation.data.slow_period}
                          </p>
                        </div>
                        <Badge variant={updateMutation.data.changed ? "success" : "neutral"}>
                          {updateMutation.data.changed ? "Changed" : "Unchanged"}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex min-h-40 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
                    No update submitted yet.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </OperatorShell>
  );
}
