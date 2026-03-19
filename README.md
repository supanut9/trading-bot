# Trading Bot

Paper-trading-first trading bot scaffold designed to be operable by AI agents and humans.

## Goal

Build a reliable trading bot platform with:

- backtesting
- paper trading
- a clean service architecture
- strong safety defaults

## Current Phase

Operator-facing paper-trading platform with backtesting, reporting, performance analytics, deployment hardening, and live-readiness groundwork.

## V1 Scope

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL via Docker for local development
- one exchange adapter
- one runtime execution strategy plus a configurable backtest rule builder
- paper trading only

## Non-Goals For V1

- live trading by default
- leverage or futures support
- multiple exchanges
- microservices

## Important Files

- `AGENTS.md`
- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/data-model.md`
- `docs/features.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/testing.md`

## Commands

Use the `Makefile` once dependencies are installed:

- `make install`
- `make install-web`
- `make install-hooks`
- `make init-db`
- `make db-up`
- `make db-down`
- `make db-logs`
- `make format`
- `make lint`
- `make test`
- `make pr-check`
- `make run-api`
- `make run-web`
- `make run-worker`
- `make run-backtest`
- `make docker-build`
- `make docker-run-api`
- `make docker-run-worker`
- `make smoke-check-api`
- `make smoke-check-worker`

## Operational API

The API now exposes basic operational visibility endpoints:

- `GET /health`
- `GET /status`
- `GET /positions`
- `GET /performance/summary`
- `GET /performance/daily.csv`
- `GET /performance/equity.csv`
- `GET /trades`
- `POST /market-data/candles`
- `POST /market-data/demo-scenarios/{scenario_name}`
- `POST /controls/market-sync`
- `POST /controls/worker-cycle`
- `POST /controls/backtest`
- `POST /controls/live-halt`
- `POST /controls/live-reconcile`
- `POST /controls/live-cancel`
- `GET /reports/positions.csv`
- `GET /reports/trades.csv`
- `GET /reports/backtest-summary.csv`
- `GET /reports/recovery`
- `GET /reports/audit.csv`
- `GET /reports/notification-delivery.csv`
- `GET /reports/live-recovery.csv`

## Operator UI

The new operator UI scaffold lives in `web/` and runs as a separate Next.js app inside this repo.

Local frontend workflow:

```bash
make install-web
make run-api
make run-web
```

Default local URLs:

- FastAPI: `http://127.0.0.1:8000`
- Next.js operator UI: `http://127.0.0.1:3000`

Current Next.js routes:

- `/`
- `/backtest`
- `/controls`
- `/reports`
- `/runtime`

Frontend environment:

- copy `web/.env.local.example` to `web/.env.local` if you need to point the UI at a different API base URL
- allow additional browser origins for the API with `FRONTEND_ORIGINS`

## Notifications

Notifications are optional and default to disabled.

Available channels:

- `none`
- `log`
- `webhook`

Useful local test:

```bash
NOTIFICATION_CHANNEL=log make run-worker
```

## Git Hooks

Install repository hooks after dependencies are installed:

```bash
make install-hooks
```

Configured hooks:

- `pre-commit`: whitespace cleanup, file ending fixes, TOML/YAML checks, `ruff format`, `ruff --fix`
- `pre-push`: `pytest`

## Local Database

Local PostgreSQL runs through Docker Compose.

```bash
make db-up
```

Initialize tables:

```bash
make init-db
```

Default connection string:

```bash
postgresql+psycopg://trading_bot:trading_bot@127.0.0.1:5434/trading_bot
```

SQLite can still be used as a fallback by overriding `DATABASE_URL`.
If `5434` is also occupied locally, set `POSTGRES_HOST_PORT` before `make db-up` and keep `DATABASE_URL` aligned with the same port.

## Market Sync

`POST /controls/market-sync` supports explicit per-run market selection plus two sync modes:

- append mode: fetch recent candles and store only candles newer than the latest one already in the database
- backfill mode: fetch recent candles and upsert the full returned window so older missing candles can be loaded into an existing database

When `symbol` and `timeframe` are omitted, the control uses the effective operator runtime
defaults. When they are supplied, the sync runs against those values without changing persisted
runtime defaults.

## Deployment Packaging

The repository now includes a single runtime image for API or worker deployment.

Build the image:

```bash
make docker-build
```

Run the API container:

```bash
make docker-run-api
```

Run the worker container:

```bash
make docker-run-worker
```

Container runtime selection uses `APP_RUNTIME`:

- `api`
- `worker`
- `backtest`

Operator UI entrypoint:

- Next.js UI at `http://127.0.0.1:3000` during local development

## Deployment Environment Baseline

Use the example files by role instead of reusing the local template directly:

- `.env.example`: minimal local overrides
- `.env.deploy.api.example`: minimal API deployment baseline
- `.env.deploy.worker.example`: minimal worker deployment baseline

Deployment guidance:

- keep API and worker env files separate
- keep defaults in code and only override values that differ for the target runtime
- keep secrets out of the example files and inject them at deploy time
- keep live trading disabled unless the live readiness checklist in `docs/runbook.md` has been completed

## Post-Deploy Smoke Check

Use the bounded smoke checks after deploy or rollback:

- `make smoke-check-api`
- `make smoke-check-worker`

These checks are non-destructive. They verify health, status, database reachability, and configuration alignment without triggering a worker cycle.

## Runtime Reliability

Runtime startup now validates deployment-critical settings before API, worker, or backtest execution continues.

Current startup guarantees:

- non-local runtimes must not use SQLite
- non-local API runtimes must not bind to loopback hosts
- webhook notification mode requires `NOTIFICATION_WEBHOOK_URL`
- live worker runtimes require `STARTUP_STATE_SYNC_ENABLED=true`

## Live Price Visibility

The current status and reporting surfaces now include the latest read-only exchange price when it is available.

Use:

- `GET /status`
- the Next.js operator UI

This price is informational only. Strategy and execution behavior remain candle-based.
