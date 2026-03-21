# RSI Momentum Strategy

## Strategy Name

`rsi_momentum`

## Rationale

The Relative Strength Index (RSI) is typically used as an overbought/oversold oscillator. However, it can also be used as a momentum indicator. The 50 level on the RSI is considered the dividing line between bullish and bearish momentum. Crossing above 50 indicates that average gains are starting to outpace average losses, signaling a potential trend shift or momentum burst.

## Signal Logic

### Buy (Long Entry)

1. `RSI crosses UP through the 50 level` — signals a shift from bearish to bullish momentum.
2. Optional: `RSI current - 50 >= min_cross_distance` — ensures a decisive cross.

### Sell (Long Exit)

1. `RSI crosses DOWN through the 50 level` — signals a shift from bullish to bearish momentum.
2. Optional: `50 - RSI current >= min_cross_distance` — ensures a decisive cross.

## Default Parameters

| Parameter | Default | Notes |
|---|---|---|
| `rsi_period` | 14 | Lookback window for RSI calculation |
| `midline` | 50 | The momentum threshold level |
| `min_cross_distance` | 0 | Minimum distance above/below midline to confirm the cross |

## Minimum Data Required

`rsi_period + 2` candles (default: 16)

## Backtest Considerations

- Often produces earlier signals than EMA crossovers.
- High signal frequency: works best on higher timeframes (1h+) to avoid noise.
- Can be used as a "fast" entry strategy to be confirmed by other trend indicators.
- In choppy markets, it can produce many whipsaws around the 50 level.

## Risk Notes

- Pure momentum strategies are prone to "fakeouts" where momentum spikes and then immediately reverses.
- Use with tight stop losses or combine with trend filters for better reliability.
