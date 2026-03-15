# EMA Crossover Strategy

## Market

- symbol: BTC/USDT
- timeframe: 1h

## Indicators

- fast EMA: 20
- slow EMA: 50

## Entry Rule

Generate a long entry signal when the 20 EMA crosses above the 50 EMA on a closed candle.

## Exit Rule

Generate an exit signal when the 20 EMA crosses below the 50 EMA on a closed candle.

## Risk Assumptions

- paper trading only
- fixed risk percentage per trade in later implementation
- no leverage

## No-Trade Conditions

- insufficient candles to compute both EMAs
- missing or invalid candle data
- live trading mode disabled unless explicitly configured

## Exact Evaluation Rule

- evaluate only on closed candles
- require at least `slow_period + 1` candles to confirm a crossover from the previous step to the current step
- treat a buy signal as: previous fast EMA less than or equal to previous slow EMA, and current fast EMA greater than current slow EMA
- treat a sell signal as: previous fast EMA greater than or equal to previous slow EMA, and current fast EMA less than current slow EMA
