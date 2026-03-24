# EMA ADX Trend Volume Strategy

## Market

- symbol: BTC/USDT
- timeframe: 1h
- mode: long-only research strategy aligned to spot-style behavior

## Indicators

- fast EMA: 20
- slow EMA: 50
- trend EMA: 100
- ADX period: 14
- ADX threshold: 20
- volume EMA period: 20
- volume multiplier: 1.2

## Entry Rule

Generate a long entry signal only when all of the following are true on a closed candle:

- the fast EMA crosses above the slow EMA
- the current close is above the current EMA 100
- ADX is greater than or equal to 20
- current candle volume is greater than or equal to `volume EMA 20 * 1.2`

## Exit Rule

Once a long position is open, manage it with fixed strategy exits instead of waiting for an opposite crossover:

- stop loss: the lowest low of the last 10 candles at entry time
- take profit: `entry + 2R`, where `R = entry - stop`
- if both the stop and take-profit are crossed inside the same candle, exit at the stop first

## Sizing Assumption

- risk 1 percent of current equity per trade
- position size = `(equity * 0.01) / (entry - stop)`
- no short entries in this strategy

## No-Trade Conditions

- insufficient candles to compute EMA 100, ADX, volume EMA, and the 10-candle swing low
- ADX below 20
- close at or below EMA 100
- volume below `volume EMA 20 * 1.2`
- swing-low stop would be at or above the entry close
- invalid non-positive risk distance

## Exact Evaluation Rule

- evaluate only on closed candles
- require at least `max(101, 2 * adx_period + 1, volume_ema_period, stop_lookback + 1)` candles
- generate buy signals only on the crossover candle itself
- do not emit sell signals from the strategy layer; exits are managed by the bounded backtest execution policy for this strategy

## Runtime Notes

- this strategy is backtest-selectable only in the current implementation
- runtime worker execution does not yet support the same swing-low stop, fixed 2R target, and strategy-specific risk-to-stop sizing semantics
- keep `ema_adx_trend` as the simpler crossover-plus-trend comparison variant
