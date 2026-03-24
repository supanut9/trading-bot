export type RuntimeStrategyName =
  | "ema_crossover"
  | "ema_adx_trend"
  | "rule_builder"
  | "macd_crossover"
  | "mean_reversion_bollinger"
  | "rsi_momentum"
  | "breakout_atr";

export type BacktestStrategyName =
  | RuntimeStrategyName
  | "ema_adx_trend_volume"
  | "ml_signal";

type StrategyDefinition<TName extends string> = {
  name: TName;
  label: string;
  description: string;
};

export const runtimeStrategyCatalog: StrategyDefinition<RuntimeStrategyName>[] = [
  {
    name: "ema_crossover",
    label: "ema_crossover",
    description:
      "Baseline two-EMA crossover. Runtime can combine it with the repo-wide RSI, volume, and ADX filters without changing the persisted operator schema.",
  },
  {
    name: "ema_adx_trend",
    label: "ema_adx_trend",
    description:
      "Two-EMA crossover with a fixed EMA 100 trend filter and ADX 14 / 20 confirmation. It stays crossover-only and does not add strategy-specific stop or take-profit handling.",
  },
  {
    name: "rule_builder",
    label: "rule_builder",
    description:
      "Operator-editable deterministic rules for backtest parity and research. Runtime keeps the same persisted fast/slow fields but resolves actual behavior from the rule payload.",
  },
  {
    name: "macd_crossover",
    label: "macd_crossover",
    description:
      "Momentum crossover using MACD fast, slow, and signal periods. Suitable when you want a smoother crossover than plain EMAs.",
  },
  {
    name: "mean_reversion_bollinger",
    label: "mean_reversion_bollinger",
    description:
      "Bollinger-band mean reversion with RSI confirmation. Designed for pullback behavior rather than trend continuation.",
  },
  {
    name: "rsi_momentum",
    label: "rsi_momentum",
    description:
      "Single-indicator momentum strategy driven by RSI thresholds. Useful for a simpler oscillator-driven comparison baseline.",
  },
  {
    name: "breakout_atr",
    label: "breakout_atr",
    description:
      "Breakout strategy with ATR expansion and ATR-based stop assumptions. Built for volatility expansion rather than crossover timing.",
  },
];

export const backtestStrategyCatalog: StrategyDefinition<BacktestStrategyName>[] = [
  ...runtimeStrategyCatalog,
  {
    name: "ema_adx_trend_volume",
    label: "ema_adx_trend_volume",
    description:
      "Long-only EMA 20/50 crossover with close above EMA 100, ADX 14 >= 20, and volume above volume EMA 20 × 1.2. Backtest exits use the 10-candle swing low as stop, fixed 2R take profit, and 1% equity risk-to-stop sizing with stop-first intrabar handling.",
  },
  {
    name: "ml_signal",
    label: "ml_signal",
    description:
      "Model-backed strategy using the current ML registry. This is the supported ML path; the older explicit xgboost-only legacy option is no longer surfaced in the operator catalog.",
  },
];

export function describeRuntimeStrategy(strategyName: string): string {
  return (
    runtimeStrategyCatalog.find((entry) => entry.name === strategyName)?.description ??
    "No strategy description is available for this runtime selection."
  );
}

export function describeBacktestStrategy(strategyName: string): string {
  return (
    backtestStrategyCatalog.find((entry) => entry.name === strategyName)?.description ??
    "No strategy description is available for this backtest selection."
  );
}
