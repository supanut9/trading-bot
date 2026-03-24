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

### 14. `feature/rule-builder-backtest`

Status:

- in progress on `feature/rule-builder-backtest`

Scope:

- bounded `rule_builder` strategy for backtest only
- reusable indicator helpers for configurable rule evaluation
- control API support for structured backtest rule payloads
- strategy docs and tests for rule-builder behavior

Main outputs:

- rule-builder strategy module with shared, buy, and sell rule groups
- configurable backtest request and response payloads for rule sets
- backtest-only strategy selection without changing worker runtime strategy

### 14. `feature/operator-ui-foundation`

Status:

- completed

Scope:

- add an in-repo Next.js app under `web/`
- define frontend stack and local development workflow
- establish the initial API consumption pattern for operator pages
- migrate the first reporting and console slices away from FastAPI-rendered HTML

Main outputs:

- documented frontend architecture and stack choice
- initial Next.js app scaffold
- shared UI shell for operator-facing screens
- a bounded migration path from `/console` and `/reports` HTML to API-backed pages

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

### 21. `feature/agent-workflow-alignment`

Status:

- in progress on `main`

Scope:

- align repo agent guidance with the current Codex structure
- keep durable repository constraints in `AGENTS.md`
- move reusable repo workflows into `.agents/skills`
- document when to use repo skills versus Codex-specific custom agents
- add bounded project-specific custom subagent profiles under `.codex/agents`

Main outputs:

- shortened `AGENTS.md`
- repo skills under `.agents/skills`
- custom agents under `.codex/agents`
- `docs/agent-workflow.md`
- README guidance for agent-facing repo structure

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

- implemented on `main`

Scope:

- expose richer audit metadata directly in the generic audit reporting slice
- keep the feature read-only and reuse existing persisted audit fields plus payload correlation ids
- avoid widening into new audit writes or new persistence models

Main outputs:

- `/reports` recent-audit table columns for market, delivery, and correlation metadata
- `GET /reports/audit.csv` column for explicit `correlation_id`
- operator visibility that no longer depends on reading raw payload JSON for common metadata

### 43. `feature/production-readiness-boundary`

Status:

- implemented on branch

Scope:

- define the explicit production target as deployed paper trading, not live trading by default
- document the remaining gap between deployable paper operation and live-capable operation
- keep the feature bounded to launch criteria, readiness checks, and operational decision points rather than new trading behavior

Main outputs:

- a documented go-live checklist for production paper deployment
- an explicit live-trading non-readiness statement and gap list
- aligned roadmap and product-spec language for the current production boundary

### 44. `feature/interactive-backtest-console`

Status:

- merged to `main`

Scope:

- turn console backtests from a fixed one-click action into a parameterized operator workflow
- let operators choose market and strategy inputs that already fit the current single-strategy architecture
- make the backtest result easier to understand without building a separate frontend stack or strategy-management subsystem

Main outputs:

- `/console` backtest form fields for symbol, timeframe, strategy, and EMA parameters
- clearer backtest result rendering with explicit run inputs and outcome summary
- bounded API-facing backtest options that reuse the existing service layer

### 45. `feature/runtime-operator-config`

Status:

- merged to `main`

Scope:

- move paper-runtime market and strategy defaults out of env-only control and into bounded persisted operator controls
- let operators update the active symbol, timeframe, and EMA periods from bounded operator controls
- make worker cycle, market sync, status, and default backtest behavior resolve the same effective runtime config

Main outputs:

- persisted operator-runtime defaults for strategy, symbol, timeframe, and EMA periods
- `/controls/operator-config` read and write endpoints
- shared use of those defaults across paper actions

### 46. `feature/operator-ui-foundation`

Status:

- merged to `main`

Scope:

- add an in-repo Next.js application under `web/`
- define the default frontend stack for operator-facing UI
- establish API-backed UI patterns for dashboard, console, and reporting slices
- migrate UI incrementally without moving trading logic out of Python

Main outputs:

- initial Next.js app scaffold and local workflow
- documented `Next.js + TypeScript + Tailwind + shadcn/ui + TanStack Query` stack choice
- a shared operator shell for dashboard and reporting pages
- a bounded migration path away from FastAPI-rendered HTML pages

### 47. `feature/operator-market-sync-controls`

Status:

- merged to `main`

Scope:

- add a real Next.js controls page for operator-triggered market sync
- allow the bounded market-sync control API to accept explicit symbol and timeframe inputs
- keep sync execution read/write bounded to candle storage without widening trading behavior

Main outputs:

- `/controls/market-sync` support for explicit market selection in the request payload
- Next.js controls page with symbol, timeframe, limit, and backfill inputs
- result panel and safe operator guidance for append vs backfill usage

### 48. `feature/operator-reporting-ui`

Status:

- merged to `main`

Scope:

- add a real Next.js reporting route for analytics and exports
- reuse existing performance analytics and CSV export APIs
- replace the old backend reporting UX with a richer API-backed page

Main outputs:

- `/reports` route in `web/`
- performance summary, equity-curve, and daily-rollup visibility in Next.js
- direct CSV export links for operational and performance datasets

### 49. `feature/operator-runtime-config-ui`

Status:

- merged to `main`

Scope:

- replace the runtime placeholder route with a real Next.js runtime-defaults editor
- reuse the existing `/controls/operator-config` API for read and write behavior
- keep runtime-default updates bounded to persisted paper defaults without widening execution logic

Main outputs:

- `/runtime` route in `web/` for runtime defaults
- form editing for strategy, symbol, timeframe, fast period, and slow period
- result feedback for persisted runtime-default updates

### 50. `feature/worker-cycle-ui`

Status:

- merged to `main`

Scope:

- add a real operator-triggered worker-cycle action to the Next.js controls surface
- reuse the existing bounded `POST /controls/worker-cycle` API
- keep execution feedback explicit without widening worker orchestration behavior

Main outputs:

- worker-cycle action panel in the Next.js controls route
- result feedback for executed, skipped, or duplicate worker outcomes
- dashboard refresh after a successful worker action

### 51. `feature/operator-backtest-ui`

Status:

- merged to `main`

Scope:

- add a real Next.js backtest route for operator-triggered replay analysis
- reuse the existing bounded `POST /controls/backtest` API and keep business logic in Python
- keep the UX preset-first while exposing structured rule-builder options for bounded experimentation

Main outputs:

- `/backtest` route in `web/`
- parameterized backtest form for market, strategy, EMA, and starting-equity inputs
- preset-first rule-builder strategy selection with clear result feedback, charting, and execution detail

### 52. `feature/live-ops-ui`

Status:

- merged to `main`

Scope:

- expose bounded live-operation controls in the Next.js operator UI
- reuse the existing live halt, reconcile, and cancel control APIs
- keep live safety policy, validation, and execution logic in the Python backend

Main outputs:

- live posture snapshot inside the controls route
- operator-triggered live halt and resume actions
- explicit live reconcile and cancel actions with result feedback

### 53. `feature/recovery-reporting-ui`

Status:

- merged to `main`

Scope:

- bring live recovery reporting into the Next.js reporting surface
- add a bounded JSON reporting endpoint over existing recovery services
- preserve filtered CSV export workflow while improving scan-friendly operator visibility

Main outputs:

- `/reports/recovery` JSON endpoint
- recovery queue, stale-order, and recovery-timeline panels in the reporting route
- read-only recovery filters with matching filtered CSV export links

### 54. `feature/notification-reporting-ui`

Status:

- merged to `main`

Scope:

- expose notification-delivery reporting in the Next.js reporting route
- add a bounded JSON endpoint over the existing notification-delivery audit slice
- preserve filtered CSV export behavior while making delivery failures easier to inspect in-browser

Main outputs:

- `/reports/notifications` JSON endpoint
- notification-delivery summary cards and recent-delivery table in the reporting route
- read-only notification filters with matching filtered CSV export links

### 55. `feature/audit-reporting-ui`

Status:

- merged to `main`

Scope:

- expose generic audit reporting in the Next.js reporting route
- add a bounded JSON endpoint over the existing recent-audit slice
- preserve filtered CSV export behavior while making cross-workflow audit review easier in-browser

Main outputs:

- `/reports/audit` JSON endpoint
- generic audit summary, filter form, and recent-audit table in the reporting route
- read-only audit filters with matching filtered CSV export links

### 56. `feature/rule-builder-editor-ui`

Status:

- merged to `main`

Scope:

- turn the current preset-first rule-builder backtest path into a real bounded editor
- keep the rule-builder strategy backtest-only and reuse the existing backtest control API
- surface validation feedback clearly without introducing a new strategy-management backend

Main outputs:

- editable `shared_filters`, `buy_rules`, and `sell_rules` groups in the Next.js backtest route
- condition add, remove, and logic controls for the existing rule-builder indicators
- clearer validation feedback when a submitted rule payload is invalid

### 57. `feature/backtest-run-history`

Status:

- implemented on `main`

Scope:

- persist summary-level backtest runs for later review
- make recent replay outcomes reviewable without rerunning immediately
- keep the feature bounded to summary history rather than full execution-ledger persistence

Main outputs:

- stored recent backtest runs with inputs, summary metrics, and serialized rules
- read-only recent-run JSON and CSV reporting
- backtest UI hydration from a selected prior run

### 58. `feature/market-data-coverage-readiness`

Status:

- implemented on `main`

Scope:

- expose historical candle coverage and replay readiness before a backtest runs
- keep the feature read-only and focused on operator visibility rather than repair automation
- reuse current market and strategy inputs to explain whether the dataset is sufficient

Main outputs:

- read-only coverage and readiness API for exchange, symbol, timeframe, and selected replay shape
- backtest and market-sync visibility into stored range, candle count, and readiness status
- operator guidance when more history is needed before replay

### 59. `feature/realistic-backtest-cost-modeling`

Status:

- implemented on `main`

Scope:

- add slippage and fee deductions to the backtest engine so reported PnL reflects real trading costs
- without this, backtest metrics overstate performance and all downstream qualification thresholds are based on inflated evidence
- keep the feature bounded to cost modeling in the existing backtest path rather than adding new strategies

Main outputs:

- configurable slippage percentage and taker fee rate applied per fill in backtest simulation
- cost-adjusted PnL, net return, and total fees paid surfaced in backtest summary and CSV exports
- updated rule-builder presets with sensible default cost assumptions for BTC/USDT on Binance

### 60. `feature/walk-forward-validation`

Status:

- implemented on `main`

Scope:

- split historical candle data into an in-sample optimization window and a separate out-of-sample test window
- a strategy that only passes in-sample is curve-fit and will likely lose money on live data
- keep the feature bounded to validation reporting rather than automated parameter search

Main outputs:

- walk-forward backtest mode with configurable in-sample and out-of-sample date splits
- side-by-side in-sample versus out-of-sample comparison in backtest results (win rate, expectancy, drawdown, Sharpe)
- overfitting warning when out-of-sample performance degrades more than a configurable threshold versus in-sample
- walk-forward results stored in backtest run history alongside standard replay results

### 61. `feature/signal-quality-improvements`

Status:

- implemented on `main` (PR #84)

Scope:

- add RSI overbought/oversold filters and volume confirmation to the EMA crossover strategy
- the base EMA crossover generates too many false signals in ranging or low-volume markets, which erodes edge through repeated small losses and fees
- keep the feature bounded to the rule-builder indicator set and the existing strategy layer

Main outputs:

- RSI filter bounds configurable in the rule-builder (e.g. only buy when RSI < 65, only sell when RSI > 35)
- volume confirmation threshold configurable in the rule-builder (require volume above N-period average at signal)
- updated default presets incorporating cost-effective filter combinations based on walk-forward evidence
- signal quality metrics in backtest reports: raw signal count, filter rejection rate, and net signal count

### 62. `feature/exchange-rule-enforcement`

Status:

- implemented on `main` (PR #85)

Scope:

- enforce exchange symbol filters before any real-money submission path is allowed
- normalize quantity, price, notional, and precision handling against exchange metadata
- keep the feature bounded to pre-submit correctness rather than enabling live trading by itself

Main outputs:

- exchange trading-rule fetch and persistence for the configured symbol
- order-sizing validation for min quantity, min notional, step size, and tick size
- explicit reject reasons when a proposed live order violates exchange rules

### 63. `feature/shadow-strategy-runtime`

Status:

- implemented on `main` (PR #86)

Scope:

- run the production strategy in shadow mode against live market data without submitting exchange orders
- track whether live signal behavior and simulated fill outcomes match walk-forward out-of-sample expectations
- keep the feature bounded to validation and observability rather than capital deployment

Main outputs:

- shadow-trading execution mode with cost-model-aware simulated fills
- persisted shadow signal history with entry price, simulated exit, gross and net PnL per trade
- signal quality drift report: shadow win rate, expectancy, and drawdown versus walk-forward OOS baseline
- blocked-signal log showing which filter rules are preventing entries in live conditions

### 64. `feature/strategy-qualification-gates`

Status:

- implemented on `feature/strategy-qualification-gates`

Scope:

- define the minimum evidence required before a strategy is allowed to touch real money
- gates must be based on cost-adjusted, out-of-sample, and shadow results rather than raw in-sample backtest metrics
- make go or no-go decisions operator-visible and auditable

Main outputs:

- qualification checklist with explicit pass/fail thresholds:
  - positive expectancy after slippage and fees (in-sample and OOS)
  - OOS Sharpe ratio above 0.5 annualized
  - OOS max drawdown below 25%
  - OOS net return within 35% of in-sample net return (overfitting guard)
  - shadow win rate and expectancy within 20% of OOS backtest baseline
  - at least 30 completed shadow trades before promotion is allowed
- operator-facing qualification report with per-gate pass/fail and evidence summary
- hard block on live mode enablement until all gates pass

### 65. `feature/live-risk-hard-gates`

Status:

- implemented on `main` (PR #90, #94)

Scope:

- harden risk controls from paper-safe defaults into real-money blocking gates
- add fail-closed behavior for live loss, exposure, and repeated-error conditions
- keep the feature bounded to capital protection rather than rollout workflow

Main outputs:

- live-only max daily loss, max weekly loss, and max concurrent exposure limits
- consecutive-loss and repeated-reject auto-halt triggers
- persisted live kill switch and machine-readable halt reasons

### 66. `feature/smart-order-execution`

Status:

- implemented on `main` (PR #91)

Scope:

- submit live orders as limit orders at a configurable offset from signal price to reduce fill costs
- fall back to market order after a configurable timeout only if the limit has not filled
- track actual fill price versus signal price per order so slippage is measured against modeled assumptions
- keep the feature bounded to order routing behavior without changing strategy or risk logic

Main outputs:

- limit-order mode with configurable price offset and timeout in environment config
- fill-price versus signal-price delta recorded per live order for slippage tracking
- fee-aware pre-submit check that blocks orders where expected gross profit does not exceed estimated round-trip fee cost
- slippage and fee summary in live reporting alongside realized PnL

### 67. `feature/validate-only-live-orders`

Status:

- implemented on `main` (PR #92)

Scope:

- prove signed exchange submission works end to end before any money is risked
- use exchange test or validate-only paths where available
- keep the feature bounded to submission correctness rather than actual fills

Main outputs:

- validate-only live order control path
- audit and reporting for exchange acceptance or rejection of signed payloads
- runbook steps for credentials, permissions, and pre-live connectivity verification

### 68. `feature/live-ledger-reconciliation-hardening`

Status:

- implemented on `main` (PR #93)

Scope:

- make the local order, trade, fee, and position ledger trustworthy under partial fills and exchange lag
- strengthen restart and replay safety for unresolved live state
- keep the feature bounded to correctness of live state rather than new strategy behavior

Main outputs:

- partial-fill-aware order and position reconciliation
- fee and average-price normalization from exchange fills
- stronger idempotency and drift detection between exchange state and local ledger

### 69. `feature/production-secrets-and-ops-hardening`

Status:

- implemented on `main` (PR #96)

Scope:

- close the operational gaps that make real-money mode unsafe even when the code path exists
- harden secrets, backups, alert routing, and recovery drills before capital is deployed
- keep the feature bounded to runtime safety posture rather than strategy logic

Main outputs:

- documented secret-rotation and restricted-key workflow
- enforced backup and restore checks for live-capable deployments
- operator drills for restart, rollback, reconciliation failure, and alert escalation

### 70. `feature/canary-live-rollout`

Status:

- implemented on `main` (PR #97)

Scope:

- enable real-money execution for one approved strategy, one symbol, and tightly bounded capital
- keep rollout deliberately narrow so failures are contained and observable
- require explicit operator promotion through paper → shadow → qualification → canary live

Main outputs:

- canary live mode with very small configured capital limits
- promotion checklist from paper to shadow to qualification gates to canary live
- live execution reporting for fills, actual slippage, realized PnL, and halt reasons

### 71. `feature/live-incident-auto-halt`

Status:

- implemented on `main` (PR #98)

Scope:

- automatically stop new live entries when runtime state becomes unreliable
- favor fail-closed behavior over attempted self-recovery with uncertain exchange state
- keep the feature bounded to incident containment rather than incident resolution automation

Main outputs:

- auto-halt on reconciliation drift, stale balances, repeated exchange errors, or missing market data
- structured incident reasons surfaced in status, audit, and notifications
- operator workflow for investigation, acknowledgment, and controlled resume

### 72. `feature/live-performance-review-loop`

Status:

- completed

Scope:

- compare live results against walk-forward OOS expectations and shadow baseline to detect real edge decay
- identify whether underperformance is due to strategy degradation, execution cost overshoot, or market regime change
- define explicit criteria for keep-running, reduce-risk, pause-and-rework, or halt decisions

Main outputs:

- live-versus-shadow-versus-walk-forward-OOS comparison reporting with cost-adjusted metrics
- monthly operator review template covering win rate, expectancy, slippage, drawdown, and regime context
- strategy health indicators: slippage vs model, OOS drift, signal frequency changes, and consecutive-loss trend

Implemented on `main`:

- `LivePerformanceReviewService` with normalized live, shadow, and walk-forward OOS comparison metrics
- modeled slippage baseline comparison in review health indicators
- operator-readable root-cause and regime context in API and reporting UI
- persisted operator review decision support
- explicit connections from review outcomes into runtime promotion and strategy iteration workflows
- service tests and a monthly review template document

### 73. `feature/live-readiness-gate`

Status:

- completed

Scope:

- compute one explicit operator-visible readiness report before any live resume or promotion path is trusted
- reuse existing qualification, reconciliation, stale-order, runtime-control, and live-risk signals instead of adding a second safety workflow
- keep the feature bounded to live enablement and operator visibility rather than new execution or sizing behavior

Main outputs:

- `LiveReadinessService` that evaluates named readiness checks and returns one report with `ready`, `degraded`, or `blocked` status
- read-only API surface for live readiness with per-check pass/fail detail and blocking reasons
- hard refusal of live resume or enable actions when readiness is blocked, while preserving reconcile, cancel, and reporting controls
- startup and status visibility that summarize the active live-readiness posture for operators
- audit and structured logging for readiness failures and denied live enablement attempts

Suggested readiness checks:

- live trading explicitly enabled in configuration
- runtime live halt is not active
- exchange credentials are present
- exchange rule metadata is available for the configured symbol
- qualification gates are passing
- startup sync and recent reconciliation state are healthy
- no unresolved stale live order or recovery condition requires manual operator action
- live max order notional and max position quantity are configured
- duplicate live-order protection remains active

### 74. `feature/strategy-iteration-workflow`

Status:

- completed

Scope:

- close the feedback loop when live results fall below walk-forward expectations
- define how the strategy is re-validated on fresh data, adjusted, and promoted back through shadow before re-enabling live
- keep the feature bounded to the existing one-strategy, one-symbol scope rather than opening multi-strategy management

Main outputs:

- parameter re-optimization workflow on the most recent candle window with walk-forward revalidation
- operator-driven promotion path from halt-for-rework back through walk-forward, shadow, and qualification gates
- changelog of strategy versions with their qualification evidence and live outcome summaries

Current completion slice:

- include persisted operator review-decision state in the iteration checklist
- include runtime promotion rollback or alignment steps when the current stage is too aggressive for the latest review outcome
- keep full live re-promotion blocked in the iteration plan until the review cycle returns to `keep_running`

### 75. `feature/futures-leverage-backtest`

Status:

- implemented on `main`

Scope:

- add leverage and margin-mode parameters to the backtest engine
- simulate realistic liquidation events when price breaches the maintenance-margin threshold
- surface leverage, margin mode, and liquidation count in backtest results and UI
- keep the feature bounded to backtest simulation rather than live futures execution

Main outputs:

- configurable leverage (1–125×) and isolated/cross margin mode in backtest API and UI
- per-candle liquidation check with maintenance margin threshold
- liquidation events surfaced in backtest execution detail and summary
- liquidation count visible in backtest run history

### 76. `feature/dashboard-unrealized-pnl`

Status:

- implemented on `main`

Scope:

- mark open positions to market on every worker cycle using the latest candle close price
- show live unrealized PnL in the dashboard runtime overview
- fix strategy name overflow in the overview card

Main outputs:

- worker cycle marks open positions to market via `_mark_open_position_to_market`
- unrealized PnL card in the 5-column runtime overview on the dashboard
- strategy name truncated with tooltip so long names never break the card layout

### 77. `feature/trade-exit-stop-loss`

Status:

- implemented on `main`

Scope:

- add ATR-based hard stop loss so a single bad trade cannot erase multiple wins
- add a trailing stop that locks in profit as price moves in favor
- keep stop logic in the strategy/risk domain layer rather than in execution services
- surface stop levels and stop-hit exits in backtest and paper trading results

Main outputs:

- ATR stop multiplier configurable per strategy (e.g. 2× ATR from entry)
- trailing stop that ratchets up as unrealized PnL grows
- stop-hit exit reason recorded on trades so operators can distinguish signal exits from stop exits
- stop levels visible in the backtest candlestick chart

Why: Without a hard stop, one adverse move can hold an underwater position for days and wipe out multiple winning trades. This is the single highest-impact improvement for real-money PnL protection.

### 78. `feature/regime-detection`

Status:

- implemented on `main`

Scope:

- detect trending vs ranging market regime using ADX before allowing a trade entry
- only enter when ADX exceeds a configurable threshold (e.g. 25) to avoid false signals in choppy markets
- add regime filter to the rule-builder indicator set so operators can backtest with and without it
- keep regime detection as a pre-entry filter rather than a separate strategy selector

Main outputs:

- ADX indicator implementation in the domain layer
- ADX threshold filter as an optional shared filter in the rule-builder
- regime filter configurable on the EMA crossover strategy via operator config
- backtest signal quality metrics showing raw count, regime-filtered rejections, and net signals

Why: EMA crossover generates too many false signals in ranging markets. ADX filtering alone typically reduces trade count by 30–50% while keeping the winning trades, improving expectancy.

### 79. `feature/volatility-adjusted-sizing`

Status:

- implemented on `main`

Scope:

- replace the flat risk-per-trade percentage with ATR-normalized position sizing
- larger positions when volatility is low (price moves are smaller), smaller when volatility is high
- keep total capital-at-risk bounded by the existing `RISK_PER_TRADE_PCT` ceiling
- surface the ATR-derived size alongside the flat-risk size in backtest and paper reports

Main outputs:

- ATR-based position sizing in the risk service as an opt-in mode
- `VOLATILITY_SIZING_ENABLED` config flag defaulting to false so existing behavior is unchanged
- backtest comparison showing equity curves with and without volatility sizing

Why: Fixed 1% risk means the same dollar loss whether the market moves 0.5% or 3% per candle. ATR sizing normalizes expected loss per trade, producing a smoother equity curve.

### 80. `feature/multi-symbol-trading`

Status:

- implemented on `main`

Scope:

- allow the worker to evaluate and execute across multiple configured symbols in one cycle
- keep per-symbol position, risk, and execution state isolated — no cross-symbol dependency
- enforce total capital exposure across all open positions against a configurable ceiling
- keep the feature bounded to paper and shadow modes until multi-symbol live risk is separately hardened

Main outputs:

- `TRADING_SYMBOLS` config list (e.g. `BTC/USDT,ETH/USDT,SOL/USDT`)
- per-symbol worker evaluation loop with independent position and risk state
- total-portfolio exposure gate that prevents opening new positions when aggregate notional exceeds the ceiling
- dashboard and reports scoped to symbol so operators can inspect per-pair performance

Why: Trading one pair means every no-signal candle is wasted compute. More symbols = more opportunities for the strategy's edge to compound without increasing per-trade risk.

### 81. `feature/auto-sync-on-backtest`

Status:

- implemented on `main`

Scope:

- automatically sync candles from the exchange before every backtest run — no manual sync step required
- fetch `required_candles + 100` bars so the strategy always has a warm-up buffer
- return a clear error if exchange API credentials are not configured
- remove the manual market sync panel from the controls UI since it is no longer needed for backtest workflows

Main outputs:

- auto-sync step injected into `OperationalControlService.run_backtest()` before reading candles from DB
- `exchange_api_not_configured` error status when credentials are absent
- market sync form removed from the controls page

Why: Requiring a separate manual sync before every backtest adds friction and is a common source of "not enough candles" failures. Auto-syncing on demand makes the backtest self-contained.

### 82. `feature/multi-timeframe-confirmation`

Status:

- implemented on `main`

Scope:

- require the higher timeframe (e.g. 4h) trend to align with the lower timeframe (e.g. 1h) entry signal before allowing a buy
- short trades are only allowed when the higher timeframe trend is also bearish
- keep the timeframe alignment check in the strategy layer, not in the execution path
- add multi-timeframe confirmation as an optional rule-builder filter

Main outputs:

- higher-timeframe candle fetch and EMA/trend evaluation in the worker cycle
- multi-timeframe alignment filter in the rule-builder indicator set
- backtest engine support for a secondary candle series at a configurable higher timeframe
- signal quality metrics showing how many entries the alignment filter rejects

Why: Entries that align with the higher timeframe trend have historically higher win rates because they trade with the dominant momentum rather than against it.

## Current Recommended Queue

Features 59–88 are complete on `main`. The system now has ATR stops, ADX regime detection, volatility-adjusted sizing, multi-symbol trading, auto-sync backtest, multi-timeframe trend confirmation, hardened replay friction plus benchmark reporting, the XGBoost signal path, and the live review / promotion loop.

Next bounded features:

- 1. `feature/live-futures-liquidation-guards` — reject isolated futures entries when configured leverage leaves too little liquidation distance for safe runtime execution

### 83. `feature/xgboost-signal-strategy`

Status:

- implemented on `main`

Scope:

- add XGBoost as a new signal strategy alongside existing rule-based strategies
- engineer features from existing indicators (EMA diff, RSI, MACD histogram, ATR, volume ratio, BB position)
- label each candle with next-candle direction (up/down) or next N% move as the prediction target
- train with walk-forward splits to prevent look-ahead bias (train on first 70%, validate on last 30%)
- save the trained model to `models/xgboost_btcusdt_<timeframe>.json`
- add `xgboost_signal` as a selectable strategy in the backtest API and worker runtime
- keep inference pure (no IO in domain layer); model loading happens in the application service layer

Implemented on `main`:

- `scripts/train_xgboost.py` — standalone training script that reads candles from DB and saves model file
- `app/domain/strategies/xgboost_signal.py` — pure inference strategy using a loaded XGBoost model
- `app/domain/strategies/features.py` — feature engineering (compute indicator vector per candle window)
- `app/application/services/model_registry.py` — loads and caches trained model files
- strategy doc at `docs/strategies/xgboost-signal.md`
- backtest and worker integration (registered in `StrategyFactory` alongside existing strategies)
- unit tests for feature engineering and inference path

Why: Rule-based EMA crossover produces too many false signals in ranging markets. XGBoost can learn non-linear combinations of indicators (e.g. RSI + ADX + BB position together) that no single threshold rule captures. Walk-forward training ensures the model generalises to unseen candles rather than overfitting history.

### 84. `feature/portfolio-risk-governor`

Status:

- completed on `main`

Scope:

- extend the existing live risk hard gates from per-trade blocking into portfolio-level capital governance
- bound aggregate exposure across symbols instead of relying only on single-order checks
- keep the feature bounded to account-level risk control rather than execution routing or strategy generation

Main outputs:

- total live notional exposure cap across all open positions
- per-symbol exposure cap
- max concurrent live positions limit
- concentration guard that blocks excessive allocation to one symbol
- machine-readable reject reasons surfaced in worker controls and audit events
- portfolio cap visibility through the status surface

Implemented on `main`:

- total live notional exposure cap across open positions
- per-symbol live exposure cap
- live symbol concentration guard
- max concurrent live positions limit
- machine-readable portfolio-risk reject reasons in worker control responses
- worker-cycle audit payloads carry the same machine-readable reject reason
- portfolio cap visibility through the status surface

Why: A system can pass single-order validation and still take unacceptable portfolio risk. Real-world deployment needs account-level controls that remain understandable to operators and fail closed before capital concentration becomes dangerous.

### 85. `feature/execution-reconciliation-recovery`

Status:

- completed on `main`

Scope:

- tighten the recovery workflow around restart, partial fill, stale-order, and exchange-drift conditions using the reconciliation features already in place
- move from “tools exist” to “operator can trust the recovery state machine”
- keep the feature bounded to correctness and restart safety rather than new trading logic

Main outputs:

- unified recovery-state classification for unresolved live orders
- startup and scheduled reconciliation that produce one operator-readable recovery outcome
- explicit review-required queue for drift, partial-fill, and missing-local-state cases
- recovery queue rows that distinguish waiting, stale, partial-fill, and manual-review cases without requiring raw status interpretation
- safer idempotency rules for replays and restarts when exchange state is uncertain
- runbook and reporting updates for recovery actions and expected operator decisions

Implemented on `main`:

- unresolved live orders are classified into operator-readable recovery states with explicit next actions
- startup sync, scheduled reconcile, manual reconcile, and manual cancel flows all feed one coherent recovery reporting path
- recovery queue, stale-order reporting, recovery posture summary, and recovery timeline are exposed through reporting and status surfaces
- live readiness, runtime promotion, live resume, live reconcile, and live halt now reuse or return the same structured recovery posture so control paths match reporting
- control audit payloads now carry post-action recovery posture for reconcile, halt, and runtime-promotion events

Why: Real systems usually fail at the recovery boundary, not the happy path. If restart and reconciliation outcomes are ambiguous, operators either over-trust stale local state or halt more often than necessary.

### 86. `feature/runtime-promotion-workflow`

Status:

- completed on `main`

Scope:

- make promotion through paper, shadow, qualified, canary, and broader live states explicit and operator-driven
- reuse existing qualification, canary, and halt controls while adding one durable promotion workflow
- keep the feature bounded to runtime state transitions rather than new strategy evidence generation

Implemented on `main`:

- persisted runtime promotion stage across paper, shadow, qualified, canary, and live
- explicit bounded control path for stage reads and updates
- stage blockers tied to qualification, readiness, recovery posture, canary exposure, and review-decision posture
- audit trail for runtime promotion updates and failed promotion attempts
- status and control responses that expose both blockers and the next missing prerequisite
- operator controls UI panel that shows the current stage and lets operators request bounded stage changes

Why: The repo already has many ingredients for safe rollout, but without one explicit promotion workflow, the safety model is spread across env flags, qualification reports, controls, and runbook rules. Real-world use needs one coherent operator path.

### 87. `feature/backtest-market-friction-hardening`

Status:

- implemented on `main`

Scope:

- improve backtest realism beyond the current slippage and fee model by covering more of the friction that separates replay from live performance
- reduce the gap between walk-forward evidence and observed live or shadow behavior
- keep the feature bounded to simulation assumptions and reporting rather than new alpha models

Implemented on `main`:

- configurable spread and latency assumptions in replay execution
- persisted spread and latency assumptions in backtest run history and reports
- explicit assumption summary included in backtest API and reporting output
- backtest UI controls that let operators set friction assumptions directly and reload them from recent runs
- optional UTC weekday and hour constraints for backtests
- deterministic partial-fill and missed-fill assumptions via candle-volume participation caps
- benchmark comparison in replay results, recent-run reporting, and CSV exports for cost-adjusted return context
- explicit friction-assumption columns in CSV exports so operators can compare runs without parsing the summary string
- explicit “assumption summary” included in backtest output so operators know what realism model was applied

Why: Even a cost-adjusted backtest can still overstate live viability if it assumes immediate fills, zero spread pressure, and perfect market availability. Hardening the friction model makes strategy promotion decisions more honest.

### 88. `feature/performance-review-decision-log`

Status:

- completed

Scope:

- persist operator decisions taken after reviewing the live performance report
- expose the latest review decision and its staleness through status and reporting surfaces
- keep the feature bounded to operator evidence and auditability rather than new promotion gating

Main outputs:

- durable `performance_review_decisions` persistence with review snapshot context
- bounded control API for recording and reading the latest operator decision
- status and reporting visibility for the latest decision, rationale, and stale/not-stale posture
- audit events for recorded performance review decisions

Why: Recommendation logic and root-cause analysis now exist, but without a durable operator decision record there is no trustworthy evidence trail for later promotion gating or review accountability.

### 89. `feature/durable-strategy-identity`

Status:

- completed on `main`

Scope:

- persist durable `strategy_name` identity on execution records instead of inferring it later from transient operator config
- keep the feature bounded to identity propagation and storage, not per-strategy risk policy yet
- preserve current one-position-per-symbol behavior until a later feature intentionally changes live position partitioning

Main outputs:

- `strategy_name` persisted on `orders`, `trades`, and `positions`
- execution and reconciliation paths that carry strategy identity from request to stored records
- local schema reconciliation for existing development databases
- tests proving strategy identity survives paper execution, live submission, and live fill reconciliation

Why: Per-strategy exposure caps are not trustworthy until the runtime stores strategy identity durably on the records those caps would inspect. Without that, any future “per-strategy” live governor would silently depend on the current operator config rather than the order or position that actually exists.

### 90. `feature/per-strategy-live-risk-caps`

Status:

- completed on `main`

Scope:

- enforce one additional live risk gate that limits notional exposure per persisted `strategy_name`
- use stored position identity rather than transient runtime config as the source of truth for current strategy exposure
- keep the feature bounded to one aggregate per-strategy cap and operator visibility, not multi-strategy netting or per-strategy position partitioning

Main outputs:

- configurable live per-strategy exposure cap in runtime settings
- worker portfolio state that computes current live exposure for the active strategy from persisted positions
- live risk rejection when the next entry would exceed the configured per-strategy notional cap
- status visibility for the configured per-strategy cap
- tests proving the cap blocks only the intended live entry path

Why: Durable strategy identity is now stored on execution records, so the system can finally enforce a real per-strategy live exposure cap using the positions that actually exist. This closes the specific safety gap intentionally deferred when the broader portfolio-risk feature was shipped.

### 91. `feature/live-futures-execution-controls`

Status:

- completed on `main`

Scope:

- apply one configured leverage and margin mode before live futures order submission
- expose the configured futures execution controls through status for operator review
- keep the feature bounded to exchange-side futures configuration and submission safety, not liquidation-aware sizing, leverage policy, or persisted operator leverage controls

Main outputs:

- runtime settings for live futures leverage and margin mode
- live futures execution path that applies margin mode and leverage before submission when not in validate-only mode
- idempotent handling for repeated margin-mode configuration on Binance futures
- status visibility for the configured live futures leverage and margin mode
- tests proving futures configuration is applied only on the futures live path

Why: The repo can already simulate futures leverage in backtests and route futures requests to the Binance futures client, but live submission still lacks one explicit place where exchange-side leverage and margin mode are configured. Applying those controls before submission is the next safe step toward bounded futures-capable live groundwork.

### 92. `feature/live-futures-liquidation-guards`

Status:

- completed on `main`

Scope:

- add one leverage-aware runtime risk guard for live futures entries in isolated margin mode
- reject entries when configured leverage leaves less than a minimum liquidation-distance buffer
- keep the feature bounded to deterministic runtime entry policy and operator visibility, not exchange mark-price polling, auto-deleveraging flows, or full futures risk modeling

Main outputs:

- runtime settings for a minimum isolated-futures liquidation buffer
- risk-service logic that computes liquidation distance from configured leverage before approving a live futures entry
- rejection path for futures entries whose configured leverage leaves too little room before liquidation
- status visibility for the configured liquidation buffer guard
- tests proving the new guard blocks only the intended isolated-futures entry path

Why: The repo now applies leverage and margin mode before live futures submission, but the runtime risk path is still leverage-blind. A bounded liquidation-distance guard is the next safe step because it fail-closes clearly risky isolated-futures entries without widening into a full futures portfolio model.

### 93. `feature/futures-operator-runtime-controls`

Status:

- completed on `main`

Scope:

- persist futures leverage and margin mode alongside the existing operator runtime config
- let operator config updates control effective futures execution defaults without a process restart
- carry the persisted futures controls through status, worker orchestration, and live execution submission
- keep the feature bounded to operator-managed runtime defaults, not new futures sizing policy, liquidation math, or additional promotion gates

Main outputs:

- persisted `operator_configs` leverage and margin-mode fields with local schema reconciliation
- `GET/POST /controls/operator-config` request and response support for futures leverage and margin mode
- operator-config validation that normalizes spot runtime config to `1x` and `ISOLATED`
- status visibility for the effective operator-managed futures leverage and margin mode
- worker and live execution propagation so persisted operator futures controls override settings defaults at runtime
- tests proving the control path, status surface, schema reconciliation, and live futures request propagation

Why: Live futures execution and liquidation guards now exist, but leverage and margin mode are still settings-driven. That forces a restart to change operator-approved runtime defaults and leaves the control path incomplete. Persisting these futures controls in operator runtime config is the next bounded step because it makes the existing operator workflow authoritative without widening into a broader futures risk-policy feature.

### 94. `feature/live-futures-max-leverage-cap`

Status:

- completed on `main`

Scope:

- add one configurable maximum leverage cap for live futures runtime approval
- reject live futures entries when the effective operator-selected leverage exceeds that cap
- expose the configured cap through status and enforce it during operator runtime-config updates
- keep the feature bounded to a simple leverage ceiling, not mark-price polling, margin-ratio simulation, or a broader futures policy engine

Main outputs:

- runtime setting for a maximum allowed live futures leverage
- config and operator-runtime validation that reject leverage above the configured cap
- risk-service rejection path for live futures entries above the configured leverage ceiling
- status visibility for the configured live futures max leverage
- tests proving the cap blocks only the intended live futures path

Why: The repo now supports operator-managed futures leverage and margin mode, but the isolated liquidation guard only covers one margin mode and does not set any global ceiling on allowable leverage. A bounded max-leverage cap is the next safe step because it constrains both isolated and cross-margin live futures operation without widening into a full leverage policy feature.

### 95. `feature/live-futures-liquidation-visibility`

Status:

- completed on `main`

Scope:

- expose one operator-readable futures risk visibility block through status and reporting
- show effective leverage, leverage-cap headroom, and estimated isolated liquidation buffer using the same formulas already enforced in runtime risk policy
- keep the feature bounded to derived visibility only, not new control writes, exchange-side mark-price polling, or additional futures approval logic

Main outputs:

- `/status` visibility for effective futures leverage posture and leverage-cap headroom
- derived isolated-margin liquidation buffer and remaining headroom versus the configured minimum
- reporting UI panel that explains futures margin posture in operator-readable terms
- tests proving the derived status and reporting surfaces stay aligned with the backend policy

Why: The repo now enforces a futures leverage cap and an isolated liquidation buffer, but operators still have to infer their current margin posture from scattered raw config fields. The next bounded step is to expose that safety posture directly so the same leverage and liquidation story is visible before a rejection happens.
