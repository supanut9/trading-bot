# MACD Signal-Line Crossover Strategy

## Strategy Name

`macd_crossover`

## Rationale

MACD (Moving Average Convergence Divergence) is a momentum-oscillator that
removes lag from two EMA lines and presents the relationship as a single
oscillating line. The signal-line crossover provides smoother, more confirmed
entries than raw EMA crossovers because the histogram confirmation filters
out crossovers with weak momentum.

## Signal Logic

### Buy (Long Entry)

1. `MACD line crosses above Signal line` — bullish momentum crossover
2. `histogram > 0` after the cross — momentum confirmation (not a false cross)

### Sell (Long Exit)

1. `MACD line crosses below Signal line` — bearish momentum crossover
2. `histogram < 0` after the cross — confirmation of bearish momentum

## Default Parameters

| Parameter | Default | Notes |
|---|---|---|
| `fast_period` | 12 | Fast EMA period for MACD line |
| `slow_period` | 26 | Slow EMA period for MACD line |
| `signal_period` | 9 | EMA period for Signal line |

## Minimum Data Required

`slow_period + signal_period + 1` candles (default: 36)

## Backtest Considerations

- Works well on trending symbols at 1h-4h timeframes
- The histogram confirmation reduces whipsaws compared to raw MACD cross
- Fewer signals than EMA crossover but higher quality
- Recommended to combine with a fee model ≥ 0.05% for realistic signal filtering

## Risk Notes

- Lagging indicator: entry will be after the trend has already started
- In strongly ranging markets MACD oscillates rapidly near zero → many small losses
