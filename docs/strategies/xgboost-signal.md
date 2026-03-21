# XGBoost Signal Strategy

## Overview

XGBoost Signal is a machine-learning-based entry strategy that replaces hand-crafted threshold rules with a gradient-boosted decision tree trained on technical indicator features.

Instead of asking "is fast EMA above slow EMA?", the model asks "given the current combination of EMA spread, RSI, MACD histogram, ATR, volume ratio, and Bollinger Band position, is the next candle likely to close higher?".

## Signal Logic

- **Buy**: model predicts next-candle close > current close (probability above threshold)
- **Sell** (exit / short): model predicts next-candle close < current close
- **Hold**: prediction probability is below confidence threshold (no signal)

## Features

| Feature | Description |
|---|---|
| `ema_diff_pct` | (fast EMA − slow EMA) / close — normalized trend direction |
| `rsi` | 14-period RSI (0–100) |
| `macd_histogram` | MACD line minus signal line |
| `atr_pct` | ATR / close — normalized volatility |
| `volume_ratio` | current volume / 20-period volume MA |
| `bb_position` | (close − lower band) / (upper − lower) — 0 = at lower, 1 = at upper |
| `candle_body_pct` | abs(close − open) / open — candle momentum |
| `high_low_pct` | (high − low) / open — range width |

## Label

Binary classification: `1` if `next_close > current_close`, else `0`.

Optional: regression target (`next_close_pct_change`) for probability-weighted sizing.

## Training

Walk-forward splits prevent look-ahead bias:

1. Sort candles by `open_time` ascending
2. Train on first 70% of candles
3. Validate on remaining 30% (out-of-sample)
4. Report OOS accuracy, precision, recall, and feature importances

Model is saved to `models/xgboost_btcusdt_<timeframe>.json`.

## Configuration

```
STRATEGY_NAME=xgboost_signal
```

Model path and inference threshold are resolved by `ModelRegistry` at startup.

## Retraining

Run `python scripts/train_xgboost.py --symbol BTC/USDT --timeframe 1h` to retrain on the latest candles stored in the database. A new model file is written; the running API will load it on next startup.

## Limitations

- Requires at least 500 candles in the DB to produce a useful training set
- Performance degrades in regimes unseen during training (model does not adapt online)
- Combining with the ADX regime filter and multi-timeframe confirmation is recommended to reduce low-quality entries in ranging markets
- No automatic retraining — operator must retrain when live performance degrades

## Relationship to Other Strategies

This strategy sits at the same layer as `ema_crossover` and `rsi_momentum`. It can be selected via the `strategy_name` field in the backtest API or via operator config. It does not replace rule-based strategies — it is an additional option for comparison in walk-forward and shadow validation.
