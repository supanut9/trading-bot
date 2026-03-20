"use client";

import { useQueries } from "@tanstack/react-query";
import { AlertTriangle, Database, Gauge, Layers3, ShieldAlert, TrendingUp } from "lucide-react";

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
import { useBinanceTicker } from "@/hooks/use-binance-ticker";
import {
  getPerformanceSummary,
  getPositions,
  getStatus,
  getTrades,
  type PerformanceAnalyticsResponse,
  type PositionResponse,
  type StatusResponse,
  type TradeResponse,
} from "@/lib/api";
import { formatDecimal, formatSignedDecimal, formatTimestamp } from "@/lib/format";

function statusVariant(value: string): "danger" | "info" | "success" | "warning" {
  const normalizedValue = value.toLowerCase();
  if (normalizedValue.includes("fail") || normalizedValue.includes("error")) {
    return "danger";
  }
  if (normalizedValue.includes("warn") || normalizedValue.includes("review")) {
    return "warning";
  }
  if (normalizedValue.includes("ready") || normalizedValue.includes("healthy")) {
    return "success";
  }
  return "info";
}

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

function PanelState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
      <AlertTriangle className="h-6 w-6 text-amber-300" />
      <p className="mt-4 text-sm font-medium text-white">{title}</p>
      <p className="mt-2 max-w-md text-sm text-slate-400">{message}</p>
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
      <PanelState
        title="No equity curve data"
        message="Run worker cycles or backtests before expecting plotted PnL movement."
      />
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

  const latest = points[points.length - 1];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-4xl font-semibold tracking-tight text-white">
            {formatSignedDecimal(latest.net_pnl)}
          </p>
          <p className="mt-1 text-sm text-slate-400">Latest net PnL across stored analytics.</p>
        </div>
        <div className="flex gap-3">
          <Badge variant="info">Points {points.length}</Badge>
          <Badge variant="neutral">Updated {formatTimestamp(latest.recorded_at)}</Badge>
        </div>
      </div>
      <div className="rounded-[1.8rem] border border-white/10 bg-[linear-gradient(180deg,rgba(34,211,238,0.08),rgba(8,12,17,0.2))] p-4">
        <svg
          aria-label="Net PnL curve"
          className="h-60 w-full"
          preserveAspectRatio="none"
          viewBox="0 0 100 100"
        >
          <defs>
            <linearGradient id="terminal-curve" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#67e8f9" />
              <stop offset="100%" stopColor="#34d399" />
            </linearGradient>
          </defs>
          <path d={path} fill="none" stroke="url(#terminal-curve)" strokeWidth="2.5" />
        </svg>
      </div>
    </div>
  );
}

function LivePriceBlock({ status }: { status: StatusResponse }) {
  const ticker = useBinanceTicker(status.symbol);

  if (ticker.status === "connecting") {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Latest Price</p>
        <Skeleton className="mt-3 h-9 w-40" />
        <p className="mt-2 text-sm text-slate-400">Connecting to stream…</p>
      </div>
    );
  }

  if (ticker.status === "error") {
    return (
      <MetricBlock
        label="Latest Price"
        value={formatDecimal(status.latest_price, { maximumFractionDigits: 2 })}
        detail={`Fallback — ${ticker.message}`}
      />
    );
  }

  const change = parseFloat(ticker.change24hPct);
  const changeLabel = `${change >= 0 ? "+" : ""}${ticker.change24hPct}% 24 h`;

  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Latest Price</p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
        {formatDecimal(ticker.price, { maximumFractionDigits: 2 })}
      </p>
      <p className={`mt-2 text-sm font-medium ${change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
        {changeLabel}
      </p>
    </div>
  );
}

function RuntimeOverview({ status }: { status: StatusResponse }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricBlock
        label="Execution"
        value={status.execution_mode.toUpperCase()}
        detail={`${status.exchange.toUpperCase()} ${status.symbol} on ${status.timeframe}`}
      />
      <MetricBlock
        label="Strategy"
        value={status.strategy_name}
        detail={`EMA ${status.fast_period}/${status.slow_period} from ${status.operator_config_source}`}
      />
      <LivePriceBlock status={status} />
      <MetricBlock
        label="Live Safety"
        value={status.live_safety_status}
        detail={
          status.live_trading_enabled
            ? status.live_trading_halted
              ? "Live enabled but currently halted"
              : "Live enabled and unhalted"
            : "Paper-trading-first posture"
        }
      />
    </div>
  );
}

function SummaryStrip({
  performance,
  positions,
}: {
  performance: PerformanceAnalyticsResponse;
  positions: PositionResponse[];
}) {
  const primarySummary = performance.summaries[0];
  const realized = positions.reduce((total, item) => total + Number(item.realized_pnl), 0);
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <MetricBlock
        label="Net PnL"
        value={formatSignedDecimal(primarySummary?.net_pnl ?? 0)}
        detail={`${primarySummary?.trade_count ?? 0} total trades`}
      />
      <MetricBlock
        label="Open Positions"
        value={String(positions.length)}
        detail={`${primarySummary?.open_position_count ?? 0} active in analytics`}
      />
      <MetricBlock
        label="Win Rate"
        value={formatDecimal(primarySummary?.win_rate_pct ?? 0)}
        detail={`${primarySummary?.winning_trades ?? 0} wins / ${primarySummary?.losing_trades ?? 0} losses`}
      />
      <MetricBlock
        label="Realized PnL"
        value={formatSignedDecimal(realized)}
        detail="Position ledger realized total"
      />
    </div>
  );
}

export function DashboardPage() {
  const [statusQuery, performanceQuery, positionsQuery, tradesQuery] = useQueries({
    queries: [
      { queryKey: ["status"], queryFn: getStatus },
      { queryKey: ["performance"], queryFn: getPerformanceSummary },
      { queryKey: ["positions"], queryFn: getPositions },
      { queryKey: ["trades"], queryFn: () => getTrades(8) },
    ],
  });

  const hasToplineData = statusQuery.data && performanceQuery.data;
  const panelError =
    statusQuery.error ?? performanceQuery.error ?? positionsQuery.error ?? tradesQuery.error;

  return (
    <OperatorShell>
      <div className="space-y-5">
        <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(10,15,20,0.92),rgba(7,16,25,0.76))] px-6 py-6 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-200/80">
                Feature Operator UI Foundation
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight text-white">
                Paper Trading Situation Room
              </h2>
              <p className="mt-3 max-w-2xl text-sm text-slate-300">
                Fresh operator shell for runtime posture, performance drift, and market-state
                visibility. This does not reuse the old console layout.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Badge variant="info">Next.js</Badge>
              <Badge variant="neutral">Read-only slice</Badge>
              <Badge variant="success">FastAPI-backed</Badge>
            </div>
          </div>
        </header>

        {statusQuery.isLoading || performanceQuery.isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : null}

        {hasToplineData ? (
          <>
            <RuntimeOverview status={statusQuery.data} />
            <SummaryStrip
              performance={performanceQuery.data}
              positions={positionsQuery.data ?? []}
            />
          </>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr)_minmax(360px,0.85fr)]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Performance Curve</CardTitle>
                <CardDescription>Live-computed trajectory from persisted trade analytics.</CardDescription>
              </div>
              <div className="rounded-2xl bg-cyan-400/10 p-3 text-cyan-200">
                <TrendingUp className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent>
              {performanceQuery.isLoading ? (
                <Skeleton className="h-72" />
              ) : performanceQuery.data ? (
                <EquityCurve performance={performanceQuery.data} />
              ) : (
                <PanelState
                  title="Performance feed unavailable"
                  message={panelError instanceof Error ? panelError.message : "Unable to load analytics."}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Runtime Posture</CardTitle>
                <CardDescription>Operational details that affect trust in the current run state.</CardDescription>
              </div>
              <div className="rounded-2xl bg-white/5 p-3 text-slate-200">
                <ShieldAlert className="h-5 w-5" />
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {statusQuery.isLoading ? (
                <>
                  <Skeleton className="h-24" />
                  <Skeleton className="h-24" />
                </>
              ) : statusQuery.data ? (
                <>
                  <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Database className="h-4 w-4 text-cyan-200" />
                        <span className="text-sm font-medium text-white">Database</span>
                      </div>
                      <Badge variant={statusVariant(statusQuery.data.database_status)}>
                        {statusQuery.data.database_status}
                      </Badge>
                    </div>
                    <p className="mt-3 break-all text-xs text-slate-400">
                      {statusQuery.data.database_url}
                    </p>
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Gauge className="h-4 w-4 text-emerald-200" />
                        <span className="text-sm font-medium text-white">Market Feed</span>
                      </div>
                      <Badge variant={statusVariant(statusQuery.data.latest_price_status)}>
                        {statusQuery.data.latest_price_status}
                      </Badge>
                    </div>
                    <p className="mt-3 text-sm text-slate-300">
                      Latest visible price{" "}
                      <span className="font-medium text-white">
                        {formatDecimal(statusQuery.data.latest_price)}
                      </span>
                    </p>
                  </div>
                  <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Layers3 className="h-4 w-4 text-sky-200" />
                        <span className="text-sm font-medium text-white">Balances</span>
                      </div>
                      <Badge variant={statusVariant(statusQuery.data.account_balance_status)}>
                        {statusQuery.data.account_balance_status}
                      </Badge>
                    </div>
                    <div className="mt-4 space-y-2">
                      {statusQuery.data.account_balances.length === 0 ? (
                        <p className="text-sm text-slate-400">No exchange balance snapshot available.</p>
                      ) : (
                        statusQuery.data.account_balances.slice(0, 4).map((balance) => (
                          <div
                            className="flex items-center justify-between rounded-2xl bg-white/[0.03] px-3 py-2"
                            key={balance.asset}
                          >
                            <span className="text-sm text-slate-200">{balance.asset}</span>
                            <span className="text-sm text-white">
                              {formatDecimal(balance.free)} free / {formatDecimal(balance.locked)} locked
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <PanelState
                  title="Runtime status unavailable"
                  message={panelError instanceof Error ? panelError.message : "Unable to load status."}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Open Positions</CardTitle>
                <CardDescription>Active inventory and unrealized exposure.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {positionsQuery.isLoading ? (
                <Skeleton className="h-64" />
              ) : positionsQuery.data ? (
                positionsQuery.data.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Market</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Entry</TableHead>
                        <TableHead>Unrealized</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {positionsQuery.data.map((position) => (
                        <TableRow key={`${position.exchange}-${position.symbol}-${position.side}`}>
                          <TableCell>{position.symbol}</TableCell>
                          <TableCell>{position.side}</TableCell>
                          <TableCell>{formatDecimal(position.quantity, { maximumFractionDigits: 4 })}</TableCell>
                          <TableCell>{formatDecimal(position.average_entry_price)}</TableCell>
                          <TableCell>{formatSignedDecimal(position.unrealized_pnl)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <PanelState
                    title="No open positions"
                    message="The position ledger is clear. New worker fills or live reconciliation will populate this table."
                  />
                )
              ) : (
                <PanelState
                  title="Position feed unavailable"
                  message={panelError instanceof Error ? panelError.message : "Unable to load positions."}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Recent Trades</CardTitle>
                <CardDescription>Latest persisted trade events from the runtime ledger.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {tradesQuery.isLoading ? (
                <Skeleton className="h-64" />
              ) : tradesQuery.data ? (
                tradesQuery.data.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Market</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Price</TableHead>
                        <TableHead>Fee</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tradesQuery.data.map((trade: TradeResponse) => (
                        <TableRow key={trade.id}>
                          <TableCell>#{trade.id}</TableCell>
                          <TableCell>{trade.symbol}</TableCell>
                          <TableCell>{trade.side}</TableCell>
                          <TableCell>{formatDecimal(trade.quantity, { maximumFractionDigits: 4 })}</TableCell>
                          <TableCell>{formatDecimal(trade.price)}</TableCell>
                          <TableCell>
                            {trade.fee_amount && trade.fee_asset
                              ? `${formatDecimal(trade.fee_amount, { maximumFractionDigits: 6 })} ${trade.fee_asset}`
                              : "-"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <PanelState
                    title="No recent trades"
                    message="Trade rows appear here after paper fills or reconciled live fills are recorded."
                  />
                )
              ) : (
                <PanelState
                  title="Trade feed unavailable"
                  message={panelError instanceof Error ? panelError.message : "Unable to load trades."}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </OperatorShell>
  );
}
