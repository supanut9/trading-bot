from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.indicators import calculate_ema, calculate_rsi, latest_ema

RuleGroupLogic = Literal["all", "any"]
RuleIndicator = Literal["ema_cross", "price_vs_ema", "rsi_threshold"]
RuleOperator = Literal["bullish", "bearish", "above", "below"]


@dataclass(frozen=True, slots=True)
class StrategyRuleCondition:
    indicator: RuleIndicator
    operator: RuleOperator
    fast_period: int | None = None
    slow_period: int | None = None
    period: int | None = None
    threshold: Decimal | None = None

    def minimum_candles(self) -> int:
        if self.indicator == "ema_cross":
            if self.fast_period is None or self.slow_period is None:
                raise ValueError("ema_cross requires fast_period and slow_period")
            if self.fast_period <= 0 or self.slow_period <= 0:
                raise ValueError("EMA periods must be positive")
            if self.fast_period >= self.slow_period:
                raise ValueError("fast period must be smaller than slow period")
            if self.operator not in {"bullish", "bearish"}:
                raise ValueError("ema_cross supports bullish or bearish operator")
            return self.slow_period + 1

        if self.indicator == "price_vs_ema":
            if self.period is None or self.period <= 0:
                raise ValueError("price_vs_ema requires a positive period")
            if self.operator not in {"above", "below"}:
                raise ValueError("price_vs_ema supports above or below operator")
            return self.period

        if self.indicator == "rsi_threshold":
            if self.period is None or self.period <= 0:
                raise ValueError("rsi_threshold requires a positive period")
            if self.threshold is None:
                raise ValueError("rsi_threshold requires a threshold")
            if self.threshold <= Decimal("0") or self.threshold >= Decimal("100"):
                raise ValueError("RSI threshold must be between 0 and 100")
            if self.operator not in {"above", "below"}:
                raise ValueError("rsi_threshold supports above or below operator")
            return self.period + 1

        raise ValueError(f"unsupported indicator: {self.indicator}")

    def evaluate(self, candles: Sequence[Candle]) -> bool:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        closes = [candle.close_price for candle in ordered_candles]
        if len(closes) < self.minimum_candles():
            return False

        if self.indicator == "ema_cross":
            assert self.fast_period is not None
            assert self.slow_period is not None
            fast_emas = calculate_ema(closes, self.fast_period)
            slow_emas = calculate_ema(closes, self.slow_period)
            fast_previous, fast_current = fast_emas[-2], fast_emas[-1]
            slow_previous, slow_current = slow_emas[-2], slow_emas[-1]
            if self.operator == "bullish":
                return fast_previous <= slow_previous and fast_current > slow_current
            return fast_previous >= slow_previous and fast_current < slow_current

        if self.indicator == "price_vs_ema":
            assert self.period is not None
            current_close = closes[-1]
            ema_value = latest_ema(closes, self.period)
            if self.operator == "above":
                return current_close > ema_value
            return current_close < ema_value

        assert self.indicator == "rsi_threshold"
        assert self.period is not None
        assert self.threshold is not None
        rsi_value = calculate_rsi(closes[-(self.period + 1) :], self.period)
        if self.operator == "above":
            return rsi_value > self.threshold
        return rsi_value < self.threshold

    def describe(self) -> str:
        if self.indicator == "ema_cross":
            return (
                f"EMA {self.fast_period}/{self.slow_period} "
                f"{'bullish' if self.operator == 'bullish' else 'bearish'} cross"
            )
        if self.indicator == "price_vs_ema":
            return f"price {self.operator} EMA {self.period}"
        return f"RSI {self.period} {self.operator} {self.threshold}"


@dataclass(frozen=True, slots=True)
class StrategyRuleGroup:
    logic: RuleGroupLogic = "all"
    conditions: tuple[StrategyRuleCondition, ...] = ()

    def validate(self) -> None:
        if self.logic not in {"all", "any"}:
            raise ValueError(f"unsupported group logic: {self.logic}")
        for condition in self.conditions:
            condition.minimum_candles()

    def minimum_candles(self) -> int:
        if not self.conditions:
            return 0
        return max(condition.minimum_candles() for condition in self.conditions)

    def evaluate(self, candles: Sequence[Candle]) -> bool:
        if not self.conditions:
            return True
        results = [condition.evaluate(candles) for condition in self.conditions]
        if self.logic == "all":
            return all(results)
        return any(results)

    def describe(self) -> str:
        if not self.conditions:
            return "no conditions"
        separator = " and " if self.logic == "all" else " or "
        return separator.join(condition.describe() for condition in self.conditions)


@dataclass(frozen=True, slots=True)
class RuleBuilderStrategyConfig:
    shared_filters: StrategyRuleGroup
    buy_rules: StrategyRuleGroup
    sell_rules: StrategyRuleGroup

    def validate(self) -> None:
        self.shared_filters.validate()
        self.buy_rules.validate()
        self.sell_rules.validate()
        if not self.buy_rules.conditions:
            raise ValueError("buy rules must include at least one condition")
        if not self.sell_rules.conditions:
            raise ValueError("sell rules must include at least one condition")

    def minimum_candles(self) -> int:
        self.validate()
        return max(
            self.shared_filters.minimum_candles(),
            self.buy_rules.minimum_candles(),
            self.sell_rules.minimum_candles(),
        )


class RuleBuilderStrategy:
    def __init__(self, config: RuleBuilderStrategyConfig) -> None:
        config.validate()
        self._config = config

    def evaluate(self, candles: Sequence[Candle]) -> Signal | None:
        if not self._config.shared_filters.evaluate(candles):
            return None

        buy_matches = self._config.buy_rules.evaluate(candles)
        sell_matches = self._config.sell_rules.evaluate(candles)

        if buy_matches and sell_matches:
            return None
        if buy_matches:
            return Signal(
                action="buy",
                reason=self._build_reason("buy", self._config.buy_rules),
            )
        if sell_matches:
            return Signal(
                action="sell",
                reason=self._build_reason("sell", self._config.sell_rules),
            )
        return None

    def _build_reason(self, side: str, group: StrategyRuleGroup) -> str:
        shared = self._config.shared_filters.describe()
        specific = group.describe()
        if self._config.shared_filters.conditions:
            return f"{side} rules matched after shared filters: {shared}; {specific}"
        return f"{side} rules matched: {specific}"
