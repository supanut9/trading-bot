from decimal import ROUND_DOWN, Decimal

from app.domain.risk.models import PortfolioState, RiskDecision, RiskLimits, TradeContext


class RiskService:
    def __init__(self, limits: RiskLimits) -> None:
        self._limits = limits

    def evaluate(self, portfolio: PortfolioState, trade: TradeContext) -> RiskDecision:
        is_entry = trade.signal.action == "buy"

        if self._limits.paper_trading_only and portfolio.trading_mode != "paper":
            return RiskDecision(approved=False, reason="live trading is not allowed by risk policy")

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
            )

        position_notional = portfolio.account_equity * self._limits.risk_per_trade_pct
        quantity = (position_notional / trade.entry_price).quantize(
            Decimal("0.00000001"),
            rounding=ROUND_DOWN,
        )

        if quantity <= Decimal("0"):
            return RiskDecision(
                approved=False,
                reason="calculated quantity must be positive",
            )

        return RiskDecision(
            approved=True,
            reason="risk checks passed",
            quantity=quantity,
        )
