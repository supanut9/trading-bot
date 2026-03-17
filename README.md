# Trading Bot

Paper-trading-first trading bot scaffold designed to be operable by AI agents and humans.

## Goal

Build a reliable trading bot platform with:

- backtesting
- paper trading
- a clean service architecture
- strong safety defaults

## Current Phase

Core trading flow with backtesting, paper execution, operational controls, reporting exports, and review gating.

## V1 Scope

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL via Docker for local development
- one exchange adapter
- one strategy
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
- `make run-worker`
- `make run-backtest`
- `make docker-build`
- `make docker-run-api`
- `make docker-run-worker`

## Operational API

The API now exposes basic operational visibility endpoints:

- `GET /health`
- `GET /status`
- `GET /positions`
- `GET /trades`
- `POST /market-data/candles`
- `POST /controls/worker-cycle`
- `POST /controls/backtest`
- `GET /reports/positions.csv`
- `GET /reports/trades.csv`
- `GET /reports/backtest-summary.csv`

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
postgresql+psycopg://trading_bot:trading_bot@127.0.0.1:5432/trading_bot
```

SQLite can still be used as a fallback by overriding `DATABASE_URL`.

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

## Deployment Environment Baseline

Use the example files by role instead of reusing the local template directly:

- `.env.example`: local development defaults
- `.env.deploy.api.example`: API deployment baseline
- `.env.deploy.worker.example`: worker deployment baseline

Deployment guidance:

- keep API and worker env files separate
- keep secrets out of the example files and inject them at deploy time
- keep live trading disabled unless the live readiness checklist in `docs/runbook.md` has been completed
