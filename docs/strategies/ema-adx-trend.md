# EMA ADX Trend Strategy

## Market

- symbol: BTC/USDT
- timeframe: 1h

## Indicators

- fast EMA: 20
- slow EMA: 50
- trend EMA: 100
- ADX period: 14
- ADX threshold: 20

## Entry Rule

Generate a long entry signal when all of the following are true on a closed candle:

- the fast EMA crosses above the slow EMA
- the current fast EMA is above the trend EMA
- the current slow EMA is above the trend EMA
- the current close is above the trend EMA
- ADX is greater than or equal to the configured threshold

## Exit Rule

Generate a sell signal when all of the following are true on a closed candle:

- the fast EMA crosses below the slow EMA
- the current fast EMA is below the trend EMA
- the current slow EMA is below the trend EMA
- the current close is below the trend EMA
- ADX is greater than or equal to the configured threshold

## Risk Assumptions

- paper trading first
- deterministic indicator-only logic
- no exchange-side state inside the strategy
- futures usage is controlled outside the strategy by runtime risk policy

## No-Trade Conditions

- insufficient candles to compute the 20, 50, 100 EMA stack and ADX
- ADX below threshold
- crossover occurs but the EMA stack is not aligned with the 100 EMA trend filter
- missing or invalid candle data

## Exact Evaluation Rule

- evaluate only on closed candles
- require at least `max(trend_period + 1, 2 * adx_period + 1)` candles
- treat a buy signal as:
  previous fast EMA less than or equal to previous slow EMA, current fast EMA greater than current slow EMA, and current fast EMA, current slow EMA, and current close all above the current trend EMA
- treat a sell signal as:
  previous fast EMA greater than or equal to previous slow EMA, current fast EMA less than current slow EMA, and current fast EMA, current slow EMA, and current close all below the current trend EMA

## Runtime Notes

- `ema_adx_trend` reuses the existing operator-config `fast_period` and `slow_period` fields
- the trend EMA remains fixed at 100 in this first implementation
- ADX is required for this strategy and defaults to `14 / 20` when backtest-specific overrides are not supplied
