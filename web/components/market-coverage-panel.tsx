"use client";

import { Database, RefreshCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { MarketDataCoverageResponse } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";

function freshnessVariant(
  status: string,
): "danger" | "info" | "neutral" | "success" | "warning" {
  if (status === "fresh") {
    return "success";
  }
  if (status === "stale") {
    return "warning";
  }
  if (status === "empty") {
    return "neutral";
  }
  if (status === "unknown") {
    return "info";
  }
  return "neutral";
}

function readinessVariant(
  status: string,
): "danger" | "info" | "neutral" | "success" | "warning" {
  if (status === "ready") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  if (status === "not_ready") {
    return "danger";
  }
  return "neutral";
}

export function MarketCoveragePanel({
  title,
  description,
  coverage,
  isLoading,
  errorMessage,
}: {
  title: string;
  description: string;
  coverage: MarketDataCoverageResponse | undefined;
  isLoading: boolean;
  errorMessage?: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-100">
          {isLoading ? <RefreshCcw className="h-5 w-5 animate-spin" /> : <Database className="h-5 w-5" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorMessage ? (
          <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
            {errorMessage}
          </div>
        ) : null}

        {isLoading && !coverage ? (
          <div className="grid gap-3 md:grid-cols-2">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        ) : coverage ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={readinessVariant(coverage.readiness_status)}>
                {coverage.readiness_status}
              </Badge>
              <Badge variant={freshnessVariant(coverage.freshness_status)}>
                {coverage.freshness_status}
              </Badge>
              <Badge variant="neutral">
                {coverage.symbol} {coverage.timeframe}
              </Badge>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Stored Candles</p>
                <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
                  {coverage.candle_count}
                </p>
                <p className="mt-2 text-sm text-slate-400">Replay minimum {coverage.required_candles}</p>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Gap To Ready</p>
                <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
                  {coverage.additional_candles_needed}
                </p>
                <p className="mt-2 text-sm text-slate-400">
                  {coverage.satisfies_required_candles ? "History is sufficient" : "More history needed"}
                </p>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">First Candle</p>
                <p className="mt-3 text-sm font-medium text-white">
                  {formatTimestamp(coverage.first_open_time)}
                </p>
                <p className="mt-2 text-sm text-slate-400">Stored range start.</p>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Latest Close</p>
                <p className="mt-3 text-sm font-medium text-white">
                  {formatTimestamp(coverage.latest_close_time)}
                </p>
                <p className="mt-2 text-sm text-slate-400">Freshness {coverage.freshness_status}.</p>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              {coverage.detail}
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 px-4 py-5 text-sm text-slate-400">
            Coverage is unavailable for this selection.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
