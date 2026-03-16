# Product Spec

## Objective

Build a maintainable trading bot that supports research, backtesting, paper trading, and later controlled live execution.

## V1 Scope

- one market symbol
- one strategy
- candle-based execution
- paper trading only
- API endpoints for health, status, positions, trades, candle ingestion, and bounded manual controls

## Initial Market And Strategy

- exchange: Binance-compatible abstraction
- symbol: BTC/USDT
- timeframe: 1h
- strategy: EMA crossover

## Core Capabilities

- fetch candle data
- ingest closed candle batches through a local API path
- run deterministic backtests over stored historical candles
- calculate indicators
- generate signals from deterministic strategy rules
- apply risk checks
- simulate order execution in paper mode
- orchestrate a worker cycle from persisted candles through execution
- emit optional notifications for worker execution, risk rejection, and backtest outcomes
- persist bot state and logs
- expose minimal operational API for health, status, positions, trades, candle ingestion, and bounded manual controls

## Current Risk Policy Baseline

- paper trading only
- fixed risk per trade
- max open positions limit
- daily loss limit before execution approval

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
