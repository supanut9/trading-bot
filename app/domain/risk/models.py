from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from app.domain.strategies.base import Signal

if TYPE_CHECKING:
    from app.domain.order_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class RiskLimits:
    risk_per_trade_pct: Decimal
    max_open_positions: int
    max_daily_loss_pct: Decimal
    max_weekly_loss_pct: Decimal = Decimal("0.10")
    max_concurrent_exposure_pct: Decimal = Decimal("1.0")
    max_consecutive_losses: int = 5
    paper_trading_only: bool = True
    live_trading_halted: bool = False
    live_max_order_notional: Decimal | None = None
    live_max_position_quantity: Decimal | None = None
    symbol_rules: SymbolRules | None = field(default=None, compare=True)
    volatility_sizing_enabled: bool = False


@dataclass(frozen=True, slots=True)
class PortfolioState:
    account_equity: Decimal
    open_positions: int
    current_position_quantity: Decimal
    daily_realized_loss_pct: Decimal
    weekly_realized_loss_pct: Decimal
    concurrent_exposure_pct: Decimal
    consecutive_losses: int
    execution_mode: Literal["paper", "live", "shadow"]
    trading_mode: Literal["SPOT", "FUTURES"]


@dataclass(frozen=True, slots=True)
class TradeContext:
    signal: Signal
    entry_price: Decimal
    atr_value: Decimal | None = None


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reason: str
    quantity: Decimal = Decimal("0")
    is_hard_violation: bool = False
