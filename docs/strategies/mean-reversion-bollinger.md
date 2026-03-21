# Mean-Reversion Bollinger Band Strategy

## Strategy Name

`mean_reversion_bollinger`

## Rationale

EMA crossover strategies work well in trending markets but generate false entries
during sideways/ranging conditions. The Bollinger Band mean-reversion strategy is
designed specifically for ranging environments where price oscillates between
predictable bounds.

## Signal Logic

### Buy (Long Entry)

All three conditions must be true on the close of the current candle:

1. `close <= lower Bollinger Band` — price has touched or breached the lower band
2. `RSI <= rsi_oversold` — RSI confirms the asset is oversold (default 35)

### Sell (Long Exit)

Either condition triggers on the close:

1. `close >= upper Bollinger Band` — price has reached the mean-reversion target
2. `RSI >= rsi_overbought` — momentum exhausted based on RSI (default 65)

## Default Parameters

| Parameter | Default | Notes |
|---|---|---|
| `bb_period` | 20 | SMA period for Bollinger mid-band |
| `bb_std_dev` | 2.0 | Standard deviations for band width |
| `rsi_period` | 14 | RSI lookback window |
| `rsi_oversold` | 35 | RSI level below which entry is allowed |
| `rsi_overbought` | 65 | RSI level above which exit is triggered |

## Backtest Considerations

- Performs best on sideways/high-volatility symbols
- Expected to underperform during sustained trends (complement with EMA crossover)
- Sensitive to fee costs since entries and exits are closer together
- Recommend reviewing with 1h or 4h timeframes on BTC/USDT or ETH/USDT

## Risk Notes

- Mean-reversion strategies can get trapped during strong directional moves
- Monitor `max_drawdown_pct` closely
- Consider pausing if 3+ consecutive losses occur in a trending market
