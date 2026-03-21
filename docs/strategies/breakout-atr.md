# Breakout + ATR Strategy

## Strategy Name

`breakout_atr`

## Rationale

Markets often oscillate in "channels" before breaking out into sustained trends. A "breakout" is defined by price exceeding a recent high or low. However, to filter out "noise" (false breakouts), the ATR (Average True Range) is used as a volatility filter. A breakout is only considered valid if price moves beyond the channel high/low by a significant multiple of recent volatility.

## Signal Logic

### Buy (Long Entry)

All three conditions must be true:

1. `current_close > breakout_period high` — price đã vượt qua mức cao nhất gần đây.
2. `current_close > period_high + (atr_breakout_multiplier * ATR)` — the breakout is significant compared to recent volatility.
3. `ATR` confirmed from current volatility.

### Sell (Long Exit)

Either condition triggers:

1. `current_close < period_low - (atr_stop_multiplier * ATR)` — a trailing or volatility-based stop loss.
2. `current_close < period_high` — price dropped back into the breakout channel (signaling a failed breakout).

## Default Parameters

| Parameter | Default | Notes |
|---|---|---|
| `breakout_period` | 20 | Lookback window for the high/low channel |
| `atr_period` | 14 | Lookback window for ATR volatility calculation |
| `atr_breakout_multiplier` | 0.5 | Multiple of ATR to confirm breakout above channel high |
| `atr_stop_multiplier` | 2.0 | Multiple of ATR for the exit stop loss |

## Minimum Data Required

`max(breakout_period, atr_period) + 2` candles (default: 22)

## Backtest Considerations

- Best for markets trending in one direction for long periods.
- ATR adjustment allows the strategy to stay in "high-vol" trades longer while keeping tight stops in low-vol regimes.
- Use with 1h, 4h, or 1d timeframes for the best results on major crypto/forex pairs.

## Risk Notes

- High "win rate" is rare; profits come from captured large trends while exiting small "fakeouts" quickly.
- Susceptible to "whipsaw" during sideways volatility spikes.
- Trailing stops are critical: monitor `max_drawdown_pct`.
