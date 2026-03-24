# Product Spec

## Objective

Build a maintainable trading bot that supports research, backtesting, paper trading, and later controlled live execution.

## V1 Scope

- one market symbol
- one runtime execution strategy plus a configurable backtest rule builder
- candle-based execution
- paper trading only
- API endpoints for health, status, positions, trades, candle ingestion, market sync, reporting exports, and bounded manual controls
- support for both spot and futures/leverage modes

## Current Milestone

Current baseline on `main`:

- paper-trading-first runtime with deterministic backtesting, paper execution, notifications, and bounded operator controls
- in-repo Next.js operator UI backed by FastAPI APIs
- performance analytics, equity-curve reporting, and CSV exports
- deployment packaging, smoke checks, and startup validation
- live-readiness groundwork for submission, reconciliation, cancel, stale-order visibility, and recovery reporting while keeping live trading disabled by default
- runtime log correlation across API requests and scheduled worker jobs via shared request and run ids
- notification payloads that carry the active runtime correlation id when alerts are emitted from a correlated run
- notification-delivery reporting in the dashboard and a dedicated CSV export for delivery audit rows
- notification-delivery filters in the dashboard with a matching filtered CSV export link
- audit-report filters in the dashboard with a matching filtered audit CSV export link
- audit-report columns in the dashboard and audit CSV so operators can inspect key metadata without parsing payload JSON
- preset-first rule-builder backtests in the dedicated Next.js backtest route over the existing control API
- summary-level backtest run history with recent-run hydration in the dedicated backtest route
- read-only market-data coverage and replay-readiness panels in the Next.js backtest and controls routes
- smart order execution for live mode supporting limit orders with configurable offsets and timeouts
- fee-aware live execution gates that block entry signals when expected profit does not cover estimated fees
- automatic slippage tracking for live fills using signal-time price and final average fill price
- automated fallback mechanism for timed-out live limit orders that cancels and resubmits as market orders
- ATR hard stop and trailing stop, ADX regime filter, ATR volatility-adjusted sizing, multi-symbol worker loop, auto-sync before backtest, and multi-timeframe HTF trend confirmation
- persisted operator performance-review decisions with audit logging plus status and reporting visibility for latest decision freshness
- durable `strategy_name` identity persisted on orders, trades, and positions across paper, shadow, and live execution paths

Current production boundary:

- production deployment target: paper trading
- non-target for current production readiness: live trading with exchange-facing execution
- live capabilities remain groundwork until the runbook live-capable checklist is completed operationally, not just in code

Project completion boundary:

- one approved strategy has demonstrated positive expectancy after costs in walk-forward out-of-sample and shadow validation, and can execute real-money trades under hard risk gates with auditable reconciliation and fail-closed incident handling
- profitable operation in all market conditions is not a delivery target; the system's job is to execute a validated strategy correctly and stop when conditions are outside its operating envelope

Next implementation queue:

Iteration and strategy improvement (current focus):

1. `feature/live-performance-review-loop` — compare live vs walk-forward OOS to detect edge decay (completed)
2. `feature/live-readiness-gate` — explicit go/no-go report before any live resume or promotion path is trusted (completed)
3. `feature/portfolio-risk-governor` — add portfolio-level exposure, concentration, and concurrent-position caps (completed)
4. `feature/execution-reconciliation-recovery` — turn restart and reconciliation tooling into one trusted recovery workflow (completed)
5. `feature/runtime-promotion-workflow` — make paper → shadow → qualified → canary → live progression explicit and auditable (completed)
6. `feature/strategy-iteration-workflow` — re-validate and re-promote when live results fall short (completed)

Profitability improvements (what separates this bot from better real-world bots):

7. `feature/backtest-market-friction-hardening` — add spread, latency, partial-fill, assumption-summary, explicit export columns, and buy-and-hold benchmark realism to replay results, run history, reporting exports, and operator controls (completed)
8. `feature/xgboost-signal-strategy` — ML-based signal using XGBoost trained on indicator features (completed)
9. `feature/durable-strategy-identity` — persist strategy identity on orders, trades, and positions before enforcing any per-strategy live-risk governor (completed)
10. `feature/per-strategy-live-risk-caps` — enforce live per-strategy notional exposure limits using persisted position strategy identity (completed)
11. `feature/live-futures-execution-controls` — apply configured leverage and margin mode before live futures submissions (completed)
12. `feature/live-futures-liquidation-guards` — reject isolated live futures entries when configured leverage leaves too little liquidation buffer (completed)
13. `feature/futures-operator-runtime-controls` — persist futures leverage and margin mode in operator runtime config so live futures defaults can change without restart (completed)
14. `feature/live-futures-max-leverage-cap` — enforce one maximum allowed leverage ceiling for live futures runtime config and approval (in progress)

## Initial Market And Strategy

- exchange: Binance-compatible abstraction
- symbol: BTC/USDT
- timeframe: 1h
- strategy: EMA crossover

## Core Capabilities

- fetch candle data
- ingest closed candle batches through a local API path
- sync recent closed candles from a configured exchange adapter before worker execution when enabled
- expose a read-only market-data coverage view with stored range, replay minimum, and freshness status for the selected replay shape
- backfill older candles into an existing market-data store through an operator-initiated sync mode when more history is needed for backtests
- allow operators to run market sync against an explicit symbol and timeframe without silently mutating persisted runtime defaults
- run deterministic backtests over stored historical candles
- calculate indicators
- generate signals from deterministic strategy rules
- apply risk checks
- simulate order execution in paper mode
- route execution through a replaceable adapter boundary, with paper execution as the current concrete implementation
- provide a signed live order client for the configured exchange, with validate-only routing available before full live execution is enabled
- orchestrate a worker cycle from persisted candles through execution
- persist accepted live orders locally while keeping trades and positions unchanged until exchange fills are explicitly reconciled
- expose a read-only live-readiness report so operators can inspect blocking prerequisites before attempting live resume
- normalize live order status into a canonical local state model before operator surfaces consume it
- block new live submissions when an unresolved same-side live order already exists for the configured market
- reconcile confirmed live exchange fills into local trades and positions through a bounded control workflow
- mark uncertain exchange outcomes as `review_required` instead of silently treating them as ordinary open or terminal states
- expose exchange-side base and quote asset balances for the configured live symbol through the status surface
- expose live readiness status and blocking reasons through the status surface
- expose configured portfolio risk caps through the status surface for operator review before enabling live mode
- expose the persisted runtime promotion stage, blockers, and next missing prerequisite through status and control surfaces
- expose the latest persisted performance-review decision and its stale/not-stale posture through the status and reporting surfaces
- require a fresh persisted `keep_running` performance-review decision before promoting from `canary` to full `live`
- block new live entries when live trading is halted by configuration while leaving recovery controls available
- allow operators to halt or resume live entry through a bounded persisted control without restarting the runtime
- fail closed on live resume attempts when readiness checks are still blocked
- bound live entries by configured max order notional and max position quantity limits
- bound live entries by aggregate exposure, per-symbol exposure, concentration, concurrent-position, and per-strategy exposure caps
- optionally run recurring live reconciliation jobs so local runtime state can catch up with exchange fills without manual control calls
- run startup live reconciliation before new live worker execution so restarts fail closed on uncertain exchange state
- allow bounded manual cancellation of recent live orders through the controls surface
- detect stale open live orders locally and surface them for operator review without automatic cancellation
- expose a compact recovery report for unresolved live orders and recent reconciliation or cancel context
- render a recovery queue and recovery timeline inside the reporting surface so operators can inspect unresolved live state without correlating raw audit rows manually
- classify unresolved live orders into operator-readable recovery states such as awaiting, partial-fill, stale, or manual-review-required
- expose one aggregate recovery posture with the dominant recovery state and next recommended action through reporting and status surfaces
- reuse that aggregate recovery posture in live-readiness and promotion blocker messaging so operator controls describe the same recovery state shown in reporting
- include the post-action recovery posture in live reconcile and live halt control results plus audit evidence
- expose the structured recovery posture directly through live-readiness and runtime-promotion control responses
- persist an operator-controlled promotion stage across paper, shadow, qualified, canary, and live states
- render recovery timeline context from audit payloads so operators can see reconcile counts and cancel identifiers inline
- allow operators to filter recovery queue and timeline views by status, review state, event type, and search terms
- emit optional live-operations alerts for failed startup sync, failed scheduled reconciliation, and stale live orders
- document deployment, restart, rollback, backup, and alert-response expectations before live-capable operation
- emit optional notifications for worker execution, risk rejection, backtest outcomes, and market sync outcomes
- persist operator review decisions taken against the live performance review through a bounded controls API with audit evidence
- include review-decision alignment and runtime-stage rollback steps in the strategy iteration plan when live results fall short
- render the strategy iteration checklist in reporting so operators can review rollback, revalidation, and re-promotion steps in one place
- persist bot state and logs
- expose minimal operational API for health, status, positions, trades, candle ingestion, and bounded manual controls
- load deterministic local demo candle scenarios for no-action, buy-crossover, and sell-crossover operator workflows
- export operational and backtest summary data as CSV for review and offline inspection
- render operator-facing dashboard, reporting, and control workflows in the in-repo Next.js application while keeping FastAPI as the source of truth for business logic and controls
- provide a dedicated market-sync controls page with explicit symbol, timeframe, limit, and backfill inputs plus sync-result feedback
- expose current live posture, halt or resume, reconcile, and manual cancel actions inside the controls page while keeping live safety and execution policy in the backend
- provide a dedicated reporting page in Next.js with performance analytics, equity-curve visibility, and direct CSV export links
- provide a dedicated backtest page with parameterized inputs and chart visualization for replay analysis
- provide preset-first backtest strategy selection backed by curated rule-builder presets
- allow operators to edit backtest-only rule-builder groups and conditions inside the backtest page while reusing the existing control API
- persist recent backtest runs with summary metrics and allow the backtest page to hydrate its form from a stored run
- expose spread, latency, and assumption-summary backtest realism settings through the control and reporting surfaces
- allow backtests to restrict simulated execution to explicit UTC weekdays and hours
- allow backtests to cap fills by candle-volume participation and optionally permit partial fills
- provide read-only Next.js recovery reporting with stale-order visibility, unresolved live-order queue, recent recovery events, and filtered export links
- persist paper-runtime operator defaults for symbol, timeframe, trading mode (SPOT/FUTURES), and EMA periods so operator actions do not depend only on startup env
- render a compact reporting summary over the latest worker outcome, PnL, trade count, positions, and stale live state
- derive durable operator-facing performance analytics from persisted trades and positions without adding a dedicated summary table first
- expose the computed performance equity curve through both the reporting page and CSV export surfaces
- persist a lightweight audit feed for control outcomes and notification delivery attempts
- run recurring worker and optional recurring backtest jobs through explicit scheduled job modules
- package API and worker runtime entrypoints into one deployable repository image
- provide explicit environment baselines for local development, deployed API runtime, and deployed worker runtime
- provide bounded post-deploy smoke checks for API and worker roles without triggering execution
- verify live safety posture and live worker startup-sync readiness in smoke-check output before trusting a deployment
- validate deployment-critical runtime settings and database connectivity during API, worker, and backtest startup
- expose the latest read-only exchange price through status and reporting surfaces for operator visibility
- render explicit market, delivery, and correlation columns in the generic audit reporting slice so operators can inspect audit metadata without opening raw payload JSON
- support smart live execution with limit orders, configurable offsets, and automatic timeout fallbacks
- enforce expected-profit thresholds against estimated trading fees before approving new live entry signals
- calculate and persist execution slippage for reconciled live fills using the signal-price baseline
- track signal-time price on all live orders to enable accurate post-trade slippage analysis
- enforce PR merge readiness with CI and resolved review feedback

## Current Risk Policy Baseline

- paper trading only
- fixed risk per trade
- max open positions limit
- daily loss limit before execution approval
- live portfolio caps for total exposure, per-symbol exposure, concentration, and concurrent positions
- execution mode must be configured explicitly as either paper or live, never both
- explicit live mode must fail safely when exchange submission or later fill reconciliation cannot confirm runtime state
- live-capable operation requires PostgreSQL persistence, backup coverage, startup sync, scheduled reconciliation, and tested alerts
- live futures execution groundwork also requires explicit leverage and margin-mode configuration before submission
- [x] **Feature: Futures/leverage support**
  - [x] Update config/settings for trading mode (SPOT/FUTURES)
  - [x] Implement Binance Futures exchange client
  - [x] Update database models for trading mode segregation
  - [x] Integrate trading mode into execution services (paper/live)
  - [x] Persist trading mode in operator configuration UI
  - [x] Mode-aware backtesting (SPOT/FUTURES simulation)
- [x] Symmetric execution (Direct shorting support in Futures)
- [x] Separate balance tracking (SPOT vs FUTURES wallets)
- [ ] Multi-symbol concurrent backtesting
- [ ] Portfolio-level risk metrics (VAR, Correlation)
  - [ ] Implement leverage-aware liquidation risk in runtime execution policy
  - [ ] Update RiskService to handle leverage-aware liquidation risk

## Current Paper Execution Baseline

- paper orders are treated as immediately filled
- each paper execution writes an order, trade, and updated position state
- sell executions realize PnL against the stored average entry price
- worker-triggered paper orders use a candle-derived `client_order_id` to avoid duplicate execution on the same signal candle

## Development Infrastructure

- local database: PostgreSQL via Docker Compose
- fallback database: SQLite for lightweight bootstrap or isolated local tasks

## Explicit Non-Goals

- high-frequency trading
- multiple concurrent execution strategies in production
- multi-exchange routing
- autonomous portfolio optimization
