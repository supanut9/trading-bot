from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SymbolRules:
    exchange: str
    symbol: str
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_notional: Decimal
    tick_size: Decimal


class OrderRuleViolation(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def snap_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round value down to the nearest multiple of step."""
    if step <= Decimal("0"):
        return value
    return (value // step) * step


def snap_to_tick(price: Decimal, tick_size: Decimal) -> Decimal:
    """Round price down to the nearest multiple of tick_size."""
    return snap_to_step(price, tick_size)


def validate_and_snap_quantity(
    quantity: Decimal,
    price: Decimal,
    rules: SymbolRules,
) -> Decimal:
    """
    Snap quantity to step_size and validate all exchange rules.
    Returns the snapped quantity if valid.
    Raises OrderRuleViolation with a descriptive reason if any rule is violated.
    """
    snapped = snap_to_step(quantity, rules.step_size)

    if snapped <= Decimal("0"):
        raise OrderRuleViolation(
            f"quantity {quantity} rounds to zero with step_size {rules.step_size}"
        )

    if snapped < rules.min_qty:
        raise OrderRuleViolation(f"quantity {snapped} is below exchange minimum {rules.min_qty}")

    if rules.max_qty > Decimal("0") and snapped > rules.max_qty:
        raise OrderRuleViolation(f"quantity {snapped} exceeds exchange maximum {rules.max_qty}")

    notional = snapped * price
    if notional < rules.min_notional:
        raise OrderRuleViolation(
            f"order notional {notional:.2f} is below exchange minimum {rules.min_notional}"
        )

    return snapped


def validate_and_snap_price(
    price: Decimal,
    rules: SymbolRules,
) -> Decimal:
    """
    Snap price to tick_size and validate against exchange rules.
    Returns the snapped price if valid.
    Raises OrderRuleViolation with a descriptive reason if any rule is violated.
    """
    snapped = snap_to_tick(price, rules.tick_size)

    if snapped <= Decimal("0"):
        raise OrderRuleViolation(f"price {price} rounds to zero with tick_size {rules.tick_size}")

    return snapped
