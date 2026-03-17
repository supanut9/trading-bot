# Product Spec

## Objective

Build a maintainable trading bot that supports research, backtesting, paper trading, and later controlled live execution.

## V1 Scope

- one market symbol
- one strategy
- candle-based execution
- paper trading only
- API endpoints for health, status, positions, trades, candle ingestion, market sync, reporting UI, and bounded manual controls

## Initial Market And Strategy

- exchange: Binance-compatible abstraction
- symbol: BTC/USDT
- timeframe: 1h
- strategy: EMA crossover

## Core Capabilities

- fetch candle data
- ingest closed candle batches through a local API path
- sync recent closed candles from a configured exchange adapter before worker execution when enabled
- run deterministic backtests over stored historical candles
- calculate indicators
- generate signals from deterministic strategy rules
- apply risk checks
- simulate order execution in paper mode
- route execution through a replaceable adapter boundary, with paper execution as the current concrete implementation
- provide a signed live order client for the configured exchange, with validate-only routing available before full live execution is enabled
- orchestrate a worker cycle from persisted candles through execution
- persist accepted live orders locally while keeping trades and positions unchanged until exchange fills are explicitly reconciled
- reconcile confirmed live exchange fills into local trades and positions through a bounded control workflow
- expose exchange-side base and quote asset balances for the configured live symbol through the status surface
- optionally run recurring live reconciliation jobs so local runtime state can catch up with exchange fills without manual control calls
- run startup live reconciliation before new live worker execution so restarts fail closed on uncertain exchange state
- allow bounded manual cancellation of recent live orders through the controls surface
- detect stale open live orders locally and surface them for operator review without automatic cancellation
- expose a compact recovery report for unresolved live orders and recent reconciliation or cancel context
- emit optional live-operations alerts for failed startup sync, failed scheduled reconciliation, and stale live orders
- document deployment, restart, rollback, backup, and alert-response expectations before live-capable operation
- emit optional notifications for worker execution, risk rejection, backtest outcomes, and market sync outcomes
- persist bot state and logs
- expose minimal operational API for health, status, positions, trades, candle ingestion, and bounded manual controls
- export operational and backtest summary data as CSV for review and offline inspection
- render an operator-facing reporting page over positions, trades, backtest summary data, and recent audit events
- render a bounded operator console page for paper-trading workflows with one-click market sync, worker-cycle, and backtest actions
- persist a lightweight audit feed for control outcomes and notification delivery attempts
- run recurring worker and optional recurring backtest jobs through explicit scheduled job modules
- package API and worker runtime entrypoints into one deployable repository image
- provide explicit environment baselines for local development, deployed API runtime, and deployed worker runtime
- provide bounded post-deploy smoke checks for API and worker roles without triggering execution
- validate deployment-critical runtime settings and database connectivity during API, worker, and backtest startup
- expose the latest read-only exchange price through status and reporting surfaces for operator visibility
- enforce PR merge readiness with CI and resolved review feedback

## Current Risk Policy Baseline

- paper trading only
- fixed risk per trade
- max open positions limit
- daily loss limit before execution approval
- execution mode must be configured explicitly as either paper or live, never both
- explicit live mode must fail safely when exchange submission or later fill reconciliation cannot confirm runtime state
- live-capable operation requires PostgreSQL persistence, backup coverage, startup sync, scheduled reconciliation, and tested alerts

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
- futures or leverage
- multiple strategies in production
- multi-exchange routing
- autonomous portfolio optimization
