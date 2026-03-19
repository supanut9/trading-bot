"use client";

import { useQueries } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Download,
  LineChart,
  NotebookTabs,
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
  getStatus,
  type PerformanceAnalyticsResponse,
  type StatusResponse,
} from "@/lib/api";
import { formatDecimal, formatSignedDecimal, formatTimestamp } from "@/lib/format";

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

export function ReportingPage() {
  const [statusQuery, performanceQuery] = useQueries({
    queries: [
      { queryKey: ["status"], queryFn: getStatus },
      { queryKey: ["performance"], queryFn: getPerformanceSummary },
    ],
  });

  const status = statusQuery.data as StatusResponse | undefined;
  const performance = performanceQuery.data as PerformanceAnalyticsResponse | undefined;
  const summary = performance?.summaries[0];

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(8,17,12,0.94),rgba(11,18,27,0.8))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-emerald-200/80">
                Feature Operator Reporting UI
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Performance Ledger
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Analytics, export links, and replay-ready reporting in the Next.js operator surface.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="success">Analytics</Badge>
              <Badge variant="info">CSV exports</Badge>
              <Badge variant="neutral">API-backed</Badge>
            </div>
          </div>
        </header>

        {statusQuery.isLoading || performanceQuery.isLoading ? (
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
                  description="Recent audit outcomes across controls."
                  href={apiUrl("/reports/audit.csv")}
                  label="Audit feed"
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
              <p className="font-medium text-white">CSV first</p>
              <p className="mt-2">
                The export desk links directly to FastAPI CSV endpoints so offline review stays
                available.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-slate-300">
              <p className="font-medium text-white">Further slices</p>
              <p className="mt-2">
                Recovery reporting and more advanced filters remain separate operator-reporting
                features.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </OperatorShell>
  );
}
