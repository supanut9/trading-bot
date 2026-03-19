"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AreaChart,
  Bot,
  CandlestickChart,
  Play,
  RefreshCcw,
  SlidersHorizontal,
} from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getOperatorConfig,
  runBacktest,
  type BacktestControlRequest,
  type BacktestControlResponse,
  type OperatorConfigResponse,
  type StrategyRuleBuilderRequest,
} from "@/lib/api";
import { formatDecimal, formatSignedDecimal } from "@/lib/format";

type BacktestFormState = {
  strategy_name: "ema_crossover" | "rule_builder";
  preset_key: "ema_crossover_equivalent" | "ema_rsi_confirmation" | "mean_reversion";
  symbol: string;
  timeframe: string;
  fast_period: string;
  slow_period: string;
  starting_equity: string;
};

type RuleBuilderPresetKey = BacktestFormState["preset_key"];

type RuleBuilderPreset = {
  key: RuleBuilderPresetKey;
  label: string;
  description: string;
  buildRules: (fastPeriod: number, slowPeriod: number) => StrategyRuleBuilderRequest;
};

const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"];

const ruleBuilderPresets: RuleBuilderPreset[] = [
  {
    key: "ema_crossover_equivalent",
    label: "EMA Crossover Mirror",
    description: "Replicates the default EMA crossover logic through the rule-builder payload.",
    buildRules: (fastPeriod, slowPeriod) => ({
      shared_filters: { logic: "all", conditions: [] },
      buy_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "ema_cross",
            operator: "bullish",
            fast_period: fastPeriod,
            slow_period: slowPeriod,
          },
        ],
      },
      sell_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "ema_cross",
            operator: "bearish",
            fast_period: fastPeriod,
            slow_period: slowPeriod,
          },
        ],
      },
    }),
  },
  {
    key: "ema_rsi_confirmation",
    label: "EMA + RSI Confirmation",
    description: "Requires an EMA cross and confirming RSI momentum on each side.",
    buildRules: (fastPeriod, slowPeriod) => ({
      shared_filters: { logic: "all", conditions: [] },
      buy_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "ema_cross",
            operator: "bullish",
            fast_period: fastPeriod,
            slow_period: slowPeriod,
          },
          {
            indicator: "rsi_threshold",
            operator: "above",
            period: 14,
            threshold: "55",
          },
        ],
      },
      sell_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "ema_cross",
            operator: "bearish",
            fast_period: fastPeriod,
            slow_period: slowPeriod,
          },
          {
            indicator: "rsi_threshold",
            operator: "below",
            period: 14,
            threshold: "45",
          },
        ],
      },
    }),
  },
  {
    key: "mean_reversion",
    label: "Mean Reversion",
    description: "Uses price-versus-EMA and RSI extremes for bounded reversal testing.",
    buildRules: () => ({
      shared_filters: { logic: "all", conditions: [] },
      buy_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "price_vs_ema",
            operator: "below",
            period: 20,
          },
          {
            indicator: "rsi_threshold",
            operator: "below",
            period: 14,
            threshold: "35",
          },
        ],
      },
      sell_rules: {
        logic: "all",
        conditions: [
          {
            indicator: "price_vs_ema",
            operator: "above",
            period: 20,
          },
          {
            indicator: "rsi_threshold",
            operator: "above",
            period: 14,
            threshold: "65",
          },
        ],
      },
    }),
  },
];

function metricVariant(status: string): "danger" | "info" | "success" | "warning" {
  if (status === "failed") {
    return "danger";
  }
  if (status === "skipped") {
    return "warning";
  }
  if (status === "completed") {
    return "success";
  }
  return "info";
}

function describeCondition(
  condition: NonNullable<StrategyRuleBuilderRequest["buy_rules"]["conditions"]>[number],
): string {
  if (condition.indicator === "ema_cross") {
    return `EMA ${condition.fast_period}/${condition.slow_period} ${condition.operator} cross`;
  }
  if (condition.indicator === "price_vs_ema") {
    return `price ${condition.operator} EMA ${condition.period}`;
  }
  return `RSI ${condition.period} ${condition.operator} ${condition.threshold}`;
}

function describeGroup(group: StrategyRuleBuilderRequest["buy_rules"]): string {
  if (group.conditions.length === 0) {
    return "No conditions";
  }
  const separator = group.logic === "all" ? " and " : " or ";
  return group.conditions.map(describeCondition).join(separator);
}

function getPreset(key: RuleBuilderPresetKey): RuleBuilderPreset {
  return (
    ruleBuilderPresets.find((preset) => preset.key === key) ?? ruleBuilderPresets[0]
  );
}

function SummaryStrip({
  operatorConfig,
}: {
  operatorConfig: OperatorConfigResponse;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Default Market</p>
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
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">EMA Defaults</p>
        <p className="mt-3 text-2xl font-semibold tracking-tight text-white">
          {operatorConfig.fast_period}/{operatorConfig.slow_period}
        </p>
        <p className="mt-2 text-sm text-slate-400">Used to seed replay inputs.</p>
      </div>
      <div className="rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">Replay Surface</p>
        <p className="mt-3 text-xl font-semibold tracking-tight text-white">Preset-first</p>
        <p className="mt-2 text-sm text-slate-300">
          Backtests stay bounded to the control API while the runtime keeps paper defaults stable.
        </p>
      </div>
    </div>
  );
}

function ExecutionCurve({ result }: { result: BacktestControlResponse }) {
  if (!result.starting_equity || result.executions.length === 0) {
    return (
      <div className="flex min-h-56 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        Run a backtest with at least one execution to render the realized-equity path.
      </div>
    );
  }

  let equity = Number(result.starting_equity);
  const points = [
    {
      label: "start",
      equity,
    },
  ];

  for (const execution of result.executions) {
    equity += Number(execution.realized_pnl);
    points.push({
      label: execution.action,
      equity,
    });
  }

  const minValue = Math.min(...points.map((point) => point.equity));
  const maxValue = Math.max(...points.map((point) => point.equity));
  const safeMin = minValue === maxValue ? minValue - 1 : minValue;
  const safeMax = minValue === maxValue ? maxValue + 1 : maxValue;
  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const normalized = (point.equity - safeMin) / (safeMax - safeMin);
      const y = 100 - normalized * 100;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-3xl font-semibold tracking-tight text-white">
            {formatSignedDecimal(result.realized_pnl)}
          </p>
          <p className="mt-1 text-sm text-slate-400">Realized PnL across replay executions.</p>
        </div>
        <div className="flex gap-2">
          <Badge variant="info">Executions {result.executions.length}</Badge>
          <Badge variant="neutral">Start {formatDecimal(result.starting_equity)}</Badge>
          <Badge variant="neutral">End {formatDecimal(result.ending_equity)}</Badge>
        </div>
      </div>

      <div className="rounded-[1.8rem] border border-white/10 bg-[linear-gradient(180deg,rgba(34,211,238,0.08),rgba(8,12,17,0.2))] p-4">
        <svg
          aria-label="Backtest realized equity curve"
          className="h-60 w-full"
          preserveAspectRatio="none"
          viewBox="0 0 100 100"
        >
          <defs>
            <linearGradient id="backtest-curve" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#fcd34d" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
          </defs>
          <path d={path} fill="none" stroke="url(#backtest-curve)" strokeWidth="2.5" />
        </svg>
      </div>
    </div>
  );
}

function ResultPanel({
  result,
}: {
  result: BacktestControlResponse | null;
}) {
  if (!result) {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
        <AreaChart className="h-6 w-6 text-cyan-200" />
        <p className="mt-4 text-sm font-medium text-white">No replay submitted yet</p>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          Submit one bounded backtest run to inspect the outcome, execution trail, and realized
          equity path.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-5">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Replay Result</p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-white">
            {result.symbol} {result.timeframe}
          </h3>
          <p className="mt-2 text-sm text-slate-300">{result.detail}</p>
        </div>
        <div className="flex gap-2">
          <Badge variant={metricVariant(result.status)}>{result.status}</Badge>
          <Badge variant="neutral">{result.strategy_name}</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Candles</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {result.candle_count}
          </p>
          <p className="mt-2 text-sm text-slate-400">Required minimum {result.required_candles}</p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Return</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {formatSignedDecimal(result.total_return_pct)}
          </p>
          <p className="mt-2 text-sm text-slate-400">Total return percentage.</p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Trades</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {result.total_trades ?? 0}
          </p>
          <p className="mt-2 text-sm text-slate-400">
            Wins {result.winning_trades ?? 0} / losses {result.losing_trades ?? 0}
          </p>
        </div>
        <div className="rounded-3xl border border-cyan-300/15 bg-cyan-300/5 p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/80">Drawdown</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
            {formatDecimal(result.max_drawdown_pct)}
          </p>
          <p className="mt-2 text-sm text-slate-300">Maximum realized drawdown percentage.</p>
        </div>
      </div>

      {result.strategy_name === "rule_builder" && result.rules ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Shared Filters</p>
            <p className="mt-3 text-sm text-slate-200">{describeGroup(result.rules.shared_filters)}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Buy Rules</p>
            <p className="mt-3 text-sm text-slate-200">{describeGroup(result.rules.buy_rules)}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Sell Rules</p>
            <p className="mt-3 text-sm text-slate-200">{describeGroup(result.rules.sell_rules)}</p>
          </div>
        </div>
      ) : null}

      <ExecutionCurve result={result} />

      <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-4">
        <div className="mb-4 flex flex-wrap gap-2">
          <Badge variant="info">Start {formatDecimal(result.starting_equity_input)}</Badge>
          {result.fast_period && result.slow_period ? (
            <Badge variant="neutral">
              EMA {result.fast_period}/{result.slow_period}
            </Badge>
          ) : null}
          <Badge variant={result.notified ? "success" : "neutral"}>
            {result.notified ? "Notification sent" : "No notification"}
          </Badge>
        </div>
        {result.executions.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Quantity</TableHead>
                <TableHead>Realized PnL</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.executions.map((execution, index) => (
                <TableRow key={`${execution.action}-${index}`}>
                  <TableCell className="uppercase">{execution.action}</TableCell>
                  <TableCell>{formatDecimal(execution.price, { maximumFractionDigits: 4 })}</TableCell>
                  <TableCell>{formatDecimal(execution.quantity, { maximumFractionDigits: 6 })}</TableCell>
                  <TableCell>{formatSignedDecimal(execution.realized_pnl)}</TableCell>
                  <TableCell>{execution.reason}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="flex min-h-32 items-center justify-center rounded-[1.4rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
            No executions were recorded for this replay result.
          </div>
        )}
      </div>
    </div>
  );
}

export function BacktestPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BacktestFormState>({
    strategy_name: "ema_crossover",
    preset_key: "ema_crossover_equivalent",
    symbol: "",
    timeframe: "",
    fast_period: "",
    slow_period: "",
    starting_equity: "10000",
  });
  const [hasHydratedDefaults, setHasHydratedDefaults] = useState(false);

  const operatorConfigQuery = useQuery({
    queryKey: ["operator-config"],
    queryFn: getOperatorConfig,
  });

  const backtestMutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["performance"] }),
        queryClient.invalidateQueries({ queryKey: ["positions"] }),
        queryClient.invalidateQueries({ queryKey: ["trades"] }),
        queryClient.invalidateQueries({ queryKey: ["status"] }),
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
      fast_period: String(operatorConfigQuery.data.fast_period),
      slow_period: String(operatorConfigQuery.data.slow_period),
    }));
    setHasHydratedDefaults(true);
  }, [hasHydratedDefaults, operatorConfigQuery.data]);

  function updateField<Key extends keyof BacktestFormState>(
    key: Key,
    value: BacktestFormState[Key],
  ) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const payload: BacktestControlRequest = {
      strategy_name: form.strategy_name,
      symbol: form.symbol.trim(),
      timeframe: form.timeframe.trim(),
      starting_equity: Number(form.starting_equity),
    };

    if (form.strategy_name === "ema_crossover") {
      payload.fast_period = Number(form.fast_period);
      payload.slow_period = Number(form.slow_period);
    } else {
      payload.rules = getPreset(form.preset_key).buildRules(
        Number(form.fast_period),
        Number(form.slow_period),
      );
    }

    backtestMutation.mutate(payload);
  }

  const selectedPreset = getPreset(form.preset_key);

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(22,17,9,0.94),rgba(10,20,28,0.82))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-amber-200/80">
                Feature Operator Backtest UI
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Replay Analysis Deck
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Run one bounded replay against stored candles, inspect the outcome immediately, and
                keep experimentation on the API-backed control path.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="warning">Write action</Badge>
              <Badge variant="info">Preset-first</Badge>
              <Badge variant="neutral">Backtest only</Badge>
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
          <SummaryStrip operatorConfig={operatorConfigQuery.data} />
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(400px,0.95fr)]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Run Backtest</CardTitle>
                <CardDescription>
                  Choose a market window, strategy shape, and starting equity for one replay.
                </CardDescription>
              </div>
              <div className="rounded-2xl bg-amber-300/10 p-3 text-amber-100">
                <Play className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Strategy
                    </span>
                    <select
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      onChange={(event) =>
                        updateField(
                          "strategy_name",
                          event.target.value as BacktestFormState["strategy_name"],
                        )
                      }
                      value={form.strategy_name}
                    >
                      <option value="ema_crossover">ema_crossover</option>
                      <option value="rule_builder">rule_builder</option>
                    </select>
                  </label>
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Starting Equity
                    </span>
                    <input
                      className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                      min={1}
                      onChange={(event) => updateField("starting_equity", event.target.value)}
                      required
                      type="number"
                      value={form.starting_equity}
                    />
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
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
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                      Fast EMA
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
                      Slow EMA
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

                {form.strategy_name === "rule_builder" ? (
                  <div className="space-y-4 rounded-[1.8rem] border border-cyan-300/10 bg-cyan-300/[0.04] p-4">
                    <label className="space-y-2">
                      <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                        Rule Builder Preset
                      </span>
                      <select
                        className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                        onChange={(event) =>
                          updateField(
                            "preset_key",
                            event.target.value as BacktestFormState["preset_key"],
                          )
                        }
                        value={form.preset_key}
                      >
                        {ruleBuilderPresets.map((preset) => (
                          <option key={preset.key} value={preset.key}>
                            {preset.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="font-medium text-white">{selectedPreset.label}</p>
                      <p className="mt-2 text-sm text-slate-300">{selectedPreset.description}</p>
                    </div>
                  </div>
                ) : null}

                {backtestMutation.error instanceof Error ? (
                  <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                    {backtestMutation.error.message}
                  </div>
                ) : null}

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    className="inline-flex items-center gap-2 rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
                    disabled={backtestMutation.isPending}
                    type="submit"
                  >
                    {backtestMutation.isPending ? (
                      <RefreshCcw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    {backtestMutation.isPending ? "Running backtest" : "Run backtest"}
                  </button>
                  <p className="text-sm text-slate-400">
                    Replays stored candles only. This does not widen live execution behavior.
                  </p>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Preset Guidance</CardTitle>
                  <CardDescription>
                    Keep the UI preset-first even when the rule-builder path is selected.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
                  <SlidersHorizontal className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">EMA crossover</p>
                  <p className="mt-2">
                    Uses explicit fast and slow periods, matching the runtime strategy shape.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Rule builder presets</p>
                  <p className="mt-2">
                    Presets serialize a bounded rule payload to the existing backtest endpoint
                    without introducing a new backend surface.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Active Replay Shape</CardTitle>
                  <CardDescription>
                    Current strategy inputs before the next backtest submission.
                  </CardDescription>
                </div>
                <div className="rounded-2xl bg-emerald-300/10 p-3 text-emerald-100">
                  {form.strategy_name === "rule_builder" ? (
                    <Bot className="h-5 w-5" />
                  ) : (
                    <CandlestickChart className="h-5 w-5" />
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Strategy</p>
                  <p className="mt-2">{form.strategy_name}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Market</p>
                  <p className="mt-2">
                    {form.symbol || "-"} {form.timeframe || "-"}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">EMA Window</p>
                  <p className="mt-2">
                    {form.fast_period || "-"} / {form.slow_period || "-"}
                  </p>
                </div>
                {form.strategy_name === "rule_builder" ? (
                  <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                    <p className="font-medium text-white">Preset</p>
                    <p className="mt-2">{selectedPreset.label}</p>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>

        <ResultPanel result={backtestMutation.data ?? null} />
      </div>
    </OperatorShell>
  );
}
