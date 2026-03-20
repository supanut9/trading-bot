# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install          # Install Python dependencies
make install-web      # Install Next.js dependencies (yarn)
make install-hooks    # Install pre-commit and pre-push hooks
make db-up            # Start PostgreSQL via Docker Compose
make init-db          # Create tables (run after db-up)
make format           # Auto-format Python (ruff) + web
make lint             # Lint Python (ruff) + web (yarn lint)
make test             # Run pytest + yarn test
make run-api          # FastAPI dev server on :8000
make run-web          # Next.js dev server on :3000
make run-worker       # Background worker (single run)
make run-backtest     # Standalone backtest CLI
```

Run a single Python test: `python -m pytest tests/test_backtest_service.py -v`

Run Python tests only: `python -m pytest`

Always run `make format && make lint && make test` before finishing any implementation work.

## Architecture

The system is a monorepo with a Python backend and a Next.js frontend. They are completely separate — the UI calls FastAPI JSON endpoints and owns no trading logic.

### Python Backend Layers

Dependencies must flow **inward** — outer layers depend on inner layers, never the reverse:

```
interfaces (routes, schemas)
    ↓
application (services, orchestration)
    ↓
domain (strategy, risk, portfolio — pure, no IO)
    ↑
infrastructure (DB, exchange, notifications — depends on domain contracts)
```

- **`app/domain/`** — Pure trading logic. No database sessions, no HTTP, no config access. Strategy modules return `Signal | None`. Risk modules return `RiskDecision`. These must be testable without any infrastructure.
- **`app/application/services/`** — Orchestration. The `OperationalControlService` is the main entry point for API-triggered actions (backtest, worker cycle, market sync, live controls). The `WorkerOrchestrationService` drives the scheduled execution loop.
- **`app/infrastructure/`** — Everything with side effects: SQLAlchemy models/repositories, Binance exchange clients, notification senders.
- **`app/interfaces/api/`** — FastAPI routes and Pydantic schemas. Route handlers translate HTTP into `BacktestRunOptions`/`WorkerCycleOptions`/etc. and call application services. No business logic in routes.
- **`app/jobs/`** — Scheduled job modules. They only decide *when* to call application services, never *what* to do.
- **`app/core/`** — `config.py` (Settings via pydantic-settings), `logger.py` (structured logging with correlation IDs).

### Key Service Relationships

The worker runtime flow:
1. `WorkerOrchestrationService` fetches candles → calls strategy → calls risk → dispatches to `ExecutionFactory` (paper or live) → persists result → notifies.

The backtest flow:
1. API route → `OperationalControlService.run_backtest()` → loads candles from DB → `BacktestService.run()` (pure, in-memory simulation) → persists summary to `backtest_runs` → returns result.

`ExecutionFactory` selects `PaperExecutionService` or `LiveExecutionService` based on config. **Live trading is disabled by default** (`PAPER_TRADING=true`).

### Database

No migrations (no Alembic). Schema is managed with `Base.metadata.create_all()` via `make init-db`. New nullable columns on existing tables are safe; adding non-nullable columns requires a default or manual ALTER.

Six core tables: `candles`, `orders`, `trades`, `positions`, `audit_events`, `backtest_runs`. See `docs/data-model.md` for column intent.

### Next.js Frontend (`web/`)

- Routes: `/` dashboard, `/backtest`, `/controls`, `/reports`, `/runtime`
- All data comes from FastAPI. No direct DB or exchange access.
- Uses TanStack Query for data fetching, shadcn/ui + Tailwind for UI.

## Delivery Rules

- Work feature by feature using `feature/<name>` branches.
- The current feature queue lives in `docs/features.md`. Pick the next planned feature from there; do not invent new scope mid-feature.
- PRs go to `main` only — no direct commits to `main`.
- Labels required on every PR: one `type:*`, at least one `area:*`, one `risk:*`. Assign to `@supanut9`.
- Do not squash merge; use merge commits.

## Documentation Updates

When changing behavior, update the relevant doc alongside the code:

| Change type | Doc to update |
|---|---|
| Architecture or safety decision | `docs/decisions.md` |
| System behavior or capability | `docs/product-spec.md` |
| Startup, deployment, or ops procedure | `docs/runbook.md` |
| New planned or completed feature | `docs/features.md` + `docs/roadmap.md` |
| New strategy | `docs/strategies/<name>.md` first, then implement |

## Safety Constraints

- `PAPER_TRADING=true` and `LIVE_TRADING_ENABLED=false` are the required defaults. Never flip these in tests or tooling.
- Strategy modules must not call exchange APIs or touch the database.
- API routes must not call exchange clients directly.
- Duplicate-order protection (`client_order_id`) must be preserved for all execution paths.
