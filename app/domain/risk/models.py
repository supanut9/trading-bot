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


@dataclass(frozen=True, slots=True)
class PortfolioState:
    account_equity: Decimal
    open_positions: int
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
