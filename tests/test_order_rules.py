from decimal import Decimal

import pytest

from app.domain.order_rules import (
    OrderRuleViolation,
    SymbolRules,
    snap_to_step,
    validate_and_snap_quantity,
)


def build_rules(
    *,
    min_qty: str = "0.00001",
    max_qty: str = "9000",
    step_size: str = "0.00001",
    min_notional: str = "10",
    tick_size: str = "0.01",
) -> SymbolRules:
    return SymbolRules(
        exchange="binance",
        symbol="BTC/USDT",
        min_qty=Decimal(min_qty),
        max_qty=Decimal(max_qty),
        step_size=Decimal(step_size),
        min_notional=Decimal(min_notional),
        tick_size=Decimal(tick_size),
    )


def test_snap_to_step_rounds_down() -> None:
    assert snap_to_step(Decimal("0.000123456"), Decimal("0.00001")) == Decimal("0.00012")


def test_snap_to_step_zero_step_returns_value() -> None:
    value = Decimal("1.23456")
    assert snap_to_step(value, Decimal("0")) == value


def test_snap_to_step_exact_multiple_unchanged() -> None:
    assert snap_to_step(Decimal("0.00015"), Decimal("0.00005")) == Decimal("0.00015")


def test_validate_and_snap_returns_snapped_quantity() -> None:
    rules = build_rules(step_size="0.001", min_qty="0.001", min_notional="10")
    qty = validate_and_snap_quantity(Decimal("0.0019"), Decimal("50000"), rules)
    assert qty == Decimal("0.001")


def test_validate_and_snap_raises_when_rounds_to_zero() -> None:
    rules = build_rules(step_size="1", min_qty="1", min_notional="10")
    with pytest.raises(OrderRuleViolation, match="rounds to zero"):
        validate_and_snap_quantity(Decimal("0.5"), Decimal("50000"), rules)


def test_validate_and_snap_raises_when_below_min_qty() -> None:
    rules = build_rules(step_size="0.001", min_qty="0.01", min_notional="5")
    with pytest.raises(OrderRuleViolation, match="below exchange minimum"):
        validate_and_snap_quantity(Decimal("0.005"), Decimal("50000"), rules)


def test_validate_and_snap_raises_when_above_max_qty() -> None:
    rules = build_rules(step_size="0.001", min_qty="0.001", max_qty="0.01", min_notional="5")
    with pytest.raises(OrderRuleViolation, match="exceeds exchange maximum"):
        validate_and_snap_quantity(Decimal("0.1"), Decimal("50000"), rules)


def test_validate_and_snap_raises_when_below_min_notional() -> None:
    rules = build_rules(step_size="0.00001", min_qty="0.00001", min_notional="10")
    with pytest.raises(OrderRuleViolation, match="below exchange minimum"):
        validate_and_snap_quantity(Decimal("0.0001"), Decimal("50"), rules)


def test_validate_and_snap_ignores_zero_max_qty() -> None:
    rules = build_rules(step_size="0.001", min_qty="0.001", max_qty="0", min_notional="10")
    qty = validate_and_snap_quantity(Decimal("1000"), Decimal("50000"), rules)
    assert qty == Decimal("1000")
