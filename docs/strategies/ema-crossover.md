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
