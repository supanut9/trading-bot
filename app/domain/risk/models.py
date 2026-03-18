from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.domain.strategies.base import Signal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    risk_per_trade_pct: Decimal
    max_open_positions: int
    max_daily_loss_pct: Decimal
    paper_trading_only: bool = True
    live_trading_halted: bool = False
    live_max_order_notional: Decimal | None = None
    live_max_position_quantity: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PortfolioState:
    account_equity: Decimal
    open_positions: int
    current_position_quantity: Decimal
    daily_realized_loss_pct: Decimal
    trading_mode: Literal["paper", "live"]


@dataclass(frozen=True, slots=True)
class TradeContext:
    signal: Signal
    entry_price: Decimal


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reason: str
    quantity: Decimal = Decimal("0")
