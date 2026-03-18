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

- implemented on `main`

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

- implemented on `main`

Scope:

- Docker PostgreSQL setup
- SQLAlchemy base and session setup
- persistence models
- DB initialization path
- schema documentation

Main outputs:

- local database workflow
- initial tables for candles, orders, trades, positions, and later audit support
- `docs/data-model.md`

### 3. `feature/market-data`

Status:

- implemented on `main`

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

- implemented on `main`

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

- implemented on `main`

Scope:

- main-branch merge policy
- CI workflow and validation expectations
- branch protection alignment with checks and review resolution

Main outputs:

- documented merge rules for `main`
- automated lint and test checks
- branch protection ready workflow

### 6. `feature/risk-engine`

Status:

- implemented on `main`

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

- implemented on `main`

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

- implemented on `main`

Scope:

- end-to-end worker flow
- scheduled execution path
- operational logging improvements

Main outputs:

- worker pipeline from candles to execution
- startup and runtime orchestration
- idempotent signal execution by candle via `client_order_id`

### 9. `feature/api-operations`

Status:

- implemented on `main`

Scope:

- richer operational endpoints
- positions and trades API
- API-level tests for operations visibility

Main outputs:

- operational API surface for inspection and control

### 10. `feature/market-data-ingestion`

Status:

- implemented on `main`

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

- implemented on `main`

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

- implemented on `main`

Scope:

- configurable outbound notifications for key runtime outcomes
- worker notifications for executions and risk rejections
- backtest and later market-sync notifications

Main outputs:

- notification sender abstraction
- optional webhook delivery path
- runtime notifications for worker and backtest workflows

### 13. `feature/operational-controls`

Status:

- implemented on `main`

Scope:

- bounded operator-triggered control endpoints
- manual worker cycle execution with current runtime settings
- manual backtest execution with current runtime settings

Main outputs:

- API endpoints for manual worker and backtest triggers
- bounded control flow that uses current runtime configuration only
- response models for control outcomes

### 14. `feature/reporting-exports`

Status:

- implemented on `main`

Scope:

- export operational data in reviewer-friendly formats
- CSV exports for positions and trades
- CSV export for on-demand backtest summary

Main outputs:

- `/reports` CSV endpoints
- export service for operational and backtest report formatting

### 15. `feature/scheduled-jobs`

Status:

- implemented on `main`

Scope:

- move recurring runtime behavior into explicit job modules
- keep worker cycle as a scheduled job
- add optional recurring backtest summary execution behind config

Main outputs:

- interval scheduler and job modules under `app/jobs`
- worker entrypoint wired through scheduled jobs instead of inline looping

### 16. `feature/market-sync-adapter`

Status:

- implemented on `main`

Scope:

- add an exchange adapter for recent closed candle sync
- let the worker optionally sync candles before evaluation
- keep exchange fetch logic outside strategy modules

Main outputs:

- Binance market-data adapter
- market-data sync service
- worker integration with safe sync failure handling

### 17. `feature/reporting-ui`

Status:

- implemented on `main`

Scope:

- add a human-friendly reporting page without a separate frontend stack
- reuse existing operational and backtest services for dashboard data
- keep CSV exports available from the reporting surface

Main outputs:

- server-rendered `/reports` dashboard
- reporting dashboard aggregation service

### 18. `feature/notification-hardening`

Status:

- implemented on `main`

Scope:

- tighten outbound notification delivery semantics for webhook channels
- extend notifications to market-sync outcomes
- keep failures non-blocking while making them explicit

Main outputs:

- webhook sender that treats non-`2xx` responses as failures
- market-sync notifications from manual control execution

### 19. `feature/execution-audit-feed`

Status:

- implemented on `main`

Scope:

- persist compact audit events for control outcomes and notification delivery
- expose recent audit events through reporting
- keep the audit model lightweight and review-oriented

Main outputs:

- `audit_events` persistence model and application service
- audit recording from control flows and notification delivery
- audit reporting and CSV export

### 20. `feature/live-execution-guardrails`

Status:

- implemented on `main`

Scope:

- make execution-mode configuration explicit and internally consistent
- expose execution mode through status and operator docs
- keep live trading disabled by default and fail safely when unsupported or misconfigured

Main outputs:

- settings validation for execution-mode flags
- safe live-mode refusal or gating behavior
- status visibility and tests for execution mode

### 21. `feature/exchange-order-adapter`

Status:

- implemented on `main`

Scope:

- introduce a replaceable execution adapter boundary for the worker
- keep paper execution as the default concrete implementation
- route explicit live mode through a separate adapter path

Main outputs:

- execution factory for worker orchestration
- paper and live execution adapter boundary

### 22. `feature/live-order-routing`

Status:

- implemented on `main`

Scope:

- add a signed live order client for the configured exchange
- keep validate-only routing available so signed requests can be exercised safely
- wire credentials and request settings through configuration

Main outputs:

- Binance spot order client for signed market-order routing
- factory support for live order clients

### 23. `feature/live-execution-service`

Status:

- implemented on `main`

Scope:

- submit live orders through the signed routing client from the execution boundary
- persist accepted live orders locally without inventing trades or position fills
- keep local runtime state unchanged until explicit fill reconciliation exists

Main outputs:

- live execution service behind the execution factory
- persisted local live orders with exchange order ids

### 24. `feature/live-fill-reconciliation`

Status:

- implemented on `main`

Scope:

- reconcile recent live exchange orders back into local runtime state
- create local trades and position updates only after confirmed remote filled status
- keep reconciliation bounded to recent open live orders and expose it through an operator control

Main outputs:

- live fill reconciliation service
- signed exchange order-status lookup support
- `POST /controls/live-reconcile`

### 25. `feature/live-order-recovery`

Status:

- implemented on `main`

Scope:

- fetch exchange balances for operator visibility
- add scheduled live reconciliation and startup state sync
- expose live cancel, stale-order detection, recovery reporting, and alerting

Main outputs:

- exchange balance visibility
- optional scheduled reconciliation and startup sync
- `POST /controls/live-cancel`
- stale live order visibility and live recovery export
- live-ops alert notifications

### 26. `feature/deployment-hardening`

Status:

- implemented on `main`

Scope:

- document production operations and readiness expectations
- package API and worker for reproducible deployment
- define deploy-time environment baselines and smoke checks

Main outputs:

- production operations runbook
- deployable runtime packaging
- deployment environment baseline
- bounded post-deploy smoke-check workflow

### 27. `feature/runtime-reliability`

Status:

- implemented on `main`

Scope:

- improve structured logging and startup validation for unattended runtime behavior
- expose latest read-only exchange price through existing operator surfaces
- keep the work focused on reliability and visibility rather than new trading behavior

Main outputs:

- stronger runtime diagnostics
- clearer startup validation failures
- latest price visibility in status, reports, and console

### 28. `feature/operator-console-and-performance`

Status:

- implemented on `main`

Scope:

- add an operator-facing page inside the FastAPI app for paper-trading workflows
- provide deterministic demo scenarios for local verification
- extend the console with richer live-capable controls
- add session summary, performance analytics, and equity-curve reporting

Main outputs:

- `GET /console`
- `POST /market-data/demo-scenarios/{scenario_name}`
- richer console controls for market sync, backtest, reconcile, and cancel
- reporting summary cards
- `GET /performance/summary`
- `GET /performance/daily.csv`
- `GET /performance/equity.csv`
- `/reports` equity-curve section

### 29. `feature/live-order-state-hardening`

Status:

- implemented on branch

Scope:

- normalize live-order states into one canonical local model
- prevent contradictory status transitions across submit, reconcile, and cancel flows
- surface uncertain exchange outcomes as explicit operator-review state

Main outputs:

- shared live-order state resolution and transition rules
- canonical statuses such as `open`, `partially_filled`, `filled`, `canceled`, `rejected`, and `review_required`
- recovery export fields for `requires_operator_review` and `next_action`
- live reconcile summaries that count review-required orders

### 30. `feature/live-risk-safety-controls`

Status:

- implemented on branch

Scope:

- add explicit live-entry safety gates beyond credential presence
- bound live entry by halt flag, max order notional, and max position quantity
- expose live safety posture through the status surface

Main outputs:

- config-backed `LIVE_TRADING_HALTED`, `LIVE_MAX_ORDER_NOTIONAL`, and `LIVE_MAX_POSITION_QUANTITY`
- live risk rejections for halted entry, oversized notional, and oversized position quantity
- status visibility for live safety posture and configured limits

### 31. `feature/operator-recovery-timeline`

Status:

- implemented on branch

Scope:

- promote live recovery into a readable operator workflow inside the reporting UI
- show unresolved live orders as a recovery queue with explicit next actions
- show recent recovery events as a compact timeline instead of one-line summary text only

Main outputs:

- `/reports` recovery queue with `review_required` and `next_action` visibility
- `/reports` recovery timeline over recent live reconcile and live cancel events

### 32. `feature/observability-and-deploy-hardening`

Status:

- implemented on branch

Scope:

- strengthen unattended-runtime logging around live safety posture
- tighten post-deploy smoke checks so they validate the configured live safety state
- keep the feature focused on diagnostics and deploy verification rather than new trading behavior

Main outputs:

- runtime and scheduled-job logs that include `live_safety_status`
- smoke checks that validate live safety fields and startup-sync readiness for live worker mode

### 33. `feature/live-operator-halt-control`

Status:

- implemented on branch

Scope:

- promote live-entry halt from startup-only configuration into an explicit operator control
- persist the halt state so API, console, and worker execution use the same value
- keep the feature bounded to live-entry halt without widening into broader live control mutation

Main outputs:

- `runtime_controls` persistence for `live_trading_halted`
- `POST /controls/live-halt`
- console actions to halt or resume live entry
- worker and status surfaces that resolve live halt from persisted operator state first

### 34. `feature/recovery-audit-timeline`

Status:

- implemented on branch

Scope:

- enrich the reporting recovery timeline with audit payload context
- keep the feature read-only and focused on operator visibility
- avoid overlapping with later filtering or search work

Main outputs:

- parsed recovery event context for live reconcile and live cancel audit events
- recovery timeline context column in `/reports`
- live recovery CSV fields that include the latest recovery event context

### 35. `feature/live-order-duplication-guardrails`

Status:

- implemented on branch

Scope:

- prevent duplicate live submissions while an unresolved same-side live order is already open
- keep the guardrail at live submission time rather than adding broader reconciliation logic
- surface the rejection through existing worker and control responses

Main outputs:

- live execution rejection for same-side unresolved live orders on the same market
- worker and controls responses that return `duplicate_live_order`
- test coverage for live execution, worker orchestration, and control API duplicate-order behavior

### 36. `feature/recovery-filters-and-search`

Status:

- implemented on branch

Scope:

- add read-only recovery filtering to the reporting deck and recovery CSV export
- narrow operator review to the current incident instead of the whole recovery backlog
- avoid overlapping with broader observability or log-correlation work

Main outputs:

- `/reports` recovery filter form and query parameters
- filtered recovery queue and recovery timeline views
- `live-recovery.csv` export that preserves the same active recovery filters

### 37. `feature/runtime-log-correlation`

Status:

- implemented on branch

Scope:

- add a shared correlation id to runtime logs without introducing a separate log storage system
- propagate request ids through API handling and generated run ids through scheduled worker jobs
- keep the change focused on log traceability rather than building new operator surfaces

Main outputs:

- log lines that include `correlation_id`
- API middleware that preserves or generates `X-Request-ID`
- scheduled worker, reconcile, backtest, and startup-sync jobs that log under one run id each

### 38. `feature/notification-correlation-context`

Status:

- implemented on branch

Scope:

- carry the active runtime correlation id into notification events and delivery audit payloads
- keep the change bounded to payload traceability without adding new channels or alert rules
- preserve compatibility when notifications are emitted outside a correlated runtime context

Main outputs:

- notification payloads with top-level `correlation_id`
- webhook and log notification senders that emit the same correlation id already present in runtime logs
- tests covering correlated and non-correlated notification delivery paths

### 39. `feature/notification-delivery-reporting`

Status:

- implemented on branch

Scope:

- expose recent notification-delivery audit rows in the reporting deck
- add a dedicated notification-delivery CSV export without changing notification write behavior
- keep the feature read-only and limited to existing audit data

Main outputs:

- notification-delivery summary cards and recent-deliveries table in `/reports`
- `GET /reports/notification-delivery.csv`
- export filtering by delivery status, channel, and related event type

### 40. `feature/notification-delivery-filters`

Status:

- implemented on branch

Scope:

- add notification-delivery filters to the reporting dashboard
- preserve the active notification-delivery filter slice in the CSV export link
- keep the feature bounded to dashboard/read-only filtering without changing audit storage

Main outputs:

- `/reports` notification-delivery filter form and summary
- filtered notification-delivery panel in the reporting deck
- notification-delivery CSV link that preserves the active filter query string

### 41. `feature/audit-report-filters`

Status:

- implemented on branch

Scope:

- add generic audit filters to the reporting dashboard
- preserve the active audit filter slice in the audit CSV export link
- keep the feature bounded to read-only filtering without changing audit writes

Main outputs:

- `/reports` audit filter form and summary
- filtered recent-audit table in the reporting deck
- audit CSV link that preserves active event, status, source, and search filters

### 42. `feature/audit-report-columns`

Status:

- implemented on branch

Scope:

- expose richer audit metadata directly in the generic audit reporting slice
- keep the feature read-only and reuse existing persisted audit fields plus payload correlation ids
- avoid widening into new audit writes or new persistence models

Main outputs:

- `/reports` recent-audit table columns for market, delivery, and correlation metadata
- `GET /reports/audit.csv` column for explicit `correlation_id`
- operator visibility that no longer depends on reading raw payload JSON for common metadata

## Current Recommended Queue

These are the next bounded features after the current `main` baseline:

1. `feature/audit-report-columns`

Current next feature:

- `feature/audit-report-columns`
