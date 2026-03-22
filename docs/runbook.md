# Runbook

## Purpose

This runbook describes how to start, stop, and inspect the trading bot during local development.

## Start API

```bash
make run-api
```

Containerized API path:

```bash
make docker-build
make docker-run-api
```

Operational endpoints:

- `GET /health`
- `GET /status`
- `GET /positions`
- `GET /performance/summary`
- `GET /performance/daily.csv`
- `GET /performance/equity.csv`
- `GET /trades`
- `POST /market-data/candles`
- `POST /market-data/demo-scenarios/{scenario_name}`
- `POST /controls/worker-cycle`
- `POST /controls/backtest`
- `POST /controls/live-halt`
- `GET /reports/positions.csv`
- `GET /reports/trades.csv`
- `GET /reports/backtest-summary.csv`
- `GET /reports/audit.csv`
- `GET /reports/notification-delivery.csv`
- `GET /reports/live-recovery.csv`

Browser UI support:

- the API allows local frontend origins from `FRONTEND_ORIGINS`
- default allowed origins are `http://127.0.0.1:3000` and `http://localhost:3000`

## Start Operator UI

```bash
make install-web
make run-web
```

Default local UI URL:

- `http://127.0.0.1:3000`

Frontend environment notes:

- `web/.env.local.example` defines `NEXT_PUBLIC_API_BASE_URL`
- the default points to `http://127.0.0.1:8000`
- override it only when the API is running on a different host or port

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

Load a preset demo scenario instead of hand-writing candle JSON:

```bash
curl -X POST http://127.0.0.1:8000/market-data/demo-scenarios/buy-crossover
```

Available demo scenarios:

- `buy-crossover`
- `sell-crossover`
- `no-action`

Demo scenario behavior:

- loads a deterministic nine-candle sequence anchored to a fixed local demo window
- overwrites the same candle window on repeated loads so the scenario is repeatable
- returns the expected strategy signal shape for quick operator verification

Manual controls:

- `POST /controls/worker-cycle` runs one worker cycle with the current configured strategy, risk, and paper/live mode
- `GET /controls/operator-config` returns the effective paper-runtime strategy, symbol, timeframe, and EMA defaults
- `POST /controls/operator-config` persists paper-runtime strategy, symbol, timeframe, and EMA defaults for later worker, sync, status, and console use
- `POST /controls/market-sync` fetches recent closed candles for the configured exchange and either the effective runtime symbol/timeframe or an explicitly supplied market override, then stores them through the market data service
- `POST /controls/backtest` runs one backtest over stored candles and can now accept either the legacy EMA inputs or a structured rule-builder payload with separate shared, buy, and sell groups
- bounded backtest runs now persist one summary history row for later review and backtest form hydration
- `GET /market-data/coverage` returns stored candle range, replay minimum, freshness status, and readiness guidance for the selected market slice and replay shape
- live worker execution now rejects a new same-side live submission when an unresolved live order already exists for that market
- `POST /controls/live-halt` persists the live-entry halt state used by status and worker execution
- control endpoints do not accept arbitrary trading parameters; they only use current application configuration
- the browser UI now lives in the Next.js app under `web/` and consumes these API endpoints instead of backend-rendered HTML pages
- the Next.js operator surface now includes `/backtest` for replay analysis, replay-readiness coverage, `/controls` for market intake and market-coverage checks, and `/reports` for performance analytics and direct CSV export links

Report exports:

- `GET /performance/summary` returns computed performance analytics by mode, including summary, equity-curve points, and daily rows
- `GET /performance/daily.csv` exports daily performance rollups for offline review
- `GET /performance/equity.csv` exports equity-curve points for offline inspection or plotting
- `GET /reports/positions.csv` exports the current positions view as CSV
- `GET /reports/trades.csv` exports recent trades as CSV and supports the same `limit` query parameter as `GET /trades`
- `GET /reports/backtest-summary.csv` runs one backtest summary export against stored candles using current settings
- `GET /reports/backtest-runs` returns recent summary-level backtest runs for the Next.js backtest route
- `GET /reports/backtest-runs.csv` exports recent summary-level backtest runs
- `GET /reports/recovery` returns the read-only recovery dashboard slice used by the Next.js reporting route
- `GET /reports/notifications` returns the read-only notification-delivery slice used by the Next.js reporting route
- `GET /reports/audit` returns the read-only generic audit slice used by the Next.js reporting route
- `GET /reports/audit.csv` exports recent audit events for control runs and notification delivery attempts
- `GET /reports/notification-delivery.csv` exports notification-delivery audit rows
- `GET /reports/live-recovery.csv` exports unresolved live-order recovery rows

## Start Worker

```bash
make run-worker
```

Containerized worker path:

```bash
make docker-build
make docker-run-worker
```

Default worker behavior:

- runs one orchestration cycle and exits
- reads the latest stored candles for the configured symbol and timeframe
- can optionally sync recent closed candles from the configured exchange before strategy evaluation
- applies strategy, risk checks, and the configured execution adapter in order
- skips duplicate execution for the same signal candle
- emits notifications for executions and risk rejections when configured
- skips the cycle safely if enabled market-data sync fails

Execution boundary notes:

- worker execution now resolves through an execution adapter factory
- paper mode uses the existing paper execution adapter
- live mode resolves through the live execution service when exchange credentials are configured

Live order routing groundwork:

- `EXCHANGE_API_BASE_URL` configures the signed exchange API endpoint
- `EXCHANGE_API_KEY` and `EXCHANGE_API_SECRET` are required when live trading is enabled
- the Binance live order client currently supports validate-only and submitted market-order requests as a tested infrastructure path

Live execution behavior:

- explicit live mode now submits orders through the live execution service when exchange credentials are configured
- accepted live orders are persisted locally with mode `live`, canonical local status, and exchange order id when available
- local trades and positions are not updated from live submission alone; they are updated only after explicit fill reconciliation confirms a remote filled status
- new live entries can be blocked by `LIVE_TRADING_HALTED=true` without disabling reconcile, cancel, or reporting workflows
- live entry sizing is bounded by `LIVE_MAX_ORDER_NOTIONAL` and `LIVE_MAX_POSITION_QUANTITY`

Live fill reconciliation:

- `POST /controls/live-reconcile` checks recent open live orders against the configured exchange
- only remote `filled` orders create local trades and update live positions
- open and partial exchange states are normalized into canonical local statuses such as `open` and `partially_filled`
- detail-incomplete or unknown exchange responses are persisted as `review_required` so operators can see uncertain state explicitly
- reconcile outcomes now also emit a compact `recovery_summary` so startup sync, scheduled reconcile, and manual reconcile runs describe the recovery slice in one operator-readable line
- repeated reconciliation is idempotent for already-reconciled orders because only recent open live orders are considered
- `LIVE_RECONCILE_SCHEDULE_ENABLED=true` and `LIVE_RECONCILE_SCHEDULE_INTERVAL_SECONDS` enable the same workflow as a recurring worker job in live mode
- `STARTUP_STATE_SYNC_ENABLED=true` runs the same reconciliation workflow once during live worker startup before any new execution is attempted
- if startup state sync fails in live mode, the worker exits without entering a new execution cycle

Live order cancel control:

- `POST /controls/live-halt` persists the live-entry halt state used by status and worker execution
- `POST /controls/live-cancel` cancels a live order by exactly one identifier: `order_id`, `client_order_id`, or `exchange_order_id`
- cancellation is bounded to local live orders in cancelable states such as `submitted`, `open`, or `partially_filled`
- local order status is updated only after the exchange confirms cancellation

Next.js controls route:

- `/controls` shows the current live posture from `GET /status`
- operators can halt or resume live entry, run live reconcile, and submit one explicit cancel identifier at a time
- the browser remains a bounded control surface; duplicate-order checks, sizing limits, and fail-closed execution behavior remain backend-owned

Stale live order visibility:

- reporting now flags open live orders whose `updated_at` age exceeds `STALE_LIVE_ORDER_THRESHOLD_MINUTES`
- stale-order detection is read-only and does not imply automatic cancellation
- operators should use stale-order visibility together with live reconcile and live cancel controls when reviewing unresolved exchange state

Live order recovery report:

- `GET /reports` now includes a compact recovery summary over unresolved live orders and recent recovery events
- the Next.js `/reports` route now consumes `GET /reports/recovery` for recovery queue, stale-order, and timeline visibility
- `GET /reports` also includes a recovery queue with `recovery_state`, `review_required`, and `next_action` columns plus a recovery timeline of recent live reconcile and live cancel events
- the recovery timeline now includes a context column derived from audit payloads such as reconcile counts or cancel identifiers
- `/reports` now supports recovery filters for order status, review-required state, event type, and free-text search
- `GET /reports/live-recovery.csv` exports unresolved live orders with the latest recovery-event context, `requires_operator_review`, `recovery_state`, and `next_action`
- recovery-state meanings:
- `awaiting_exchange`: recent open order, usually rerun reconcile before acting
- `partial_fill_in_flight`: exchange has executed part of the order, rerun reconcile and avoid speculative cancel decisions
- `stale_open_order`: open order has aged past the stale threshold, reconcile or cancel after confirming exchange state
- `stale_partial_fill`: partial fill has aged past the stale threshold, reconcile first and cancel only when the remaining open quantity is understood
- `manual_review_required`: exchange response drift or missing fill detail, inspect exchange state before trusting local recovery state
- recovery reporting is read-only and is intended to shorten operator review during live incident handling

Runtime log correlation:

- API responses now return `X-Request-ID`; send one if you want to preserve an upstream request id, otherwise the API generates one
- standard log lines now include `correlation_id`, which matches the request id for API work
- scheduled worker-cycle, backtest, live-reconcile, and startup-sync runs generate one runtime correlation id per run so related log entries can be grouped quickly
- notifications emitted during those correlated runs now include the same `correlation_id` in the payload and notification-delivery audit trail

Notification delivery reporting:

- `GET /reports` now includes notification-delivery summary cards and a recent delivery table
- the Next.js `/reports` route now consumes `GET /reports/notifications` for the notification-delivery panel
- `GET /reports/notification-delivery.csv` exports notification-delivery audit rows
- the notification-delivery CSV export supports filtering by `notification_status`, `notification_channel`, and `notification_related_event_type`
- `GET /reports` also includes a notification-delivery filter form, and the export link preserves the same active notification filters

Audit reporting:

- `GET /reports` now includes an audit filter form for `audit_event_type`, `audit_status`, `audit_source`, and `audit_search`
- the recent-audit table now includes explicit columns for exchange, symbol, timeframe, channel, related event type, and correlation id when available
- `GET /reports/audit.csv` supports the same audit filter parameters
- `GET /reports/audit.csv` also exports `correlation_id` as a first-class column instead of requiring payload parsing
- the audit CSV export link preserves the same active audit filters shown in the dashboard

Reconciliation alerting:

- failed startup sync emits a `startup_state_sync.failed` notification when notifications are enabled
- failed scheduled live reconciliation emits a `live_reconcile.failed` notification when notifications are enabled
- scheduled live reconciliation also emits `live_orders.stale_detected` when stale live orders remain after the reconciliation pass

Live balance visibility:

- `GET /status` includes `account_balance_status` and `account_balances`
- `GET /status` also includes `live_safety_status`, `live_trading_halted`, `live_max_order_notional`, `live_max_position_quantity`, `live_max_total_exposure_notional`, `live_max_symbol_exposure_notional`, `live_max_symbol_concentration_pct`, and `live_max_concurrent_positions`
- balance visibility is read-only and only attempts exchange lookup when live trading is enabled
- the snapshot is filtered to the configured symbol's base and quote assets so operators can verify funded live mode quickly

Deployment packaging:

- the repository ships one runtime image that selects `api`, `worker`, or `backtest` via `APP_RUNTIME`
- `make docker-run-api` exposes the API on port `8000`
- `make docker-run-worker` runs the worker with the same image and current `.env`
- runtime packaging does not inject secrets; exchange credentials and database URLs must still come from environment variables

Deployment environment baseline:

- `.env.deploy.api.example` is the baseline for API containers and binds `API_HOST=0.0.0.0`
- `.env.deploy.worker.example` is the baseline for worker containers and sets `WORKER_RUN_ONCE=false`
- `.env.example` remains the local-development baseline and focuses on local-only overrides
- the example env files are intentionally minimal; unspecified values fall back to `app/config.py`
- API and worker deployments should use separate env files even when they share the same database and exchange defaults

Post-deploy smoke checks:

- `make smoke-check-api` verifies `/health`, `/status`, and database reachability against the deployed API
- `make smoke-check-worker` verifies the deployed worker configuration, database reachability, and live safety posture without running a worker cycle
- run the smoke checks after deploy and again after rollback before resuming normal operator workflows
- live-capable smoke checks now fail if `/status` does not match the configured halt flag, configured live limits, or required startup-sync posture

Runtime startup validation:

- API, worker, and backtest startup now fail early when deployment-critical configuration is invalid
- non-local runtimes must use a PostgreSQL-compatible `DATABASE_URL`
- non-local API runtimes must not bind `API_HOST` to loopback addresses
- `NOTIFICATION_CHANNEL=webhook` requires `NOTIFICATION_WEBHOOK_URL`
- live worker runtimes require `STARTUP_STATE_SYNC_ENABLED=true`

Latest price visibility:

- `GET /status` now includes `latest_price_status` and `latest_price`
- `GET /reports` shows the same latest read-only price in the reporting deck
- `GET /console` shows the same latest read-only price alongside paper-trading controls
- latest price uses the public exchange market-data client and does not imply websocket or tick-stream support

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
- `LIVE_TRADING_HALTED`
- `LIVE_MAX_ORDER_NOTIONAL`
- `LIVE_MAX_POSITION_QUANTITY`
- `WORKER_POLL_INTERVAL_SECONDS`
- `MARKET_DATA_SYNC_ENABLED`
- `MARKET_DATA_SYNC_LIMIT`
- `MARKET_DATA_SYNC_TIMEOUT_SECONDS`
- `MARKET_DATA_API_BASE_URL`
- `BACKTEST_SCHEDULE_ENABLED`
- `BACKTEST_SCHEDULE_INTERVAL_SECONDS`
- `LIVE_RECONCILE_SCHEDULE_ENABLED`
- `LIVE_RECONCILE_SCHEDULE_INTERVAL_SECONDS`
- `STARTUP_STATE_SYNC_ENABLED`
- `STALE_LIVE_ORDER_THRESHOLD_MINUTES`
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
- append sync stores only candles newer than the latest stored candle, while backfill sync upserts the full fetched window to load older missing candles

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
postgresql+psycopg://trading_bot:trading_bot@127.0.0.1:5434/trading_bot
```

Override the default host port when needed:

```bash
POSTGRES_HOST_PORT=5544 make db-up
```

Keep `DATABASE_URL` on the same port you expose from Docker Compose.

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

## Production Readiness

Current production target:

- deployed paper trading with PostgreSQL, startup validation, smoke checks, reporting, and bounded operator controls
- live trading remains a separate higher bar and should stay disabled by default until the live-capable checklist below is satisfied end to end

Paper-production go-live checklist:

- deploy only from merged `main`
- PostgreSQL is in use and reachable from both API and worker runtimes
- API and worker use the intended deployment env files rather than local bootstrap defaults
- `GET /health`, `GET /status`, `GET /console`, and `GET /reports` all respond as expected in the deployed environment
- `make smoke-check-api` and `make smoke-check-worker` or their deployed equivalents pass after release
- market-data sync, one bounded worker cycle, and one bounded backtest have been exercised successfully against the deployed stack
- reporting surfaces show expected positions, trades, audit events, and latest runtime status after the verification run
- notification delivery is configured and tested if operators rely on alerts during paper operation
- operators know the bounded controls they may use in production: market sync, worker cycle, backtest, live halt, live reconcile, and live cancel
- rollback steps, backup ownership, and on-call review surfaces are documented for the deployed environment

Paper-production operator conclusion:

- the deployment is suitable for unattended or semi-attended paper trading
- runtime visibility is good enough to detect failures without direct database inspection
- live trading is still disabled and is not implied by paper-production readiness

Minimum checks before enabling live mode:

- `main` is green on the latest merged change and no required checks are failing
- `GET /health` returns healthy and `GET /status` returns the expected `execution_mode`
- `GET /controls/live-readiness` returns `ready=true`
- `/status` shows `live_readiness_status=ready` with no blocking reasons
- exchange credentials are provided only through environment variables
- `account_balance_status` is `available` and the reported base and quote assets match the configured symbol
- portfolio risk caps are configured and visible in `/status` for the intended live rollout shape
- `STARTUP_STATE_SYNC_ENABLED=true` and `LIVE_RECONCILE_SCHEDULE_ENABLED=true` are set for live-capable operation
- notification delivery is configured and tested through the intended channel
- stale live order threshold is set and understood by the operator
- PostgreSQL persistence is in use; SQLite is not acceptable for live-capable operation
- a recent database backup exists and restore steps have been verified
- operators know the bounded recovery controls: live reconcile, live cancel, stale-order review, and live recovery report

Recommended pre-live verification sequence:

```bash
make test
make run-api
make run-worker
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/status
curl http://127.0.0.1:8000/controls/live-readiness
curl -X POST http://127.0.0.1:8000/controls/live-reconcile
curl http://127.0.0.1:8000/reports/live-recovery.csv
```

Expected operator conclusion before enabling live mode:

- local status is healthy
- live readiness is explicitly understood and no blocking prerequisite is unresolved
- exchange balances are visible
- reconciliation succeeds or clearly reports no unresolved work
- no unexplained stale live orders remain
- configured portfolio caps are understood and match the intended rollout size
- alerts are routed to an observed destination

Live-trading gap rule:

- treat live trading as not production-ready by default even when the code paths exist
- do not use paper-production readiness as evidence that exchange-facing execution is safe enough
- if any live prerequisite above is missing or untested, keep `LIVE_TRADING_ENABLED=false`
- if a live resume attempt is rejected by readiness checks, investigate the reported blocking reasons before retrying

## Deployment And Restart

Deployment expectations:

- deploy only from merged `main`
- use the same configuration bundle for API and worker where live flags and exchange credentials must agree
- keep one writer-style worker deployment for live execution and reconciliation to avoid duplicated scheduled work
- verify database connectivity before starting API or worker processes

Recommended restart order for live-capable operation:

1. Confirm there is no active incident requiring manual pause, cancel, or reconciliation.
2. Start PostgreSQL and verify connectivity.
3. Start the API and confirm `GET /health` and `GET /status` are healthy.
4. Start the worker with startup state sync enabled.
5. Confirm the worker completed startup sync before allowing new live execution to continue.

Restart semantics:

- live startup should fail closed if startup state sync cannot confirm exchange state
- do not bypass startup sync after an unclean stop unless the open-order state is already understood manually
- after restart, review `/reports`, `/reports/audit.csv`, and `/reports/live-recovery.csv` before concluding the system is caught up

## Rollback

Rollback expectations:

- prefer rolling back application code without rolling back database state
- do not restore an older code revision into live mode unless its order and reconciliation schema expectations still match the current database
- if a deployment is reverted, run live reconcile before trusting local open-order state

Recommended rollback sequence:

1. Stop the worker so no new execution is attempted during rollback.
2. Keep the API available if needed for bounded controls and reporting.
3. Deploy the last known-good application revision.
4. Run startup state sync or `POST /controls/live-reconcile` before resuming worker execution.
5. Review stale orders, recent audit events, and live recovery output before resuming normal operation.

## Backups And Recovery

Backup expectations:

- back up PostgreSQL on a regular schedule before live-capable operation
- treat orders, trades, positions, candles, and audit events as the minimum recovery dataset
- keep backups outside the running container or host-local ephemeral storage

Recovery guidance:

- restore the latest consistent PostgreSQL backup first
- start the API in a non-live posture if exchange state is still uncertain
- run reconciliation against the exchange before trusting restored local order, trade, or position state
- use live recovery reports and stale-order visibility to identify any remaining mismatch after restore

## Stop

Stop the running process with `Ctrl+C`.

## Safety

- local mode uses paper trading by default
- valid execution-mode combinations are `PAPER_TRADING=true` with `LIVE_TRADING_ENABLED=false` or `PAPER_TRADING=false` with `LIVE_TRADING_ENABLED=true`
- do not enable explicit live mode without exchange credentials and a clear plan for fill reconciliation
- do not enable explicit live mode without PostgreSQL backups, alert routing, and a documented operator procedure
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
- if live orders are being submitted, confirm exchange order status separately before assuming any local position change
- if notifications are expected but absent, verify `NOTIFICATION_CHANNEL` and `NOTIFICATION_WEBHOOK_URL`
- if webhook delivery fails, inspect the `notification_delivery_failed` log entry for the event type and channel, then confirm the webhook endpoint returned an HTTP `2xx`

## Alerts And Incident Handling

Alert response expectations:

- `startup_state_sync.failed`: do not resume live execution until reconciliation failure is understood and cleared
- `live_reconcile.failed`: investigate exchange connectivity or credential issues, then rerun bounded reconciliation
- `live_orders.stale_detected`: review unresolved orders, rerun reconcile, and cancel only when the exchange state is confirmed

Minimum operator review surfaces during an incident:

- `/status`
- `/reports`
- `/reports/audit.csv`
- `/reports/live-recovery.csv`

Incident handling rule:

- prefer bounded manual reconciliation and cancellation over speculative local state edits
- if exchange state and local state disagree, trust the exchange only after a successful authenticated lookup confirms it

## Logging Expectations

During development, keep these sources of truth separate:

- code and git history for implementation detail
- `docs/decisions.md` for durable project decisions
- application logs for runtime behavior

When debugging the bot, prefer runtime logs first. When explaining why the system is designed a certain way, prefer `docs/decisions.md`.

Current log-correlation rule:

- use `X-Request-ID` from API responses when tracing one request through app logs
- use the job-generated `correlation_id` when tracing one scheduled worker, reconcile, backtest, or startup-sync run
