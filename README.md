# Trading Bot

Paper-trading-first trading bot scaffold designed to be operable by AI agents and humans.

## Goal

Build a reliable trading bot platform with:

- backtesting
- paper trading
- a clean service architecture
- strong safety defaults

## Current Phase

Repository bootstrap and architecture scaffolding.

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

## Operational API

The API now exposes basic operational visibility endpoints:

- `GET /health`
- `GET /status`
- `GET /positions`
- `GET /trades`
- `POST /market-data/candles`

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
