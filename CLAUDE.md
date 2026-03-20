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
make run-web          # Next.js dev server on :3005
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
- **`app/application/services/`** — Orchestration layer. Key services:
  - `OperationalControlService` — main entry point for all API-triggered actions (backtest, worker cycle, market sync, live controls, symbol rules, qualification)
  - `WorkerOrchestrationService` — drives the scheduled execution loop
  - `ExecutionFactory` — selects `PaperExecutionService`, `LiveExecutionService`, or `ShadowExecutionService` based on `execution_mode`
  - `QualificationService` — evaluates 7 evidence-based gates before live promotion
  - `ShadowReportService` — shadow trading quality report (win rate, expectancy, OOS baseline)
  - `BacktestService` — pure in-memory backtest with slippage/fee cost modeling and walk-forward validation
  - `SymbolRulesService` — fetches and caches exchange symbol rules (min qty, step size, min notional)
- **`app/infrastructure/`** — Everything with side effects: SQLAlchemy models/repositories, Binance exchange clients, notification senders.
- **`app/interfaces/api/`** — FastAPI routes and Pydantic schemas. Route handlers translate HTTP into options/request objects and call application services. No business logic in routes.
- **`app/jobs/`** — Scheduled job modules. They only decide *when* to call application services, never *what* to do.
- **`app/config.py`** — `Settings` via pydantic-settings with `@lru_cache`. Settings are cached at startup; `.env` changes require an API restart.

### Execution Modes

`execution_mode` is derived from config, never set directly:

| Mode | Condition | Behaviour |
|---|---|---|
| `paper` | `PAPER_TRADING=true` (default) | Simulated fills, no exchange orders |
| `shadow` | `SHADOW_TRADING_ENABLED=true` | Strategy runs, fills simulated, no real orders, results persisted to `shadow_trades` |
| `live` | `LIVE_TRADING_ENABLED=true`, `PAPER_TRADING=false` | Real signed orders via Binance |

`SHADOW_TRADING_ENABLED` and `LIVE_TRADING_ENABLED` cannot both be true — Settings validator rejects it.

### Key Service Flows

**Worker runtime:**
1. `WorkerOrchestrationService` syncs candles (optional) → runs strategy → risk check → `ExecutionFactory` → paper/shadow/live execution → persist → notify.

**Backtest:**
1. API route → `OperationalControlService.run_backtest()` → loads candles from DB → `BacktestService.run()` (or `run_walk_forward()`) → persists summary to `backtest_runs` → returns result.

**Shadow quality report:**
1. `GET /reports/shadow` → `ShadowReportService.get_quality_report()` → aggregates `shadow_trades` + `shadow_blocked_signals` + latest walk-forward OOS baseline from `backtest_runs`.

**Qualification gates:**
1. `GET /controls/qualification` → `QualificationService.evaluate()` → checks 7 gates: walk-forward run exists, OOS positive return, OOS drawdown < 25%, no overfitting (degradation ≤ 35%), shadow trades ≥ 30, shadow positive expectancy, shadow drawdown < 25%.

### Database

No migrations (no Alembic). Schema is managed with `Base.metadata.create_all()` via `make init-db`. New nullable columns on existing tables are safe; adding non-nullable columns requires a default or manual ALTER.

**Tables:**

| Table | Purpose |
|---|---|
| `candles` | OHLCV market data |
| `orders` | Paper and live order records |
| `trades` | Filled trade records |
| `positions` | Current open position state |
| `audit_events` | Compact event log for control outcomes and notifications |
| `backtest_runs` | Backtest summary history with walk-forward OOS metrics |
| `operator_config` | Persisted runtime defaults (symbol, timeframe, EMA periods, strategy) |
| `runtime_controls` | Persisted operator state (e.g. `live_trading_halted`) |
| `symbol_rules` | Cached exchange symbol filters (min qty, step size, min notional, tick size) |
| `shadow_trades` | Shadow-mode simulated fills with gross/net PnL |
| `shadow_blocked_signals` | Signals blocked by risk or filters in shadow mode |

See `docs/data-model.md` for column intent.

### Next.js Frontend (`web/`)

- Routes: `/` dashboard, `/backtest`, `/controls`, `/reports`, `/runtime`
- Dev server runs on port **3005** (always — set in `Makefile` and `web/.env.local`)
- Backend API base URL is configured in `web/.env.local` as `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
- All data comes from FastAPI. No direct DB or exchange access.
- Uses TanStack Query for data fetching, shadcn/ui + Tailwind for UI.
- Live price on the dashboard connects directly to Binance's public WebSocket (`wss://stream.binance.com`) via `web/hooks/use-binance-ticker.ts`.

### API Surface

| Router | Prefix | Key endpoints |
|---|---|---|
| controls | `/controls` | `POST /worker-cycle`, `POST /backtest`, `POST /market-sync`, `GET /operator-config`, `POST /operator-config`, `POST /live-halt`, `POST /live-reconcile`, `POST /live-cancel`, `GET /symbol-rules`, `POST /symbol-rules/refresh`, `GET /qualification` |
| reports | `/reports` | `GET /backtest-runs`, `GET /recovery`, `GET /notifications`, `GET /audit`, CSV exports |
| operations | `/operations` | `GET /positions`, `GET /trades`, `GET /performance/summary` |
| market-data | `/market-data` | `POST /candles`, `GET /coverage`, `POST /demo-scenarios/{name}` |
| status | `/status` | `GET /` |
| health | `/health` | `GET /` |

## Delivery Rules

- Work feature by feature using `feature/<name>` branches.
- The current feature queue lives in `docs/features.md`. Pick the next planned feature from there; do not invent new scope mid-feature.
- PRs go to `main` only — no direct commits to `main`.
- Labels required on every PR: one `type:*`, at least one `area:*`, one `risk:*`. Assign to `@supanut9`.
- Every PR must have a milestone and must be added to the "Trading Bot Delivery" GitHub project. Run `make pr-check` to validate.
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
- `SHADOW_TRADING_ENABLED` and `LIVE_TRADING_ENABLED` must not both be true.
- Strategy modules must not call exchange APIs or touch the database.
- API routes must not call exchange clients directly.
- Duplicate-order protection (`client_order_id`) must be preserved for all execution paths.
- Exchange symbol rules (min qty, step size, min notional) must be enforced before any live order submission via `validate_and_snap_quantity` in `app/domain/order_rules.py`.
- The `QualificationService` gates must all pass before a strategy is promoted to live. Never bypass the qualification report in live-promotion workflows.
