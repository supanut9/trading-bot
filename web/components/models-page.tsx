"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, RefreshCcw } from "lucide-react";

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
  trainModel,
  type ModelStatusItem,
  type TrainModelResponse,
} from "@/lib/api";

type TrainFormState = {
  symbol: string;
  timeframe: string;
  exchange: string;
  n_estimators: string;
  max_depth: string;
  learning_rate: string;
  split_ratio: string;
};

const timeframeOptions = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

const INPUT_CLS =
  "w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10";
const LABEL_CLS = "text-[11px] uppercase tracking-[0.18em] text-slate-400";

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
    n_estimators: "200",
    max_depth: "4",
    learning_rate: "0.1",
    split_ratio: "0.7",
  });
  const [trainResult, setTrainResult] = useState<TrainModelResponse | null>(null);

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
    trainMutation.mutate({
      symbol: form.symbol.trim(),
      timeframe: form.timeframe,
      exchange: form.exchange.trim(),
      n_estimators: Number(form.n_estimators),
      max_depth: Number(form.max_depth),
      learning_rate: Number(form.learning_rate),
      split_ratio: Number(form.split_ratio),
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
                Train an XGBoost classifier on stored candle data. The model learns buy and sell
                signals from 8 technical indicator features and is saved locally for use in the
                XGBoost Signal strategy.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="warning">Write action</Badge>
              <Badge variant="info">XGBoost</Badge>
            </div>
          </div>
        </header>

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

                <label className="space-y-2">
                  <span className={LABEL_CLS}>Exchange</span>
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-[#050b11] px-4 py-3 text-sm text-slate-500 outline-none"
                    readOnly
                    value={form.exchange}
                  />
                </label>

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
                  disabled={trainMutation.isPending}
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
