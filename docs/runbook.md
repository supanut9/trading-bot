# Runbook

## Purpose

This runbook describes how to start, stop, and inspect the trading bot during local development.

## Start API

```bash
make run-api
```

## Start Worker

```bash
make run-worker
```

Default worker behavior:

- runs one orchestration cycle and exits
- reads the latest stored candles for the configured symbol and timeframe
- applies strategy, risk checks, and paper execution in order
- skips duplicate execution for the same signal candle

To run it as a polling worker instead of a single cycle:

```bash
WORKER_RUN_ONCE=false make run-worker
```

Optional worker tuning variables:

- `STRATEGY_FAST_PERIOD`
- `STRATEGY_SLOW_PERIOD`
- `PAPER_ACCOUNT_EQUITY`
- `RISK_PER_TRADE_PCT`
- `MAX_OPEN_POSITIONS`
- `MAX_DAILY_LOSS_PCT`
- `WORKER_POLL_INTERVAL_SECONDS`

## Start Database

```bash
make db-up
```

Default local connection string:

```bash
postgresql+psycopg://trading_bot:trading_bot@127.0.0.1:5432/trading_bot
```

To inspect database logs:

```bash
make db-logs
```

To stop the database:

```bash
make db-down
```

To initialize tables after dependencies are installed:

```bash
make init-db
```

## Stop

Stop the running process with `Ctrl+C`.

## Safety

- local mode uses paper trading by default
- do not enable live trading during bootstrap
- credentials should be provided only through environment variables
- SQLite remains an acceptable fallback only for lightweight local bootstrap work

## Observability

- API health endpoint: `/health`
- logs are written to stdout
- major architecture and workflow decisions are tracked in `docs/decisions.md`

## Failure Handling

- if the worker crashes, inspect the latest logs first
- if configuration is missing, verify `.env` values against `.env.example`
- if the worker reports `no_candles`, load or persist recent candles before retrying
- if the worker reports `duplicate_signal`, confirm whether the latest signal candle was already executed as intended

## Logging Expectations

During development, keep these sources of truth separate:

- code and git history for implementation detail
- `docs/decisions.md` for durable project decisions
- application logs for runtime behavior

When debugging the bot, prefer runtime logs first. When explaining why the system is designed a certain way, prefer `docs/decisions.md`.
