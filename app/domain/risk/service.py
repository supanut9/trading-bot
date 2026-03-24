from decimal import ROUND_DOWN, Decimal

from app.domain.order_rules import OrderRuleViolation, validate_and_snap_quantity
from app.domain.risk.models import PortfolioState, RiskDecision, RiskLimits, TradeContext

MAINTENANCE_MARGIN_RATE = Decimal("0.004")


class RiskService:
    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    def evaluate(self, portfolio: PortfolioState, trade: TradeContext) -> RiskDecision:
        if portfolio.trading_mode == "SPOT":
            is_entry = trade.signal.action == "buy"
        else:  # FUTURES
            # Entry if opening new position or increasing existing one
            if portfolio.current_position_quantity == Decimal("0"):
                is_entry = True
            elif portfolio.current_position_quantity > Decimal("0"):
                is_entry = trade.signal.action == "buy"
            else:  # position < 0 (short)
                is_entry = trade.signal.action == "sell"

        if self._limits.paper_trading_only and portfolio.execution_mode != "paper":
            return RiskDecision(approved=False, reason="live trading is not allowed by risk policy")

        if is_entry and portfolio.execution_mode == "live" and self._limits.live_trading_halted:
            return RiskDecision(approved=False, reason="live trading is halted by configuration")

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_concurrent_positions is not None
            and portfolio.current_position_quantity == Decimal("0")
            and portfolio.open_positions >= self._limits.live_max_concurrent_positions
        ):
            return RiskDecision(
                approved=False,
                reason="live max concurrent positions reached",
                is_hard_violation=True,
            )

        if portfolio.account_equity <= Decimal("0"):
            return RiskDecision(approved=False, reason="account equity must be positive")

        if trade.entry_price <= Decimal("0"):
            return RiskDecision(approved=False, reason="entry price must be positive")

        if is_entry and portfolio.open_positions >= self._limits.max_open_positions:
            return RiskDecision(
                approved=False,
                reason="max open positions reached",
            )

        if is_entry and portfolio.daily_realized_loss_pct >= self._limits.max_daily_loss_pct:
            return RiskDecision(
                approved=False,
                reason="daily loss limit reached",
                is_hard_violation=True,
            )

        if is_entry and portfolio.weekly_realized_loss_pct >= self._limits.max_weekly_loss_pct:
            return RiskDecision(
                approved=False,
                reason="weekly loss limit reached",
                is_hard_violation=True,
            )

        if is_entry and portfolio.consecutive_losses >= self._limits.max_consecutive_losses:
            return RiskDecision(
                approved=False,
                reason=f"max consecutive losses ({self._limits.max_consecutive_losses}) reached",
                is_hard_violation=True,
            )

        if (
            is_entry
            and portfolio.concurrent_exposure_pct >= self._limits.max_concurrent_exposure_pct
        ):
            return RiskDecision(
                approved=False,
                reason="max concurrent exposure reached",
                is_hard_violation=True,
            )

        dollar_risk = portfolio.account_equity * self._limits.risk_per_trade_pct
        # ATR-normalized sizing: target dollar_risk per trade, sized so that one ATR move
        # equals exactly dollar_risk. Falls back to price-based sizing when unavailable.
        use_atr = (
            self._limits.volatility_sizing_enabled
            and trade.atr_value is not None
            and trade.atr_value > Decimal("0")
        )
        divisor = trade.atr_value if use_atr else trade.entry_price
        quantity = (dollar_risk / divisor).quantize(  # type: ignore[operator]
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )

        if quantity <= Decimal("0"):
            return RiskDecision(
                approved=False,
                reason="calculated quantity must be positive",
            )

        if self._limits.symbol_rules is not None:
            try:
                quantity = validate_and_snap_quantity(
                    quantity, trade.entry_price, self._limits.symbol_rules
                )
            except OrderRuleViolation as exc:
                return RiskDecision(approved=False, reason=exc.reason)

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_order_notional is not None
        ):
            order_notional = quantity * trade.entry_price
            if order_notional > self._limits.live_max_order_notional:
                return RiskDecision(
                    approved=False,
                    reason="live order notional exceeds configured limit",
                    is_hard_violation=True,
                )
        else:
            order_notional = quantity * trade.entry_price

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_total_exposure_notional is not None
            and portfolio.total_open_exposure_notional + order_notional
            > self._limits.live_max_total_exposure_notional
        ):
            return RiskDecision(
                approved=False,
                reason="live total exposure exceeds configured limit",
                is_hard_violation=True,
            )

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_symbol_exposure_notional is not None
            and portfolio.current_symbol_exposure_notional + order_notional
            > self._limits.live_max_symbol_exposure_notional
        ):
            return RiskDecision(
                approved=False,
                reason="live symbol exposure exceeds configured limit",
                is_hard_violation=True,
            )

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_strategy_exposure_notional is not None
            and portfolio.current_strategy_exposure_notional + order_notional
            > self._limits.live_max_strategy_exposure_notional
        ):
            return RiskDecision(
                approved=False,
                reason="live strategy exposure exceeds configured limit",
                is_hard_violation=True,
            )

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_symbol_concentration_pct is not None
        ):
            new_total_exposure = portfolio.total_open_exposure_notional + order_notional
            new_symbol_exposure = portfolio.current_symbol_exposure_notional + order_notional
            if (
                new_total_exposure > Decimal("0")
                and new_symbol_exposure / new_total_exposure
                > self._limits.live_max_symbol_concentration_pct
            ):
                return RiskDecision(
                    approved=False,
                    reason="live symbol concentration exceeds configured limit",
                    is_hard_violation=True,
                )

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and self._limits.live_max_position_quantity is not None
            and portfolio.current_position_quantity + quantity
            > self._limits.live_max_position_quantity
        ):
            return RiskDecision(
                approved=False,
                reason="live position quantity exceeds configured limit",
                is_hard_violation=True,
            )

        if (
            is_entry
            and portfolio.execution_mode == "live"
            and portfolio.trading_mode == "FUTURES"
            and self._limits.live_futures_margin_mode == "ISOLATED"
            and self._limits.live_futures_min_liquidation_buffer_pct is not None
        ):
            liquidation_buffer_pct = (
                Decimal("1") / Decimal(self._limits.live_futures_leverage)
            ) - MAINTENANCE_MARGIN_RATE
            if liquidation_buffer_pct <= Decimal("0") or (
                liquidation_buffer_pct < self._limits.live_futures_min_liquidation_buffer_pct
            ):
                return RiskDecision(
                    approved=False,
                    reason="live futures liquidation buffer below configured minimum",
                    is_hard_violation=True,
                )

        return RiskDecision(
            approved=True,
            reason="risk checks passed",
            quantity=quantity,
        )
