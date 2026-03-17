# Data Model

## Purpose

This document describes the durable persistence model for the trading bot at a system level. Exact implementation details live in the SQLAlchemy models and future migrations.

## Design Rules

- persistence models belong to `app/infrastructure/database/models`
- domain logic must not depend on storage-specific details
- schema design should favor PostgreSQL as the normal local development target
- SQLite compatibility is useful but secondary to correct persistence behavior
- schema changes that affect runtime behavior, safety, or operations should also update this document or `docs/decisions.md`

## Core Tables

### `candles`

Purpose:

- store normalized OHLCV candle data used by strategies and backtests

Key columns:

- exchange
- symbol
- timeframe
- open_time
- close_time
- open_price
- high_price
- low_price
- close_price
- volume

Important constraint:

- one candle per `exchange + symbol + timeframe + open_time`

### `orders`

Purpose:

- store paper or live order attempts and their execution state

Key columns:

- exchange
- symbol
- side
- order_type
- status
- mode
- client_order_id
- exchange_order_id
- quantity
- price
- average_fill_price

Notes:

- `mode` distinguishes paper and future live execution
- this table is the main audit trail for execution attempts

### `trades`

Purpose:

- store fills or executed trade events associated with an order when available

Key columns:

- order_id
- exchange
- symbol
- side
- quantity
- price
- fee_amount
- fee_asset

Notes:

- a trade represents execution outcome, not strategy intent

### `positions`

Purpose:

- store the current aggregate position state for a symbol and mode

Key columns:

- exchange
- symbol
- side
- mode
- quantity
- average_entry_price
- realized_pnl
- unrealized_pnl

Important constraint:

- one active position row per `exchange + symbol + mode`

### `audit_events`

Purpose:

- store operator-facing audit events for control execution and notification delivery

Key columns:

- event_type
- source
- status
- detail
- exchange
- symbol
- timeframe
- channel
- related_event_type
- payload_json

Notes:

- this table is a compact runtime audit feed, not a full log sink
- `payload_json` keeps event-specific context without widening the schema for every new control or notification detail

## Relationships

- `orders` may produce zero or more `trades`
- `trades` affect `positions`
- `candles` feed strategies but are not directly tied to order rows
- `audit_events` reference runtime outcomes by context rather than foreign-key linkage

## Operational Notes

- schema is intentionally small for v1
- order, trade, and position data should be sufficient to reconstruct paper trading behavior
- audit events add a lightweight operator timeline for controls and notifications
- future tables may include signals, bot runs, bot logs, and strategy snapshots
