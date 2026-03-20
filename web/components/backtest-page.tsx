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

import { MarketCoveragePanel } from "@/components/market-coverage-panel";
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
  getBacktestRuns,
  getMarketDataCoverage,
  getOperatorConfig,
  runBacktest,
  type BacktestControlRequest,
  type BacktestControlResponse,
  type BacktestRunResponse,
  type MarketDataCoverageResponse,
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
  rules: StrategyRuleBuilderRequest;
};

type RuleBuilderPresetKey = BacktestFormState["preset_key"];
type RuleGroupKey = keyof StrategyRuleBuilderRequest;
type RuleCondition = StrategyRuleBuilderRequest["buy_rules"]["conditions"][number];

type RuleBuilderPreset = {
  key: RuleBuilderPresetKey;
  label: string;
  description: string;
  buildRules: (fastPeriod: number, slowPeriod: number) => StrategyRuleBuilderRequest;
};

const timeframeOptions = ["5m", "15m", "1h", "4h", "1d"];
const ruleGroupLabels: Record<RuleGroupKey, string> = {
  shared_filters: "Shared filters",
  buy_rules: "Buy rules",
  sell_rules: "Sell rules",
};

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

function cloneRuleGroup(group: StrategyRuleBuilderRequest["buy_rules"]): StrategyRuleBuilderRequest["buy_rules"] {
  return {
    logic: group.logic,
    conditions: group.conditions.map((condition) => ({ ...condition })),
  };
}

function cloneRules(rules: StrategyRuleBuilderRequest): StrategyRuleBuilderRequest {
  return {
    shared_filters: cloneRuleGroup(rules.shared_filters),
    buy_rules: cloneRuleGroup(rules.buy_rules),
    sell_rules: cloneRuleGroup(rules.sell_rules),
  };
}

function buildPresetRules(
  presetKey: RuleBuilderPresetKey,
  fastPeriod: string,
  slowPeriod: string,
): StrategyRuleBuilderRequest {
  return getPreset(presetKey).buildRules(Number(fastPeriod) || 20, Number(slowPeriod) || 50);
}

function createCondition(
  indicator: RuleCondition["indicator"],
  fastPeriod: string,
  slowPeriod: string,
): RuleCondition {
  if (indicator === "ema_cross") {
    return {
      indicator,
      operator: "bullish",
      fast_period: Number(fastPeriod) || 20,
      slow_period: Number(slowPeriod) || 50,
    };
  }
  if (indicator === "price_vs_ema") {
    return {
      indicator,
      operator: "above",
      period: 20,
    };
  }
  return {
    indicator,
    operator: "above",
    period: 14,
    threshold: "55",
  };
}

function allowedOperators(indicator: RuleCondition["indicator"]): RuleCondition["operator"][] {
  if (indicator === "ema_cross") {
    return ["bullish", "bearish"];
  }
  return ["above", "below"];
}

function minimumCandlesForCondition(condition: RuleCondition): number | null {
  if (condition.indicator === "ema_cross") {
    if (!condition.fast_period || !condition.slow_period || condition.fast_period >= condition.slow_period) {
      return null;
    }
    return condition.slow_period + 1;
  }
  if (condition.indicator === "price_vs_ema") {
    return condition.period && condition.period > 0 ? condition.period : null;
  }
  if (!condition.period || condition.period <= 0 || !condition.threshold) {
    return null;
  }
  return condition.period + 1;
}

function minimumCandlesForRules(rules: StrategyRuleBuilderRequest): number | null {
  const values = [
    rules.shared_filters,
    rules.buy_rules,
    rules.sell_rules,
  ].map((group) => {
    if (group.conditions.length === 0) {
      return group === rules.shared_filters ? 0 : null;
    }
    const minimums = group.conditions.map(minimumCandlesForCondition);
    if (minimums.some((value) => value === null)) {
      return null;
    }
    return Math.max(...minimums.filter((value): value is number => value !== null));
  });

  if (values.some((value) => value === null)) {
    return null;
  }

  return Math.max(...values.filter((value): value is number => value !== null));
}

function inferRuleBuilderPeriods(
  rules: StrategyRuleBuilderRequest,
  fallbackFast: string,
  fallbackSlow: string,
): { fastPeriod: string; slowPeriod: string } {
  for (const group of [rules.shared_filters, rules.buy_rules, rules.sell_rules]) {
    for (const condition of group.conditions) {
      if (
        condition.indicator === "ema_cross" &&
        condition.fast_period !== undefined &&
        condition.slow_period !== undefined
      ) {
        return {
          fastPeriod: String(condition.fast_period),
          slowPeriod: String(condition.slow_period),
        };
      }
    }
  }
  return { fastPeriod: fallbackFast, slowPeriod: fallbackSlow };
}

function detectPresetKey(
  rules: StrategyRuleBuilderRequest,
  fastPeriod: string,
  slowPeriod: string,
): RuleBuilderPresetKey {
  const candidate = JSON.stringify(rules);
  const preset = ruleBuilderPresets.find(
    (entry) =>
      JSON.stringify(buildPresetRules(entry.key, fastPeriod, slowPeriod)) === candidate,
  );
  return preset?.key ?? "ema_crossover_equivalent";
}

function formatRunCreatedAt(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function RuleConditionEditor({
  condition,
  groupKey,
  index,
  fastPeriod,
  slowPeriod,
  onChange,
  onRemove,
}: {
  condition: RuleCondition;
  groupKey: RuleGroupKey;
  index: number;
  fastPeriod: string;
  slowPeriod: string;
  onChange: (next: RuleCondition) => void;
  onRemove: () => void;
}) {
  const prefix = `${ruleGroupLabels[groupKey]} condition ${index + 1}`;

  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-[#09121a] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-white">{prefix}</p>
        <button
          className="rounded-xl border border-rose-400/25 px-3 py-1 text-xs font-medium text-rose-100 transition hover:bg-rose-400/10"
          onClick={onRemove}
          type="button"
        >
          Remove
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-2">
          <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Indicator</span>
          <select
            aria-label={`${prefix} indicator`}
            className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
            onChange={(event) =>
              onChange(createCondition(event.target.value as RuleCondition["indicator"], fastPeriod, slowPeriod))
            }
            value={condition.indicator}
          >
            <option value="ema_cross">ema_cross</option>
            <option value="price_vs_ema">price_vs_ema</option>
            <option value="rsi_threshold">rsi_threshold</option>
          </select>
        </label>

        <label className="space-y-2">
          <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Operator</span>
          <select
            aria-label={`${prefix} operator`}
            className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
            onChange={(event) =>
              onChange({
                ...condition,
                operator: event.target.value as RuleCondition["operator"],
              })
            }
            value={condition.operator}
          >
            {allowedOperators(condition.indicator).map((operator) => (
              <option key={operator} value={operator}>
                {operator}
              </option>
            ))}
          </select>
        </label>
      </div>

      {condition.indicator === "ema_cross" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Fast Period</span>
            <input
              aria-label={`${prefix} fast period`}
              className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
              min={1}
              onChange={(event) =>
                onChange({
                  ...condition,
                  fast_period: Number(event.target.value),
                })
              }
              type="number"
              value={condition.fast_period ?? ""}
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Slow Period</span>
            <input
              aria-label={`${prefix} slow period`}
              className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
              min={1}
              onChange={(event) =>
                onChange({
                  ...condition,
                  slow_period: Number(event.target.value),
                })
              }
              type="number"
              value={condition.slow_period ?? ""}
            />
          </label>
        </div>
      ) : null}

      {condition.indicator === "price_vs_ema" ? (
        <label className="space-y-2">
          <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">EMA Period</span>
          <input
            aria-label={`${prefix} period`}
            className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
            min={1}
            onChange={(event) =>
              onChange({
                ...condition,
                period: Number(event.target.value),
              })
            }
            type="number"
            value={condition.period ?? ""}
          />
        </label>
      ) : null}

      {condition.indicator === "rsi_threshold" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">RSI Period</span>
            <input
              aria-label={`${prefix} period`}
              className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
              min={1}
              onChange={(event) =>
                onChange({
                  ...condition,
                  period: Number(event.target.value),
                })
              }
              type="number"
              value={condition.period ?? ""}
            />
          </label>
          <label className="space-y-2">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Threshold</span>
            <input
              aria-label={`${prefix} threshold`}
              className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
              max={99}
              min={1}
              onChange={(event) =>
                onChange({
                  ...condition,
                  threshold: event.target.value,
                })
              }
              step="0.1"
              type="number"
              value={condition.threshold ?? ""}
            />
          </label>
        </div>
      ) : null}

      <p className="text-xs text-slate-400">
        Minimum candles: {minimumCandlesForCondition(condition) ?? "fix fields"}
      </p>
    </div>
  );
}

function RuleGroupEditor({
  groupKey,
  group,
  fastPeriod,
  slowPeriod,
  onChange,
}: {
  groupKey: RuleGroupKey;
  group: StrategyRuleBuilderRequest["buy_rules"];
  fastPeriod: string;
  slowPeriod: string;
  onChange: (next: StrategyRuleBuilderRequest["buy_rules"]) => void;
}) {
  return (
    <div className="space-y-4 rounded-[1.8rem] border border-cyan-300/10 bg-cyan-300/[0.04] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-white">{ruleGroupLabels[groupKey]}</p>
          <p className="mt-1 text-sm text-slate-300">
            {groupKey === "shared_filters"
              ? "These conditions must pass before either side can trigger."
              : "These conditions decide when the side-specific rule matches."}
          </p>
        </div>
        <button
          className="rounded-2xl border border-cyan-300/20 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-300/10"
          onClick={() =>
            onChange({
              ...group,
              conditions: [...group.conditions, createCondition("ema_cross", fastPeriod, slowPeriod)],
            })
          }
          type="button"
        >
          Add condition
        </button>
      </div>

      <label className="space-y-2">
        <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Group Logic</span>
        <select
          aria-label={`${ruleGroupLabels[groupKey]} logic`}
          className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
          onChange={(event) =>
            onChange({
              ...group,
              logic: event.target.value as StrategyRuleBuilderRequest["buy_rules"]["logic"],
            })
          }
          value={group.logic}
        >
          <option value="all">all</option>
          <option value="any">any</option>
        </select>
      </label>

      {group.conditions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-sm text-slate-400">
          No conditions yet.
        </div>
      ) : (
        <div className="space-y-3">
          {group.conditions.map((condition, index) => (
            <RuleConditionEditor
              condition={condition}
              fastPeriod={fastPeriod}
              groupKey={groupKey}
              index={index}
              key={`${groupKey}-${index}`}
              onChange={(nextCondition) =>
                onChange({
                  ...group,
                  conditions: group.conditions.map((entry, entryIndex) =>
                    entryIndex === index ? nextCondition : entry,
                  ),
                })
              }
              onRemove={() =>
                onChange({
                  ...group,
                  conditions: group.conditions.filter((_, entryIndex) => entryIndex !== index),
                })
              }
              slowPeriod={slowPeriod}
            />
          ))}
        </div>
      )}
    </div>
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

function RecentRunsPanel({
  runs,
  onLoadRun,
}: {
  runs: BacktestRunResponse[];
  onLoadRun: (run: BacktestRunResponse) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Recent Runs</CardTitle>
          <CardDescription>
            Hydrate the form from a recent replay without re-entering the same inputs.
          </CardDescription>
        </div>
        <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
          <AreaChart className="h-5 w-5" />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {runs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-sm text-slate-400">
            No recent runs yet.
          </div>
        ) : (
          runs.map((run) => (
            <div
              className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
              key={run.id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-white">
                    {run.symbol} {run.timeframe}
                  </p>
                  <p className="mt-1 text-sm text-slate-300">{run.detail}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {formatRunCreatedAt(run.created_at)} via {run.source}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={metricVariant(run.status)}>{run.status}</Badge>
                  <Badge variant="neutral">{run.strategy_name}</Badge>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span>Start {formatDecimal(run.starting_equity_input)}</span>
                <span>Required {run.required_candles}</span>
                <span>Return {formatSignedDecimal(run.total_return_pct)}</span>
              </div>
              <button
                className="mt-4 rounded-2xl border border-cyan-300/20 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300/10"
                onClick={() => onLoadRun(run)}
                type="button"
              >
                Load run
              </button>
            </div>
          ))
        )}
      </CardContent>
    </Card>
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
    rules: buildPresetRules("ema_crossover_equivalent", "20", "50"),
  });
  const [hasHydratedDefaults, setHasHydratedDefaults] = useState(false);

  const operatorConfigQuery = useQuery({
    queryKey: ["operator-config"],
    queryFn: getOperatorConfig,
  });
  const recentRunsQuery = useQuery({
    queryKey: ["backtest-runs"],
    queryFn: () => getBacktestRuns(8),
  });
  const coverageQuery = useQuery<MarketDataCoverageResponse>({
    queryKey: [
      "market-data-coverage",
      form.strategy_name,
      form.symbol,
      form.timeframe,
      form.fast_period,
      form.slow_period,
      form.strategy_name === "rule_builder" ? JSON.stringify(form.rules) : "ema",
    ],
    enabled: Boolean(form.symbol.trim() && form.timeframe.trim()),
    queryFn: () =>
      getMarketDataCoverage({
        strategy_name: form.strategy_name,
        symbol: form.symbol.trim(),
        timeframe: form.timeframe.trim(),
        fast_period: Number(form.fast_period),
        slow_period: Number(form.slow_period),
        rules: form.strategy_name === "rule_builder" ? cloneRules(form.rules) : undefined,
      }),
  });

  const backtestMutation = useMutation({
    mutationFn: runBacktest,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["backtest-runs"] }),
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
      rules: buildPresetRules(
        current.preset_key,
        String(operatorConfigQuery.data.fast_period),
        String(operatorConfigQuery.data.slow_period),
      ),
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

  function updateRuleGroup(
    groupKey: RuleGroupKey,
    nextGroup: StrategyRuleBuilderRequest["buy_rules"],
  ) {
    setForm((current) => ({
      ...current,
      rules: {
        ...cloneRules(current.rules),
        [groupKey]: nextGroup,
      },
    }));
  }

  function applyPreset(presetKey: RuleBuilderPresetKey) {
    setForm((current) => ({
      ...current,
      preset_key: presetKey,
      rules: buildPresetRules(presetKey, current.fast_period, current.slow_period),
    }));
  }

  function loadRun(run: BacktestRunResponse) {
    if (run.strategy_name === "rule_builder" && run.rules) {
      const inferred = inferRuleBuilderPeriods(run.rules, form.fast_period, form.slow_period);
      setForm({
        strategy_name: "rule_builder",
        preset_key: detectPresetKey(run.rules, inferred.fastPeriod, inferred.slowPeriod),
        symbol: run.symbol,
        timeframe: run.timeframe,
        fast_period: inferred.fastPeriod,
        slow_period: inferred.slowPeriod,
        starting_equity: String(Number(run.starting_equity_input)),
        rules: cloneRules(run.rules),
      });
      return;
    }

    setForm((current) => ({
      ...current,
      strategy_name: "ema_crossover",
      symbol: run.symbol,
      timeframe: run.timeframe,
      fast_period: run.fast_period !== null ? String(run.fast_period) : current.fast_period,
      slow_period: run.slow_period !== null ? String(run.slow_period) : current.slow_period,
      starting_equity: String(Number(run.starting_equity_input)),
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
      payload.rules = cloneRules(form.rules);
    }

    backtestMutation.mutate(payload);
  }

  const selectedPreset = getPreset(form.preset_key);
  const minimumRuleCandles = minimumCandlesForRules(form.rules);

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

        <MarketCoveragePanel
          coverage={coverageQuery.data}
          description="Inspect stored range, replay minimum, and freshness before submitting the next replay."
          errorMessage={coverageQuery.error instanceof Error ? coverageQuery.error.message : null}
          isLoading={coverageQuery.isLoading}
          title="Replay Readiness"
        />

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
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <label className="flex-1 space-y-2">
                        <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          Rule Builder Preset
                        </span>
                        <select
                          className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                          onChange={(event) =>
                            applyPreset(event.target.value as BacktestFormState["preset_key"])
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
                      <button
                        className="rounded-2xl border border-cyan-300/20 px-4 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300/10"
                        onClick={() => applyPreset(form.preset_key)}
                        type="button"
                      >
                        Reset from preset
                      </button>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="font-medium text-white">{selectedPreset.label}</p>
                      <p className="mt-2 text-sm text-slate-300">{selectedPreset.description}</p>
                      <p className="mt-3 text-xs uppercase tracking-[0.18em] text-slate-400">
                        Estimated minimum candles: {minimumRuleCandles ?? "fix rule fields"}
                      </p>
                    </div>

                    <RuleGroupEditor
                      fastPeriod={form.fast_period}
                      group={form.rules.shared_filters}
                      groupKey="shared_filters"
                      onChange={(nextGroup) => updateRuleGroup("shared_filters", nextGroup)}
                      slowPeriod={form.slow_period}
                    />
                    <RuleGroupEditor
                      fastPeriod={form.fast_period}
                      group={form.rules.buy_rules}
                      groupKey="buy_rules"
                      onChange={(nextGroup) => updateRuleGroup("buy_rules", nextGroup)}
                      slowPeriod={form.slow_period}
                    />
                    <RuleGroupEditor
                      fastPeriod={form.fast_period}
                      group={form.rules.sell_rules}
                      groupKey="sell_rules"
                      onChange={(nextGroup) => updateRuleGroup("sell_rules", nextGroup)}
                      slowPeriod={form.slow_period}
                    />
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
                    Presets still seed the flow, but the payload is now editable before submission.
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
                  <p className="font-medium text-white">Rule builder editor</p>
                  <p className="mt-2">
                    Conditions stay bounded to the existing indicator set and still submit through
                    the existing backtest control API.
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
                    <p className="font-medium text-white">Rule builder</p>
                    <p className="mt-2">
                      {form.rules.shared_filters.conditions.length} shared,{" "}
                      {form.rules.buy_rules.conditions.length} buy,{" "}
                      {form.rules.sell_rules.conditions.length} sell conditions
                    </p>
                    <p className="mt-2 text-xs text-slate-400">
                      Preset seed: {selectedPreset.label}
                    </p>
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <RecentRunsPanel
              onLoadRun={loadRun}
              runs={recentRunsQuery.data?.runs ?? []}
            />
          </div>
        </div>

        <ResultPanel result={backtestMutation.data ?? null} />
      </div>
    </OperatorShell>
  );
}
