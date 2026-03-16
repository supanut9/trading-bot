# Features

## Purpose

This document breaks the project into bounded features so implementation, branching, PR review, and merge flow stay controlled.

## Workflow Rule

Before implementation starts, choose the current feature from this document or add a new bounded feature here first.

Branch naming pattern:

- `feature/<name>`

Delivery rule:

- one feature branch should focus on one bounded outcome
- commits inside the branch should stay small and logically grouped
- if the scope grows beyond the feature boundary, stop and define the next feature instead of continuing to expand the current one

## Current Feature Map

### 1. `feature/repo-bootstrap`

Status:

- implemented locally

Scope:

- repository initialization
- `AGENTS.md`
- baseline docs
- Python scaffold
- tooling, hooks, and Make targets

Main outputs:

- repo operating rules
- README and docs skeleton
- FastAPI and worker entrypoints
- lint, format, test, and hook setup

### 2. `feature/persistence-foundation`

Status:

- implemented locally

Scope:

- Docker PostgreSQL setup
- SQLAlchemy base and session setup
- persistence models
- DB initialization path
- schema documentation

Main outputs:

- local database workflow
- initial tables for candles, orders, trades, and positions
- `docs/data-model.md`

### 3. `feature/market-data`

Status:

- implemented locally

Scope:

- candle repository
- market data service
- DB visibility in status endpoint
- basic persistence tests for market data

Main outputs:

- candle persistence API
- stored and queryable recent candles
- runtime status visibility for database readiness

### 4. `feature/strategy-engine`

Status:

- implemented on branch

Scope:

- refine strategy interface
- implement EMA crossover strategy
- add deterministic signal tests

Main outputs:

- concrete EMA strategy module
- signal generation tests
- strategy behavior aligned with `docs/strategies/ema-crossover.md`

### 5. `feature/repo-governance-ci`

Status:

- implemented on branch

Scope:

- main-branch merge policy
- GitHub Actions CI workflow
- branch protection alignment with CI checks

Main outputs:

- documented merge rules for `main`
- automated lint and test checks on pull requests and pushes
- branch protection ready to require CI checks

### 6. `feature/risk-engine`

Status:

- implemented on branch

Scope:

- position sizing rules
- approval and rejection flow
- safety checks before execution

Main outputs:

- risk service
- risk unit tests
- documented approval rules

### 7. `feature/paper-execution`

Status:

- implemented on branch

Scope:

- paper order submission flow
- trade and position updates
- execution logging

Main outputs:

- paper execution service
- order and trade persistence flow
- execution tests

### 8. `feature/worker-orchestration`

Status:

- implemented on branch

Scope:

- end-to-end worker flow
- scheduled execution path
- operational logging improvements

Main outputs:

- worker pipeline from candles to execution
- startup and runtime orchestration
- idempotent signal execution by candle via `client_order_id`
- updated runbook for local operation

### 9. `feature/api-operations`

Status:

- implemented on branch

Scope:

- richer operational endpoints
- positions and trades API
- API-level tests for operations visibility

Main outputs:

- operational API surface for inspection and control

### 10. `feature/market-data-ingestion`

Status:

- implemented on branch

Scope:

- local candle ingestion path
- API-facing batch persistence
- endpoint tests and runbook updates for worker preparation

Main outputs:

- `POST /market-data/candles`
- documented local workflow for loading candles before worker runs
- API tests for candle ingestion

### 11. `feature/backtest-runner`

Status:

- implemented on branch

Scope:

- deterministic backtest application service
- local backtest entrypoint
- tests and runbook updates for historical replay

Main outputs:

- in-memory backtest runner over stored candles
- `make run-backtest`
- tests for backtest outcomes and forced final close

## Next Recommended Feature

`feature/notifications`

Reason:

- the bot can now ingest candles, run workers, expose operations, and backtest strategy behavior
- the next useful operational gap is reporting significant outcomes such as backtest completion, risk rejection, and execution events
