from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.strategies.base import Candle
from app.domain.strategies.rule_builder import (
    RuleBuilderStrategy,
    RuleBuilderStrategyConfig,
    StrategyRuleCondition,
    StrategyRuleGroup,
)


def build_candles(closes: list[int]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close),
                close_price=Decimal(close),
                volume=Decimal("1"),
            )
        )
    return candles


def test_rule_builder_emits_buy_signal_from_bullish_ema_cross() -> None:
    strategy = RuleBuilderStrategy(
        RuleBuilderStrategyConfig(
            shared_filters=StrategyRuleGroup(logic="all", conditions=()),
            buy_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bullish",
                        fast_period=3,
                        slow_period=5,
                    ),
                ),
            ),
            sell_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bearish",
                        fast_period=3,
                        slow_period=5,
                    ),
                ),
            ),
        )
    )

    signal = strategy.evaluate(build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20]))

    assert signal is not None
    assert signal.action == "buy"
    assert "buy rules matched" in signal.reason


def test_rule_builder_shared_filter_can_block_signal() -> None:
    strategy = RuleBuilderStrategy(
        RuleBuilderStrategyConfig(
            shared_filters=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="price_vs_ema",
                        operator="below",
                        period=3,
                    ),
                ),
            ),
            buy_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bullish",
                        fast_period=3,
                        slow_period=5,
                    ),
                ),
            ),
            sell_rules=StrategyRuleGroup(
                logic="all",
                conditions=(
                    StrategyRuleCondition(
                        indicator="ema_cross",
                        operator="bearish",
                        fast_period=3,
                        slow_period=5,
                    ),
                ),
            ),
        )
    )

    signal = strategy.evaluate(build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20]))

    assert signal is None


def test_rule_builder_config_reports_required_candles_from_largest_condition() -> None:
    config = RuleBuilderStrategyConfig(
        shared_filters=StrategyRuleGroup(
            logic="all",
            conditions=(
                StrategyRuleCondition(
                    indicator="rsi_threshold",
                    operator="below",
                    period=14,
                    threshold=Decimal("40"),
                ),
            ),
        ),
        buy_rules=StrategyRuleGroup(
            logic="all",
            conditions=(
                StrategyRuleCondition(
                    indicator="price_vs_ema",
                    operator="above",
                    period=9,
                ),
            ),
        ),
        sell_rules=StrategyRuleGroup(
            logic="all",
            conditions=(
                StrategyRuleCondition(
                    indicator="ema_cross",
                    operator="bearish",
                    fast_period=9,
                    slow_period=21,
                ),
            ),
        ),
    )

    assert config.minimum_candles() == 22


def test_rule_builder_requires_buy_and_sell_rules() -> None:
    config = RuleBuilderStrategyConfig(
        shared_filters=StrategyRuleGroup(logic="all", conditions=()),
        buy_rules=StrategyRuleGroup(logic="all", conditions=()),
        sell_rules=StrategyRuleGroup(logic="all", conditions=()),
    )

    with pytest.raises(ValueError, match="buy rules must include at least one condition"):
        config.validate()
