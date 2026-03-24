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
    live_max_total_exposure_notional: Decimal | None = None
    live_max_symbol_exposure_notional: Decimal | None = None
    live_max_symbol_concentration_pct: Decimal | None = None
    live_max_concurrent_positions: int | None = None
    live_max_strategy_exposure_notional: Decimal | None = None
    live_futures_leverage: int = 1
    live_futures_margin_mode: Literal["ISOLATED", "CROSS"] = "ISOLATED"
    live_futures_min_liquidation_buffer_pct: Decimal | None = None
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
    total_open_exposure_notional: Decimal = Decimal("0")
    current_symbol_exposure_notional: Decimal = Decimal("0")
    current_strategy_exposure_notional: Decimal = Decimal("0")


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
