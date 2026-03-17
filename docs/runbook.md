# Runbook

## Purpose

This runbook describes how to start, stop, and inspect the trading bot during local development.

## Start API

```bash
make run-api
```

Operational endpoints:

- `GET /health`
- `GET /status`
- `GET /positions`
- `GET /trades`
- `POST /market-data/candles`
- `POST /controls/worker-cycle`
- `POST /controls/backtest`
- `GET /reports`
- `GET /reports/positions.csv`
- `GET /reports/trades.csv`
- `GET /reports/backtest-summary.csv`
- `GET /reports/audit.csv`

Load candles for local worker testing:

```bash
curl -X POST http://127.0.0.1:8000/market-data/candles \
  -H 'Content-Type: application/json' \
  -d '{
    "candles": [
      {
        "open_time": "2026-01-01T00:00:00Z",
        "close_time": "2026-01-01T01:00:00Z",
        "open_price": "100000",
        "high_price": "100100",
        "low_price": "99900",
        "close_price": "100050",
        "volume": "12.5"
      }
    ]
  }'
```

Request behavior:

- uses configured defaults for `exchange`, `symbol`, and `timeframe` when omitted
- stores closed candle batches through the existing market data service
- upserts by `exchange + symbol + timeframe + open_time`

Manual controls:

- `POST /controls/worker-cycle` runs one worker cycle with the current configured strategy, risk, and paper/live mode
- `POST /controls/market-sync` fetches recent closed candles for the configured exchange, symbol, and timeframe and stores them through the market data service
- `POST /controls/backtest` runs one backtest over stored candles with the current configured strategy and risk settings
- control endpoints do not accept arbitrary trading parameters; they only use current application configuration

Report exports:

- `GET /reports` renders an operator-facing HTML dashboard over positions, trades, backtest summary data, and recent audit events
- `GET /reports/positions.csv` exports the current positions view as CSV
- `GET /reports/trades.csv` exports recent trades as CSV and supports the same `limit` query parameter as `GET /trades`
- `GET /reports/backtest-summary.csv` runs one backtest summary export against stored candles using current settings
- `GET /reports/audit.csv` exports recent audit events for control runs and notification delivery attempts

## Start Worker

```bash
make run-worker
```

Default worker behavior:

- runs one orchestration cycle and exits
- reads the latest stored candles for the configured symbol and timeframe
- can optionally sync recent closed candles from the configured exchange before strategy evaluation
- applies strategy, risk checks, and paper execution in order
- skips duplicate execution for the same signal candle
- emits notifications for executions and risk rejections when configured
- skips the cycle safely if enabled market-data sync fails

To run it as a polling worker instead of a single cycle:

```bash
WORKER_RUN_ONCE=false make run-worker
```

In polling mode, the worker cycle is registered as a scheduled job. Optional recurring
backtest summaries can also be enabled as a second scheduled job.

Optional worker tuning variables:

- `STRATEGY_FAST_PERIOD`
- `STRATEGY_SLOW_PERIOD`
- `PAPER_ACCOUNT_EQUITY`
- `RISK_PER_TRADE_PCT`
- `MAX_OPEN_POSITIONS`
- `MAX_DAILY_LOSS_PCT`
- `WORKER_POLL_INTERVAL_SECONDS`
- `MARKET_DATA_SYNC_ENABLED`
- `MARKET_DATA_SYNC_LIMIT`
- `MARKET_DATA_SYNC_TIMEOUT_SECONDS`
- `MARKET_DATA_API_BASE_URL`
- `BACKTEST_SCHEDULE_ENABLED`
- `BACKTEST_SCHEDULE_INTERVAL_SECONDS`
- `NOTIFICATION_CHANNEL`
- `NOTIFICATION_WEBHOOK_URL`
- `NOTIFICATION_TIMEOUT_SECONDS`

To enable Binance candle sync before each worker cycle:

```bash
MARKET_DATA_SYNC_ENABLED=true make run-worker
```

## Run Backtest

```bash
make run-backtest
```

Backtest behavior:

- loads stored candles for the configured exchange, symbol, and timeframe
- reuses the EMA strategy and risk sizing logic
- simulates entries and exits in memory without writing orders, trades, or positions
- force-closes any remaining open position on the final candle for summary reporting
- emits notifications for completed and skipped runs when configured

Notification channels:

- `NOTIFICATION_CHANNEL=none`: disable notifications
- `NOTIFICATION_CHANNEL=log`: write notification payloads into stdout logs
- `NOTIFICATION_CHANNEL=webhook`: send JSON payloads to `NOTIFICATION_WEBHOOK_URL`

Current notification coverage:

- worker execution outcomes
- worker risk rejections
- backtest completed and skipped outcomes
- market sync completed and failed outcomes from `POST /controls/market-sync`

Webhook delivery behavior:

- webhook notifications are treated as successful only on HTTP `2xx`
- non-`2xx` responses are logged as `notification_delivery_failed` and do not change the underlying worker, backtest, or market-sync result

Example local notification test:

```bash
NOTIFICATION_CHANNEL=log make run-backtest
```

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
- recent operational audit events are available through `/reports` and `/reports/audit.csv`
- major architecture and workflow decisions are tracked in `docs/decisions.md`

## Failure Handling

- if the worker crashes, inspect the latest logs first
- if configuration is missing, verify `.env` values against `.env.example`
- if the worker reports `no_candles`, load recent candles through `POST /market-data/candles` before retrying
- if the worker reports `duplicate_signal`, confirm whether the latest signal candle was already executed as intended
- if notifications are expected but absent, verify `NOTIFICATION_CHANNEL` and `NOTIFICATION_WEBHOOK_URL`
- if webhook delivery fails, inspect the `notification_delivery_failed` log entry for the event type and channel, then confirm the webhook endpoint returned an HTTP `2xx`

## Logging Expectations

During development, keep these sources of truth separate:

- code and git history for implementation detail
- `docs/decisions.md` for durable project decisions
- application logs for runtime behavior

When debugging the bot, prefer runtime logs first. When explaining why the system is designed a certain way, prefer `docs/decisions.md`.
