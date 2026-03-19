"use client";

import type { ChangeEvent } from "react";
import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Download,
  LineChart,
  NotebookTabs,
  Radar,
  Search,
  Sigma,
  WalletCards,
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
  apiUrl,
  getPerformanceSummary,
  getRecoveryDashboard,
  getStatus,
  type PerformanceAnalyticsResponse,
  type RecoveryDashboardResponse,
  type StatusResponse,
} from "@/lib/api";
import { formatDecimal, formatSignedDecimal, formatTimestamp } from "@/lib/format";

type RecoveryFilterState = {
  order_status: string;
  requires_review: "all" | "true" | "false";
  event_type: string;
  search: string;
};

function MetricBlock({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">{label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-white">{value}</p>
      <p className="mt-2 text-sm text-slate-400">{detail}</p>
    </div>
  );
}

function EquityCurve({
  performance,
}: {
  performance: PerformanceAnalyticsResponse;
}) {
  const points = performance.equity_curve;
  if (points.length === 0) {
    return (
      <div className="flex min-h-56 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
        No equity-curve points yet. Run worker cycles or backtests before expecting trend data.
      </div>
    );
  }

  const numericValues = points.map((point) => Number(point.net_pnl));
  const minValue = Math.min(...numericValues);
  const maxValue = Math.max(...numericValues);
  const safeMin = minValue === maxValue ? minValue - 1 : minValue;
  const safeMax = minValue === maxValue ? maxValue + 1 : maxValue;
  const path = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * 100;
      const normalized = (Number(point.net_pnl) - safeMin) / (safeMax - safeMin);
      const y = 100 - normalized * 100;
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-300">
          Latest point {formatTimestamp(points[points.length - 1]?.recorded_at)}
        </p>
        <Badge variant="info">Points {points.length}</Badge>
      </div>
      <div className="rounded-[1.8rem] border border-white/10 bg-[linear-gradient(180deg,rgba(74,222,128,0.08),rgba(8,12,17,0.2))] p-4">
        <svg
          aria-label="Reporting equity curve"
          className="h-64 w-full"
          preserveAspectRatio="none"
          viewBox="0 0 100 100"
        >
          <defs>
            <linearGradient id="reporting-curve" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#4ade80" />
              <stop offset="100%" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
          <path d={path} fill="none" stroke="url(#reporting-curve)" strokeWidth="2.5" />
        </svg>
      </div>
    </div>
  );
}

function ExportLink({
  href,
  label,
  description,
}: {
  href: string;
  label: string;
  description: string;
}) {
  return (
    <a
      className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 transition hover:border-white/20 hover:bg-white/[0.05]"
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <div>
        <p className="text-sm font-medium text-white">{label}</p>
        <p className="mt-1 text-sm text-slate-400">{description}</p>
      </div>
      <ArrowUpRight className="h-4 w-4 text-cyan-200" />
    </a>
  );
}

function buildRecoveryCsvHref(filters: RecoveryFilterState): string {
  const params = new URLSearchParams();
  if (filters.order_status) {
    params.set("recovery_order_status", filters.order_status);
  }
  if (filters.requires_review !== "all") {
    params.set("recovery_requires_review", filters.requires_review);
  }
  if (filters.event_type) {
    params.set("recovery_event_type", filters.event_type);
  }
  if (filters.search.trim()) {
    params.set("recovery_search", filters.search.trim());
  }
  const suffix = params.toString();
  return apiUrl(`/reports/live-recovery.csv${suffix ? `?${suffix}` : ""}`);
}

export function ReportingPage() {
  const [recoveryFilters, setRecoveryFilters] = useState<RecoveryFilterState>({
    order_status: "",
    requires_review: "all",
    event_type: "",
    search: "",
  });

  const recoveryQueryParams = {
    recovery_order_status: recoveryFilters.order_status || undefined,
    recovery_requires_review:
      recoveryFilters.requires_review === "all"
        ? undefined
        : recoveryFilters.requires_review === "true",
    recovery_event_type: recoveryFilters.event_type || undefined,
    recovery_search: recoveryFilters.search.trim() || undefined,
  };

  const [statusQuery, performanceQuery, recoveryQuery] = useQueries({
    queries: [
      { queryKey: ["status"], queryFn: getStatus },
      { queryKey: ["performance"], queryFn: getPerformanceSummary },
      {
        queryKey: ["recovery-dashboard", recoveryQueryParams],
        queryFn: () => getRecoveryDashboard(recoveryQueryParams),
      },
    ],
  });

  const status = statusQuery.data as StatusResponse | undefined;
  const performance = performanceQuery.data as PerformanceAnalyticsResponse | undefined;
  const recovery = recoveryQuery.data as RecoveryDashboardResponse | undefined;
  const summary = performance?.summaries[0];

  function updateRecoveryFilter<Key extends keyof RecoveryFilterState>(
    key: Key,
    value: RecoveryFilterState[Key],
  ) {
    setRecoveryFilters((current) => ({
      ...current,
      [key]: value,
    }));
  }

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(8,17,12,0.94),rgba(11,18,27,0.8))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-emerald-200/80">
                Feature Recovery Reporting UI
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Performance And Recovery Ledger
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Analytics, export links, and live recovery visibility in the Next.js operator
                surface.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="success">Analytics</Badge>
              <Badge variant="warning">Recovery</Badge>
              <Badge variant="info">CSV exports</Badge>
            </div>
          </div>
        </header>

        {statusQuery.isLoading || performanceQuery.isLoading || recoveryQuery.isLoading ? (
          <div className="grid gap-4 lg:grid-cols-4">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : null}

        {status && summary ? (
          <div className="grid gap-4 lg:grid-cols-4">
            <MetricBlock
              label="Mode"
              value={status.execution_mode.toUpperCase()}
              detail={`${status.symbol} ${status.timeframe}`}
            />
            <MetricBlock
              label="Net PnL"
              value={formatSignedDecimal(summary.net_pnl)}
              detail={`${summary.trade_count} total trades`}
            />
            <MetricBlock
              label="Win Rate"
              value={formatDecimal(summary.win_rate_pct)}
              detail={`${summary.winning_trades} wins / ${summary.losing_trades} losses`}
            />
            <MetricBlock
              label="Drawdown"
              value={formatDecimal(summary.max_drawdown)}
              detail={`${summary.open_position_count} open positions`}
            />
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Equity Curve</CardTitle>
                <CardDescription>
                  Stored performance points from paper-runtime and backtest activity.
                </CardDescription>
              </div>
              <div className="rounded-2xl bg-emerald-300/10 p-3 text-emerald-100">
                <LineChart className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              {performanceQuery.isLoading ? (
                <Skeleton className="h-72" />
              ) : performance ? (
                <EquityCurve performance={performance} />
              ) : (
                <div className="rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 py-10 text-center text-sm text-slate-400">
                  Performance analytics are unavailable.
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-5">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Export Desk</CardTitle>
                  <CardDescription>Download the current reporting datasets as CSV.</CardDescription>
                </div>
                <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
                  <Download className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <ExportLink
                  description="Daily realized PnL rollups."
                  href={apiUrl("/performance/daily.csv")}
                  label="Daily performance"
                />
                <ExportLink
                  description="Equity-curve points for plotting."
                  href={apiUrl("/performance/equity.csv")}
                  label="Equity curve"
                />
                <ExportLink
                  description="Current positions view."
                  href={apiUrl("/reports/positions.csv")}
                  label="Positions"
                />
                <ExportLink
                  description="Recent trades export."
                  href={apiUrl("/reports/trades.csv?limit=100")}
                  label="Trades"
                />
                <ExportLink
                  description="Filtered live recovery export."
                  href={buildRecoveryCsvHref(recoveryFilters)}
                  label="Live recovery"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Summary Detail</CardTitle>
                  <CardDescription>Computed metrics from the latest analytics snapshot.</CardDescription>
                </div>
                <div className="rounded-2xl bg-cyan-300/10 p-3 text-cyan-200">
                  <Sigma className="h-5 w-5" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-300">
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Average win / loss</p>
                  <p className="mt-2">
                    {formatSignedDecimal(summary?.average_win)} /{" "}
                    {formatSignedDecimal(summary?.average_loss)}
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Profit factor</p>
                  <p className="mt-2">{formatDecimal(summary?.profit_factor)}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-medium text-white">Expectancy</p>
                  <p className="mt-2">{formatSignedDecimal(summary?.expectancy)}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Recovery Overview</CardTitle>
              <CardDescription>
                Unresolved live state, stale orders, and recent recovery activity.
              </CardDescription>
            </div>
            <div className="rounded-2xl bg-amber-300/10 p-3 text-amber-100">
              <Radar className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 lg:grid-cols-4">
              <MetricBlock
                label="Safety"
                value={recovery?.live_safety_status ?? "n/a"}
                detail={
                  recovery?.live_trading_enabled
                    ? recovery.live_trading_halted
                      ? "Live enabled, entry halted"
                      : "Live enabled"
                    : "Paper only"
                }
              />
              <MetricBlock
                label="Unresolved"
                value={String(recovery?.unresolved_live_orders ?? 0)}
                detail="Filtered unresolved live orders"
              />
              <MetricBlock
                label="Events"
                value={String(recovery?.recovery_event_count ?? 0)}
                detail="Recent reconcile and cancel activity"
              />
              <MetricBlock
                label="Stale Orders"
                value={String(recovery?.stale_live_orders.length ?? 0)}
                detail={`Threshold ${recovery?.stale_threshold_minutes ?? "-"} minutes`}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.2fr)]">
              <label className="space-y-2">
                <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Order Status
                </span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    updateRecoveryFilter("order_status", event.target.value)
                  }
                  value={recoveryFilters.order_status}
                >
                  <option value="">All statuses</option>
                  <option value="review_required">review_required</option>
                  <option value="submitted">submitted</option>
                  <option value="open">open</option>
                  <option value="partially_filled">partially_filled</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Needs Review
                </span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    updateRecoveryFilter(
                      "requires_review",
                      event.target.value as RecoveryFilterState["requires_review"],
                    )
                  }
                  value={recoveryFilters.requires_review}
                >
                  <option value="all">All</option>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Event Type
                </span>
                <select
                  className="w-full rounded-2xl border border-white/10 bg-[#09121a] px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                  onChange={(event: ChangeEvent<HTMLSelectElement>) =>
                    updateRecoveryFilter("event_type", event.target.value)
                  }
                  value={recoveryFilters.event_type}
                >
                  <option value="">All events</option>
                  <option value="live_reconcile">live_reconcile</option>
                  <option value="live_cancel">live_cancel</option>
                </select>
              </label>
              <label className="space-y-2">
                <span className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Search
                </span>
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
                  <input
                    className="w-full rounded-2xl border border-white/10 bg-[#09121a] py-3 pl-10 pr-4 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/10"
                    onChange={(event: ChangeEvent<HTMLInputElement>) =>
                      updateRecoveryFilter("search", event.target.value)
                    }
                    placeholder="client order id, status, next action"
                    value={recoveryFilters.search}
                  />
                </div>
              </label>
            </div>

            <div className="grid gap-5 xl:grid-cols-2">
              <div className="space-y-5">
                <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="warning">
                      Latest {recovery?.latest_recovery_event_type ?? "none"}
                    </Badge>
                    <Badge variant="neutral">
                      {recovery?.latest_recovery_event_status ?? "n/a"}
                    </Badge>
                    <Badge variant="info">
                      {recovery?.latest_recovery_event_at
                        ? formatTimestamp(recovery.latest_recovery_event_at)
                        : "No recent event"}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm text-slate-300">
                    {recovery?.latest_recovery_event_context ?? "No recovery context yet."}
                  </p>
                </div>

                <Card className="bg-[rgba(10,15,20,0.5)]">
                  <CardHeader>
                    <div>
                      <CardTitle>Stale Live Orders</CardTitle>
                      <CardDescription>
                        Orders older than the configured stale threshold.
                      </CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {recovery && recovery.stale_live_orders.length > 0 ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Order</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Age</TableHead>
                            <TableHead>Updated</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {recovery.stale_live_orders.map((order) => (
                            <TableRow key={order.id}>
                              <TableCell>#{order.id}</TableCell>
                              <TableCell>{order.status}</TableCell>
                              <TableCell>{order.age_minutes}m</TableCell>
                              <TableCell>{formatTimestamp(order.updated_at)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : (
                      <div className="flex min-h-40 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
                        No stale live orders matched the current recovery slice.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card className="bg-[rgba(10,15,20,0.5)]">
                <CardHeader>
                  <div>
                    <CardTitle>Recovery Queue</CardTitle>
                    <CardDescription>
                      Unresolved live orders and their current next action.
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {recovery && recovery.unresolved_orders.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Order</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Review</TableHead>
                          <TableHead>Next Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {recovery.unresolved_orders.map((order) => (
                          <TableRow key={order.id}>
                            <TableCell>
                              #{order.id} {order.client_order_id ?? order.exchange_order_id ?? ""}
                            </TableCell>
                            <TableCell>{order.status}</TableCell>
                            <TableCell>{String(order.requires_operator_review)}</TableCell>
                            <TableCell>{order.next_action}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="flex min-h-40 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
                      No unresolved live orders matched the current filters.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card className="bg-[rgba(10,15,20,0.5)]">
              <CardHeader>
                <div>
                  <CardTitle>Recovery Timeline</CardTitle>
                  <CardDescription>
                    Recent live reconcile and cancel outcomes with derived context.
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                {recovery && recovery.recovery_events.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>When</TableHead>
                        <TableHead>Event</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Detail</TableHead>
                        <TableHead>Context</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recovery.recovery_events.map((event) => (
                        <TableRow key={`${event.created_at}-${event.event_type}`}>
                          <TableCell>{formatTimestamp(event.created_at)}</TableCell>
                          <TableCell>{event.event_type}</TableCell>
                          <TableCell>{event.status}</TableCell>
                          <TableCell>{event.detail}</TableCell>
                          <TableCell>{event.context}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex min-h-40 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
                    No recovery events matched the current filters.
                  </div>
                )}
              </CardContent>
            </Card>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Daily Rollup</CardTitle>
              <CardDescription>Most recent trading-day aggregates from persisted analytics.</CardDescription>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
              <NotebookTabs className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent>
            {performanceQuery.isLoading ? (
              <Skeleton className="h-72" />
            ) : performance && performance.daily_rows.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Trades</TableHead>
                    <TableHead>Wins</TableHead>
                    <TableHead>Losses</TableHead>
                    <TableHead>Realized</TableHead>
                    <TableHead>Fees</TableHead>
                    <TableHead>Net</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {performance.daily_rows.slice(0, 10).map((row) => (
                    <TableRow key={`${row.mode}-${row.trade_date}`}>
                      <TableCell>{row.trade_date}</TableCell>
                      <TableCell>{row.trade_count}</TableCell>
                      <TableCell>{row.winning_trades}</TableCell>
                      <TableCell>{row.losing_trades}</TableCell>
                      <TableCell>{formatSignedDecimal(row.realized_pnl)}</TableCell>
                      <TableCell>{formatDecimal(row.fees)}</TableCell>
                      <TableCell>{formatSignedDecimal(row.net_pnl)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex min-h-48 items-center justify-center rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.02] px-6 text-center text-sm text-slate-400">
                No daily performance rows yet.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Coverage Notes</CardTitle>
              <CardDescription>What this reporting slice is responsible for today.</CardDescription>
            </div>
            <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
              <WalletCards className="h-5 w-5" />
            </div>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              <p className="font-medium text-white">Analytics only</p>
              <p className="mt-2">
                This route reads computed performance data and report exports. It does not mutate
                runtime state.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              <p className="font-medium text-white">Live recovery</p>
              <p className="mt-2">
                Recovery queue, stale orders, and recent recovery events now reuse read-only API
                slices instead of leaving operators with CSV-only visibility.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              <p className="font-medium text-white">CSV still first-class</p>
              <p className="mt-2">
                Filtered live-recovery exports remain available for offline review.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </OperatorShell>
  );
}
