# Rule Builder Strategy

## Purpose

Provide a configurable backtest-only strategy builder that combines reusable indicator conditions
into separate shared, buy, and sell rule groups.

## Scope

- backtest only in v1
- no live or worker runtime execution
- deterministic evaluation on closed candles only

## Supported Indicators In V1

- EMA cross
- price versus EMA
- RSI threshold

## Rule Groups

- `shared_filters`
  - conditions that must pass before either buy or sell rules can trigger
- `buy_rules`
  - conditions evaluated for buy entry signals
- `sell_rules`
  - conditions evaluated for sell exit signals

Each group supports one logic mode:

- `all`
  - every condition in the group must pass
- `any`
  - at least one condition in the group must pass

## Indicator Definitions

### EMA Cross

- bullish: previous fast EMA less than or equal to previous slow EMA, and current fast EMA greater than current slow EMA
- bearish: previous fast EMA greater than or equal to previous slow EMA, and current fast EMA less than current slow EMA

Minimum candles:

- `slow_period + 1`

### Price Versus EMA

- above: latest close strictly greater than the latest EMA value
- below: latest close strictly less than the latest EMA value

Minimum candles:

- `period`

### RSI Threshold

- above: latest RSI strictly greater than the configured threshold
- below: latest RSI strictly less than the configured threshold

Minimum candles:

- `period + 1`

## Signal Resolution

- evaluate shared filters first
- if shared filters fail, emit no signal
- evaluate buy and sell groups independently on the same closed candle
- if only buy rules pass, emit a buy signal
- if only sell rules pass, emit a sell signal
- if both sides pass on the same candle, emit no signal to avoid ambiguous intent

## No-Trade Conditions

- one or both side-specific groups are empty
- insufficient candles for one or more active conditions
- invalid indicator parameters
- contradictory buy and sell rules matching on the same candle

## UI Boundary

- operators can add or remove conditions in each group
- operators can choose whether a condition belongs to shared, buy, or sell logic
- the UI serializes the rule set as a structured payload passed to the existing backtest path
- runtime defaults remain on the fixed EMA strategy until a later feature expands worker/runtime support
