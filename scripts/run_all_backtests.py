#!/usr/bin/env python3
"""Run backtests for every strategy × timeframe combination and print a report."""

import json
import sys
import time
from datetime import datetime

import urllib.request
import urllib.error

API_BASE = "http://127.0.0.1:8000"

STRATEGIES = [
    "ema_crossover",
    "macd_crossover",
    "mean_reversion_bollinger",
    "rsi_momentum",
    "breakout_atr",
]

TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "12h", "1d"]

# Default params per strategy
STRATEGY_PARAMS: dict[str, dict] = {
    "ema_crossover": {"fast_period": 9, "slow_period": 21},
    "macd_crossover": {"fast_period": 12, "slow_period": 26, "macd_signal_period": 9},
    "mean_reversion_bollinger": {
        "bb_period": 20,
        "bb_std_dev": "2.0",
        "rsi_period": 14,
        "rsi_overbought": "70.0",
        "rsi_oversold": "30.0",
    },
    "rsi_momentum": {"rsi_period": 14},
    "breakout_atr": {
        "breakout_period": 20,
        "atr_period": 14,
        "atr_breakout_multiplier": "1.5",
        "atr_stop_multiplier": "2.0",
    },
}


def run_backtest(strategy: str, timeframe: str) -> dict:
    payload = {
        "strategy_name": strategy,
        "timeframe": timeframe,
        "starting_equity": 1000,
        "trading_mode": "SPOT",
        **STRATEGY_PARAMS[strategy],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}/controls/backtest",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"status": "error", "detail": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def fmt(val, decimals=2, suffix="") -> str:
    if val is None:
        return "—"
    try:
        return f"{float(val):.{decimals}f}{suffix}"
    except Exception:
        return str(val)


def main() -> None:
    results = []
    total = len(STRATEGIES) * len(TIMEFRAMES)
    done = 0

    print(
        f"Running {total} backtest combinations ({len(STRATEGIES)} strategies × {len(TIMEFRAMES)} timeframes)…"
    )
    print("This will auto-sync candles from Binance for each combination.\n")

    for strategy in STRATEGIES:
        for timeframe in TIMEFRAMES:
            done += 1
            label = f"{strategy}/{timeframe}"
            print(f"  [{done:2d}/{total}] {label:<40}", end="", flush=True)
            t0 = time.time()
            r = run_backtest(strategy, timeframe)
            elapsed = time.time() - t0
            status = r.get("status", "error")
            print(f"{status}  ({elapsed:.1f}s)")
            results.append({"strategy": strategy, "timeframe": timeframe, "elapsed": elapsed, **r})

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n")
    print("=" * 110)
    print(
        f"  Backtest Report — BTC/USDT SPOT — generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    print("=" * 110)

    header = f"{'Strategy':<28} {'TF':<5} {'Status':<10} {'Candles':>7} {'Trades':>6} {'Return%':>8} {'MaxDD%':>7} {'WinRate':>8} {'PnL':>10} {'Equity':>10}"
    print(header)
    print("-" * 110)

    for r in results:
        status = r.get("status", "error")
        tf = r.get("timeframe", "")
        strat = r.get("strategy_name", r.get("strategy", ""))[:27]

        if status == "completed":
            candles = r.get("candle_count", 0)
            trades = r.get("total_trades") or 0
            ret = r.get("total_return_pct")
            dd = r.get("max_drawdown_pct")
            pnl = r.get("realized_pnl")
            equity = r.get("ending_equity")
            wins = r.get("winning_trades") or 0
            win_rate = f"{(wins / trades * 100):.1f}%" if trades > 0 else "—"
            ret_str = fmt(ret, 2, "%")
            dd_str = fmt(dd, 2, "%")
            pnl_str = fmt(pnl, 2)
            eq_str = fmt(equity, 2)
            print(
                f"{strat:<28} {tf:<5} {status:<10} {candles:>7} {trades:>6} {ret_str:>8} {dd_str:>7} {win_rate:>8} {pnl_str:>10} {eq_str:>10}"
            )
        elif status == "skipped":
            detail = r.get("detail", "")
            candles = r.get("candle_count", 0)
            req = r.get("required_candles", "?")
            print(f"{strat:<28} {tf:<5} {status:<10} {candles:>7}  need {req} — {detail}")
        else:
            detail = str(r.get("detail", r.get("message", "")))[:60]
            print(f"{strat:<28} {tf:<5} {status:<10}  {detail}")

    print("-" * 110)

    # Summary counts
    completed = [r for r in results if r.get("status") == "completed"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    errors = [r for r in results if r.get("status") not in ("completed", "skipped")]

    print(
        f"\n  Completed: {len(completed)} / Skipped (not enough candles): {len(skipped)} / Errors: {len(errors)}"
    )

    if completed:
        profitable = [
            r
            for r in completed
            if r.get("total_return_pct") is not None and float(r["total_return_pct"]) > 0
        ]
        print(f"  Profitable combos: {len(profitable)}/{len(completed)}")

        best = max(completed, key=lambda r: float(r.get("total_return_pct") or -9999))
        worst = min(completed, key=lambda r: float(r.get("total_return_pct") or 9999))
        print(
            f"  Best:  {best.get('strategy_name', best.get('strategy'))}/{best.get('timeframe')}  → {fmt(best.get('total_return_pct'), 2, '%')} return,  {best.get('total_trades', 0)} trades"
        )
        print(
            f"  Worst: {worst.get('strategy_name', worst.get('strategy'))}/{worst.get('timeframe')} → {fmt(worst.get('total_return_pct'), 2, '%')} return,  {worst.get('total_trades', 0)} trades"
        )

    print()


if __name__ == "__main__":
    main()
