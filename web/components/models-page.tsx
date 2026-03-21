"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, RefreshCcw, ChevronDown, ChevronUp, DatabaseZap } from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getModelStatus,
  runMarketSync,
  trainModel,
  type ModelStatusItem,
  type TrainModelResponse,
} from "@/lib/api";

// ─── Feature groups (mirrors features.py FEATURE_GROUPS) ───────────────────
const FEATURE_GROUPS: Record<string, string[]> = {
  Trend: ["ema_diff_pct", "bb_position", "roc_5", "adx"],
  Momentum: ["rsi", "macd_histogram", "stoch_k"],
  Volatility: ["atr_pct", "bb_width", "high_low_pct"],
  Volume: ["volume_ratio"],
  Candle: ["candle_body_pct", "wick_upper_pct", "wick_lower_pct"],
  "Lag Returns": ["close_lag_1", "close_lag_2", "close_lag_3"],
  Time: ["hour_sin", "hour_cos"],
};

const DEFAULT_FEATURES = [
  "ema_diff_pct",
  "bb_position",
  "rsi",
  "macd_histogram",
  "atr_pct",
  "volume_ratio",
  "candle_body_pct",
  "roc_5",
];

const ALL_FEATURES = Object.values(FEATURE_GROUPS).flat();

// ─── Form state ─────────────────────────────────────────────────────────────
type TrainFormState = {
  symbol: string;
  timeframe: string;
  exchange: string;
  model_type: string;
  label_type: string;
  label_horizon: string;
  label_threshold: string;
  candle_limit: string;
  n_estimators: string;
  max_depth: string;
  learning_rate: string;
  split_ratio: string;
  buy_threshold: string;
  sell_threshold: string;
  feature_names: string[];
};

const timeframeOptions = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

const INPUT_CLS =
  "w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10";
const LABEL_CLS = "text-[11px] uppercase tracking-[0.18em] text-slate-400";

// ─── Sub-components ──────────────────────────────────────────────────────────
function MetricCard({ label, value, raw }: { label: string; value: number | null; raw?: boolean }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <p className={LABEL_CLS}>{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">
        {value !== null ? (raw ? value.toFixed(4) : `${(value * 100).toFixed(2)}%`) : "—"}
      </p>
    </div>
  );
}

function FeatureImportancesTable({
  importances,
}: {
  importances: TrainModelResponse["feature_importances"];
}) {
  const sorted = [...importances].sort((a, b) => b.importance - a.importance);
  const maxImportance = sorted[0]?.importance ?? 1;

  return (
    <div className="space-y-2">
      <p className={LABEL_CLS}>Feature Importances</p>
      <div className="space-y-2">
        {sorted.map(({ feature, importance }) => {
          const widthPct = Math.round((importance / maxImportance) * 100);
          return (
            <div className="flex items-center gap-3" key={feature}>
              <span className="w-40 shrink-0 truncate text-xs text-slate-300">{feature}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-blue-500" style={{ width: `${widthPct}%` }} />
              </div>
              <span className="w-16 shrink-0 text-right text-xs text-slate-400">
                {importance.toFixed(4)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function statusVariant(status: string): "success" | "danger" | "warning" | "neutral" {
  if (status === "completed") return "success";
  if (status === "error") return "danger";
  if (status === "insufficient_data") return "warning";
  return "neutral";
}

function TrainingResults({ result }: { result: TrainModelResponse }) {
  const isCompleted = result.status === "completed";

  return (
    <Card className="border-white/10 bg-[rgba(6,10,14,0.92)]">
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-4">
        <CardTitle className="text-base font-semibold text-white">Training Results</CardTitle>
        <Badge variant={statusVariant(result.status)}>{result.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-6">
        {isCompleted ? (
          <>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Accuracy" value={result.accuracy} />
              <MetricCard label="Precision" value={result.precision} />
              <MetricCard label="Recall" value={result.recall} />
              <MetricCard label="ROC-AUC" value={result.roc_auc} raw />
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              <span className="font-medium text-white">{result.sample_count}</span> samples
              {" · "}
              <span className="font-medium text-white">{result.train_count}</span> train
              {" · "}
              <span className="font-medium text-white">{result.test_count}</span> test
              {" · "}
              <span className="font-medium text-white">OOS from #{result.oos_start_index}</span>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300 space-y-1">
              <p><span className="text-slate-500">Model type: </span><span className="text-white">{result.model_type}</span></p>
              <p><span className="text-slate-500">Label: </span><span className="text-white">{result.label_type}</span>{" · "}horizon {result.label_horizon}{" · "}threshold {(result.label_threshold * 100).toFixed(2)}%</p>
              <p><span className="text-slate-500">Buy threshold: </span><span className="text-white">{result.feature_names?.length ?? 0} features</span></p>
            </div>

            {result.feature_importances.length > 0 && (
              <FeatureImportancesTable importances={result.feature_importances} />
            )}

            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <p className={LABEL_CLS}>Model saved to</p>
              <p className="mt-2 break-all text-xs text-slate-300">{result.model_path}</p>
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-rose-400/25 bg-rose-400/5 p-4">
            <p className="text-sm text-rose-300">{result.detail || "Training did not complete."}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FeatureSelector({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (features: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const total = ALL_FEATURES.length;

  function toggle(feature: string) {
    if (selected.includes(feature)) {
      onChange(selected.filter((f) => f !== feature));
    } else {
      onChange([...selected, feature]);
    }
  }

  function toggleGroup(features: string[]) {
    const allOn = features.every((f) => selected.includes(f));
    if (allOn) {
      onChange(selected.filter((f) => !features.includes(f)));
    } else {
      const next = [...selected];
      for (const f of features) {
        if (!next.includes(f)) next.push(f);
      }
      onChange(next);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className={LABEL_CLS}>Features</span>
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">{selected.length} / {total} selected</span>
          <button
            className="text-xs text-cyan-400 hover:text-cyan-300 transition"
            onClick={() => onChange(ALL_FEATURES)}
            type="button"
          >
            All
          </button>
          <button
            className="text-xs text-cyan-400 hover:text-cyan-300 transition"
            onClick={() => onChange(DEFAULT_FEATURES)}
            type="button"
          >
            Default
          </button>
          <button
            className="text-xs text-slate-500 hover:text-white transition"
            onClick={() => setOpen((v) => !v)}
            type="button"
          >
            <span className="flex items-center gap-1">
              {open ? "Hide" : "Expand"}
              {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </span>
          </button>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-3">
        {/* Always-visible group pills */}
        <div className="flex flex-wrap gap-2 mb-2">
          {Object.entries(FEATURE_GROUPS).map(([group, features]) => {
            const allOn = features.every((f) => selected.includes(f));
            const someOn = features.some((f) => selected.includes(f));
            return (
              <button
                className={`rounded-xl border px-3 py-1 text-xs transition ${
                  allOn
                    ? "border-blue-500/50 bg-blue-500/15 text-blue-300"
                    : someOn
                    ? "border-blue-500/25 bg-blue-500/5 text-blue-400/70"
                    : "border-white/10 bg-transparent text-slate-500 hover:text-slate-300"
                }`}
                key={group}
                onClick={() => toggleGroup(features)}
                type="button"
              >
                {group}
              </button>
            );
          })}
        </div>

        {/* Expanded per-feature checkboxes */}
        {open && (
          <div className="mt-3 space-y-3 border-t border-white/10 pt-3">
            {Object.entries(FEATURE_GROUPS).map(([group, features]) => (
              <div key={group}>
                <p className="mb-2 text-[10px] uppercase tracking-widest text-slate-500">{group}</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                  {features.map((feature) => (
                    <label className="flex cursor-pointer items-center gap-2" key={feature}>
                      <input
                        checked={selected.includes(feature)}
                        className="h-3.5 w-3.5 rounded accent-blue-500"
                        onChange={() => toggle(feature)}
                        type="checkbox"
                      />
                      <span className="text-xs text-slate-300">{feature}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ExistingModelsCard() {
  const queryClient = useQueryClient();
  const modelStatusQuery = useQuery({
    queryKey: ["model-status"],
    queryFn: getModelStatus,
  });

  const models: ModelStatusItem[] = modelStatusQuery.data?.models ?? [];

  return (
    <Card className="border-white/10 bg-[rgba(6,10,14,0.92)]">
      <CardHeader className="flex flex-row items-center justify-between gap-4 pb-4">
        <CardTitle className="text-base font-semibold text-white">Trained Models</CardTitle>
        <button
          className="flex items-center gap-1.5 rounded-xl border border-white/10 px-3 py-1.5 text-xs text-slate-400 transition hover:bg-white/[0.04] hover:text-white disabled:opacity-50"
          disabled={modelStatusQuery.isFetching}
          onClick={() => void queryClient.invalidateQueries({ queryKey: ["model-status"] })}
          type="button"
        >
          <RefreshCcw className={`h-3 w-3 ${modelStatusQuery.isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </CardHeader>
      <CardContent>
        {modelStatusQuery.isLoading ? (
          <p className="py-4 text-center text-sm text-slate-500">Loading…</p>
        ) : models.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-500">
            No trained models yet. Train one above.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-white/10">
                <TableHead className="text-slate-400">Symbol</TableHead>
                <TableHead className="text-slate-400">Timeframe</TableHead>
                <TableHead className="text-slate-400">File</TableHead>
                <TableHead className="text-right text-slate-400">Size</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.map((model) => (
                <TableRow
                  className="border-white/10 hover:bg-white/[0.02]"
                  key={`${model.symbol}-${model.timeframe}`}
                >
                  <TableCell className="font-medium text-white">{model.symbol}</TableCell>
                  <TableCell className="text-slate-300">{model.timeframe}</TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-slate-400">
                    {model.model_path}
                  </TableCell>
                  <TableCell className="text-right text-slate-300">
                    {model.exists && model.file_size_kb !== null
                      ? `${model.file_size_kb.toFixed(1)} KB`
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export function ModelsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TrainFormState>({
    symbol: "BTC/USDT",
    timeframe: "1h",
    exchange: "binance",
    model_type: "xgboost",
    label_type: "forward_return",
    label_horizon: "5",
    label_threshold: "0.003",
    candle_limit: "10000",
    n_estimators: "200",
    max_depth: "4",
    learning_rate: "0.1",
    split_ratio: "0.7",
    buy_threshold: "0.60",
    sell_threshold: "0.40",
    feature_names: DEFAULT_FEATURES,
  });
  const [trainResult, setTrainResult] = useState<TrainModelResponse | null>(null);
  const [syncLimit, setSyncLimit] = useState("5000");

  const syncMutation = useMutation({
    mutationFn: () =>
      runMarketSync({
        symbol: form.symbol.trim(),
        timeframe: form.timeframe,
        limit: Number(syncLimit),
        backfill: true,
      }),
  });

  const trainMutation = useMutation({
    mutationFn: trainModel,
    onSuccess: async (data) => {
      setTrainResult(data);
      await queryClient.invalidateQueries({ queryKey: ["model-status"] });
    },
  });

  function updateField<K extends keyof TrainFormState>(key: K, value: TrainFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.feature_names.length === 0) return;
    trainMutation.mutate({
      symbol: form.symbol.trim(),
      timeframe: form.timeframe,
      exchange: form.exchange.trim(),
      model_type: form.model_type,
      label_type: form.label_type,
      label_horizon: Number(form.label_horizon),
      label_threshold: Number(form.label_threshold),
      feature_names: form.feature_names,
      candle_limit: Number(form.candle_limit),
      n_estimators: Number(form.n_estimators),
      max_depth: Number(form.max_depth),
      learning_rate: Number(form.learning_rate),
      split_ratio: Number(form.split_ratio),
      buy_threshold: Number(form.buy_threshold),
      sell_threshold: Number(form.sell_threshold),
    });
  }

  const splitPct = Math.round(Number(form.split_ratio) * 100);
  const testPct = 100 - splitPct;

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(22,9,22,0.94),rgba(10,20,28,0.82))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-purple-200/80">
                Machine Learning
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Model Training
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Train ML classifiers (XGBoost, LightGBM, Random Forest) on stored candle data.
                Select features, configure labels, and set signal thresholds. Models are saved
                locally for use in the ML Signal strategy.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="warning">Write action</Badge>
              <Badge variant="info">ML</Badge>
            </div>
          </div>
        </header>

        {/* Sync candles card */}
        <Card className="border-white/10 bg-[rgba(6,10,14,0.92)]">
          <CardHeader className="flex flex-row items-center justify-between gap-4 pb-4">
            <CardTitle className="text-base font-semibold text-white">Sync Candles</CardTitle>
            <div className="rounded-2xl bg-cyan-400/10 p-3 text-cyan-200">
              <DatabaseZap className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex-1 space-y-2" style={{ minWidth: "140px" }}>
                <span className={LABEL_CLS}>Number of candles</span>
                <input
                  className={INPUT_CLS}
                  max={50000}
                  min={100}
                  onChange={(e) => setSyncLimit(e.target.value)}
                  step={100}
                  type="number"
                  value={syncLimit}
                />
              </label>
              <div className="space-y-2">
                <span className={LABEL_CLS}>Symbol · Timeframe</span>
                <p className="rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-slate-400">
                  {form.symbol} · {form.timeframe}
                </p>
              </div>
              <button
                className="rounded-2xl bg-cyan-700 px-5 py-3 text-sm font-medium text-white transition hover:bg-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={syncMutation.isPending}
                onClick={() => syncMutation.mutate()}
                type="button"
              >
                {syncMutation.isPending ? "Syncing…" : "Sync"}
              </button>
            </div>
            {syncMutation.isSuccess && (
              <p className="mt-3 text-sm text-emerald-400">
                Sync complete — {syncMutation.data.status}
              </p>
            )}
            {syncMutation.isError && (
              <p className="mt-3 text-sm text-rose-400">
                {syncMutation.error instanceof Error ? syncMutation.error.message : "Sync failed."}
              </p>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-5 xl:grid-cols-2">
          {/* Training form */}
          <Card className="border-white/10 bg-[rgba(6,10,14,0.92)]">
            <CardHeader className="flex flex-row items-center justify-between gap-4 pb-4">
              <CardTitle className="text-base font-semibold text-white">Train New Model</CardTitle>
              <div className="rounded-2xl bg-purple-400/10 p-3 text-purple-200">
                <BrainCircuit className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              <form className="space-y-5" onSubmit={handleSubmit}>
                {/* Symbol + Timeframe */}
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Symbol</span>
                    <input
                      className={INPUT_CLS}
                      onChange={(e) => updateField("symbol", e.target.value)}
                      required
                      value={form.symbol}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Timeframe</span>
                    <select
                      className={INPUT_CLS}
                      onChange={(e) => updateField("timeframe", e.target.value)}
                      value={form.timeframe}
                    >
                      {timeframeOptions.map((tf) => (
                        <option key={tf} value={tf}>
                          {tf}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {/* Exchange (read-only) */}
                <label className="space-y-2">
                  <span className={LABEL_CLS}>Exchange</span>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-slate-500 outline-none"
                    readOnly
                    value={form.exchange}
                  />
                </label>

                {/* Model type */}
                <label className="space-y-2">
                  <span className={LABEL_CLS}>Model Type</span>
                  <select
                    className={INPUT_CLS}
                    onChange={(e) => updateField("model_type", e.target.value)}
                    value={form.model_type}
                  >
                    <option value="xgboost">XGBoost</option>
                    <option value="lightgbm">LightGBM</option>
                    <option value="random_forest">Random Forest</option>
                  </select>
                </label>

                {/* Label configuration */}
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 space-y-4">
                  <p className={LABEL_CLS}>Label Configuration</p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className={LABEL_CLS}>Label Type</span>
                      <select
                        className={INPUT_CLS}
                        onChange={(e) => updateField("label_type", e.target.value)}
                        value={form.label_type}
                      >
                        <option value="forward_return">Forward Return</option>
                        <option value="next_candle">Next Candle</option>
                      </select>
                      <p className="text-xs text-slate-500">
                        {form.label_type === "forward_return"
                          ? "Price up >threshold% in next N candles"
                          : "Binary: next candle up or down"}
                      </p>
                    </label>
                    <label className="space-y-2">
                      <span className={LABEL_CLS}>Horizon (candles)</span>
                      <input
                        className={INPUT_CLS}
                        disabled={form.label_type === "next_candle"}
                        max={20}
                        min={1}
                        onChange={(e) => updateField("label_horizon", e.target.value)}
                        required
                        type="number"
                        value={form.label_horizon}
                      />
                    </label>
                  </div>
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Return Threshold (e.g. 0.003 = 0.3%)</span>
                    <input
                      className={INPUT_CLS}
                      disabled={form.label_type === "next_candle"}
                      max={0.1}
                      min={0}
                      onChange={(e) => updateField("label_threshold", e.target.value)}
                      required
                      step={0.001}
                      type="number"
                      value={form.label_threshold}
                    />
                  </label>
                </div>

                {/* Feature selection */}
                <FeatureSelector
                  onChange={(features) => updateField("feature_names", features)}
                  selected={form.feature_names}
                />
                {form.feature_names.length === 0 && (
                  <p className="text-xs text-rose-400">Select at least one feature.</p>
                )}

                {/* Candle limit */}
                <label className="space-y-2">
                  <span className={LABEL_CLS}>Candle Limit</span>
                  <input
                    className={INPUT_CLS}
                    max={50000}
                    min={100}
                    onChange={(e) => updateField("candle_limit", e.target.value)}
                    required
                    step={100}
                    type="number"
                    value={form.candle_limit}
                  />
                  <p className="text-xs text-slate-500">Max candles to use for training (100 – 50,000)</p>
                </label>

                {/* Hyperparameters */}
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>N Estimators</span>
                    <input
                      className={INPUT_CLS}
                      max={2000}
                      min={10}
                      onChange={(e) => updateField("n_estimators", e.target.value)}
                      required
                      type="number"
                      value={form.n_estimators}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Max Depth</span>
                    <input
                      className={INPUT_CLS}
                      max={20}
                      min={1}
                      onChange={(e) => updateField("max_depth", e.target.value)}
                      required
                      type="number"
                      value={form.max_depth}
                    />
                  </label>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Learning Rate</span>
                    <input
                      className={INPUT_CLS}
                      disabled={form.model_type === "random_forest"}
                      max={1}
                      min={0.001}
                      onChange={(e) => updateField("learning_rate", e.target.value)}
                      required
                      step={0.001}
                      type="number"
                      value={form.learning_rate}
                    />
                  </label>
                  <label className="space-y-2">
                    <span className={LABEL_CLS}>Train / Test Split</span>
                    <input
                      className={INPUT_CLS}
                      max={0.95}
                      min={0.5}
                      onChange={(e) => updateField("split_ratio", e.target.value)}
                      required
                      step={0.05}
                      type="number"
                      value={form.split_ratio}
                    />
                    <p className="text-xs text-slate-500">
                      {splitPct}% train · {testPct}% test
                    </p>
                  </label>
                </div>

                {/* Signal thresholds */}
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 space-y-4">
                  <p className={LABEL_CLS}>Signal Thresholds</p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2">
                      <span className={LABEL_CLS}>Buy Threshold</span>
                      <input
                        className={INPUT_CLS}
                        max={1}
                        min={0.5}
                        onChange={(e) => updateField("buy_threshold", e.target.value)}
                        required
                        step={0.01}
                        type="number"
                        value={form.buy_threshold}
                      />
                      <p className="text-xs text-slate-500">P(up) must exceed this to BUY</p>
                    </label>
                    <label className="space-y-2">
                      <span className={LABEL_CLS}>Sell Threshold</span>
                      <input
                        className={INPUT_CLS}
                        max={0.5}
                        min={0}
                        onChange={(e) => updateField("sell_threshold", e.target.value)}
                        required
                        step={0.01}
                        type="number"
                        value={form.sell_threshold}
                      />
                      <p className="text-xs text-slate-500">P(up) must fall below this to SELL</p>
                    </label>
                  </div>
                </div>

                {trainMutation.isError && (
                  <div className="rounded-2xl border border-rose-400/25 bg-rose-400/5 p-4">
                    <p className="text-sm text-rose-300">
                      {trainMutation.error instanceof Error
                        ? trainMutation.error.message
                        : "Training request failed."}
                    </p>
                  </div>
                )}

                <button
                  className="w-full rounded-2xl bg-purple-600 py-3 text-sm font-medium text-white transition hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={trainMutation.isPending || form.feature_names.length === 0}
                  type="submit"
                >
                  {trainMutation.isPending ? "Training…" : "Train Model"}
                </button>
              </form>
            </CardContent>
          </Card>

          {/* Results panel */}
          {trainResult !== null && <TrainingResults result={trainResult} />}
        </div>

        <ExistingModelsCard />
      </div>
    </OperatorShell>
  );
}
