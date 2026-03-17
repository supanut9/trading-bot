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

### 12. `feature/notifications`

Status:

- implemented on branch

Scope:

- configurable outbound notifications for key runtime outcomes
- worker notifications for executions and risk rejections
- backtest notifications for completion and skipped runs
- notification sender tests and operational documentation

Main outputs:

- notification event formatter and sender abstraction
- optional webhook delivery path
- runtime notifications for worker and backtest workflows

### 13. `feature/operational-controls`

Status:

- implemented on branch

Scope:

- bounded operator-triggered control endpoints
- manual worker cycle execution with current runtime settings
- manual backtest execution with current runtime settings
- tests and docs for safe manual control usage

Main outputs:

- API endpoints for manual worker and backtest triggers
- application service that closes DB sessions before notification delivery
- response models for control outcomes

### 14. `feature/reporting-exports`

Status:

- implemented on branch

Scope:

- export operational data in reviewer-friendly formats
- CSV exports for positions and trades
- CSV export for on-demand backtest summary
- tests and docs for report download behavior

Main outputs:

- `/reports` API endpoints for CSV exports
- export service for operational and backtest report formatting
- API tests for CSV payload shape and headers

### 15. `feature/review-gating`

Status:

- implemented on branch

Scope:

- tighten PR review merge handling
- document review and merge expectations

Main outputs:

- review workflow documentation updates

### 16. `feature/scheduled-jobs`

Status:

- implemented on branch

Scope:

- move recurring runtime behavior into explicit job modules
- keep worker cycle as a scheduled job
- add optional recurring backtest summary execution behind config
- tests and docs for scheduling behavior

Main outputs:

- interval scheduler and job modules under `app/jobs`
- worker entrypoint wired through scheduled jobs instead of inline looping
- optional scheduled backtest summary with safe default disabled

### 17. `feature/review-gating-strict`

Status:

- implemented on branch

Scope:

- refine PR review merge handling
- update workflow docs for stricter review resolution expectations

Main outputs:

- updated merge-gate documentation

### 18. `feature/market-sync-adapter`

Status:

- implemented on branch

Scope:

- add an exchange adapter for recent closed candle sync
- keep exchange-specific fetch logic outside strategy and application decision code
- let the worker optionally sync candles before evaluation
- add tests and runbook coverage for the new sync path

Main outputs:

- Binance market-data adapter
- market-data sync service
- worker integration with safe sync failure handling

### 19. `feature/reporting-ui`

Status:

- implemented on branch

Scope:

- add a human-friendly reporting page without introducing a separate frontend stack
- reuse existing operational and backtest services for dashboard data
- keep CSV exports available for download from the reporting surface
- add API tests and runbook coverage for the dashboard route

Main outputs:

- server-rendered `/reports` dashboard
- reporting dashboard aggregation service
- updated operator docs for HTML and CSV report access

### 20. `feature/notification-hardening`

Status:

- implemented on branch

Scope:

- tighten outbound notification delivery semantics for webhook channels
- extend notifications to market sync outcomes
- keep notification failures non-blocking while making them more explicit
- add tests and runbook coverage for hardened notification behavior

Main outputs:

- webhook sender that treats non-`2xx` responses as delivery failures
- market sync notifications from manual control execution
- updated notification and operational tests

### 21. `feature/execution-audit-feed`

Status:

- implemented on branch

Scope:

- persist compact audit events for control outcomes and notification delivery
- expose recent audit events through the reporting surface
- keep the audit model lightweight and review-oriented rather than building full log ingestion
- add tests and docs for the new audit feed behavior

Main outputs:

- `audit_events` persistence model and application service
- audit recording from control flows and notification delivery
- reporting dashboard and CSV export for recent audit events

### 22. `feature/live-execution-guardrails`

Status:

- implemented on branch

Scope:

- make execution-mode configuration explicit and internally consistent
- refuse explicit live-mode execution safely until a real live executor exists
- expose execution mode through status and operator docs
- add tests for invalid config states and live-mode refusal behavior

Main outputs:

- settings validation for execution-mode flags
- safe worker refusal path for unsupported live execution
- status visibility and tests for execution mode

### 23. `feature/exchange-order-adapter`

Status:

- in progress

Scope:

- introduce a replaceable execution adapter boundary for the worker
- keep paper execution as the default concrete implementation
- route explicit live mode through a deliberate unsupported adapter until exchange order routing exists
- add tests and docs for adapter selection behavior

Main outputs:

- execution factory for worker orchestration
- unsupported live execution adapter
- tests for adapter selection and worker execution-unavailable behavior

## Next Recommended Feature

`feature/live-order-routing`

Reason:

- once the execution adapter boundary exists, the next bounded step is implementing a real exchange-backed live order adapter behind that seam
