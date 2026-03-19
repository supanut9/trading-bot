from __future__ import annotations

from decimal import Decimal

from app.domain.strategies.rule_builder import (
    RuleBuilderStrategyConfig,
    StrategyRuleCondition,
    StrategyRuleGroup,
)
from app.interfaces.api.schemas import (
    StrategyRuleBuilderRequest,
    StrategyRuleConditionRequest,
    StrategyRuleGroupRequest,
)


def to_rule_builder_config(
    request: StrategyRuleBuilderRequest | None,
) -> RuleBuilderStrategyConfig | None:
    if request is None:
        return None
    return RuleBuilderStrategyConfig(
        shared_filters=_to_rule_group(request.shared_filters),
        buy_rules=_to_rule_group(request.buy_rules),
        sell_rules=_to_rule_group(request.sell_rules),
    )


def to_rule_builder_request(
    config: RuleBuilderStrategyConfig | None,
) -> StrategyRuleBuilderRequest | None:
    if config is None:
        return None
    return StrategyRuleBuilderRequest(
        shared_filters=_to_rule_group_request(config.shared_filters),
        buy_rules=_to_rule_group_request(config.buy_rules),
        sell_rules=_to_rule_group_request(config.sell_rules),
    )


def _to_rule_group(request: StrategyRuleGroupRequest) -> StrategyRuleGroup:
    return StrategyRuleGroup(
        logic=request.logic,
        conditions=tuple(_to_rule_condition(condition) for condition in request.conditions),
    )


def _to_rule_condition(request: StrategyRuleConditionRequest) -> StrategyRuleCondition:
    return StrategyRuleCondition(
        indicator=request.indicator,
        operator=request.operator,
        fast_period=request.fast_period,
        slow_period=request.slow_period,
        period=request.period,
        threshold=Decimal(str(request.threshold)) if request.threshold is not None else None,
    )


def _to_rule_group_request(group: StrategyRuleGroup) -> StrategyRuleGroupRequest:
    return StrategyRuleGroupRequest(
        logic=group.logic,
        conditions=[_to_rule_condition_request(condition) for condition in group.conditions],
    )


def _to_rule_condition_request(condition: StrategyRuleCondition) -> StrategyRuleConditionRequest:
    return StrategyRuleConditionRequest(
        indicator=condition.indicator,
        operator=condition.operator,
        fast_period=condition.fast_period,
        slow_period=condition.slow_period,
        period=condition.period,
        threshold=condition.threshold,
    )
