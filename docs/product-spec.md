# Product Spec

## Objective

Build a maintainable trading bot that supports research, backtesting, paper trading, and later controlled live execution.

## V1 Scope

- one market symbol
- one strategy
- candle-based execution
- paper trading only
- API endpoints for health and status

## Initial Market And Strategy

- exchange: Binance-compatible abstraction
- symbol: BTC/USDT
- timeframe: 1h
- strategy: EMA crossover

## Core Capabilities

- fetch candle data
- calculate indicators
- generate signals from deterministic strategy rules
- apply risk checks
- simulate order execution in paper mode
- persist bot state and logs
- expose minimal operational API

## Current Risk Policy Baseline

- paper trading only
- fixed risk per trade
- max open positions limit
- daily loss limit before execution approval

## Development Infrastructure

- local database: PostgreSQL via Docker Compose
- fallback database: SQLite for lightweight bootstrap or isolated local tasks

## Explicit Non-Goals

- high-frequency trading
- futures or leverage
- multiple strategies in production
- multi-exchange routing
- autonomous portfolio optimization
