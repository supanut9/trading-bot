from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.risk import PortfolioState, RiskLimits, RiskService, TradeContext
from app.domain.strategies.base import Candle, Strategy
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy

MAINTENANCE_MARGIN_RATE = Decimal("0.004")


@dataclass(frozen=True, slots=True)
class LiquidationEvent:
    candle_open_time: datetime
    position_side: str  # "long" or "short"
    entry_price: Decimal
    liquidation_price: Decimal
    breach_price: Decimal  # candle low (long) or high (short) that crossed


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    in_sample: "BacktestResult"
    out_of_sample: "BacktestResult"
    split_ratio: Decimal
    in_sample_candles: int
    out_of_sample_candles: int
    return_degradation_pct: Decimal
    overfitting_warning: bool
    overfitting_threshold_pct: Decimal


@dataclass(frozen=True, slots=True)
class BacktestExecution:
    action: str
    price: Decimal
    fill_price: Decimal
    quantity: Decimal
    fee: Decimal
    realized_pnl: Decimal
    reason: str
    candle_open_time: datetime = datetime.min
    liquidation_price: Decimal | None = None
    was_liquidated: bool = False


@dataclass(frozen=True, slots=True)
class BacktestResult:
    starting_equity: Decimal
    ending_equity: Decimal
    total_return_pct: Decimal
    realized_pnl: Decimal
    total_fees_paid: Decimal
    max_drawdown_pct: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    slippage_pct: Decimal
    fee_pct: Decimal
    executions: tuple[BacktestExecution, ...]
    candles: tuple[Candle, ...] = ()
    leverage: int = 1
    margin_mode: str = "ISOLATED"
    liquidation_count: int = 0
    liquidation_events: tuple[LiquidationEvent, ...] = ()
    stop_loss_count: int = 0


class BacktestService:
    def __init__(
        self,
        *,
        strategy: Strategy | None = None,
        risk_service: RiskService | None = None,
        starting_equity: Decimal = Decimal("10000"),
        slippage_pct: Decimal = Decimal("0"),
        fee_pct: Decimal = Decimal("0"),
        trading_mode: str = "SPOT",
        leverage: int = 1,
        margin_mode: str = "ISOLATED",
        stop_loss_atr_multiplier: Decimal = Decimal("0"),
        stop_loss_atr_period: int = 14,
        trailing_stop_enabled: bool = False,
        volatility_sizing_enabled: bool = False,
        volatility_sizing_atr_period: int = 14,
    ) -> None:
        self._strategy = strategy or EmaCrossoverStrategy()
        self._volatility_sizing_enabled = volatility_sizing_enabled
        self._volatility_sizing_atr_period = volatility_sizing_atr_period
        self._risk = risk_service or RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal("0.01"),
                max_open_positions=1,
                max_daily_loss_pct=Decimal("0.03"),
                paper_trading_only=True,
                volatility_sizing_enabled=volatility_sizing_enabled,
            )
        )
        self._starting_equity = starting_equity
        self._slippage_pct = slippage_pct
        self._fee_pct = fee_pct
        self._trading_mode = trading_mode.upper()
        self._leverage = leverage
        self._margin_mode = margin_mode
        # Stop loss: multiplier=0 means disabled
        self._stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self._stop_loss_atr_period = stop_loss_atr_period
        self._trailing_stop_enabled = trailing_stop_enabled

    def run(self, candles: Sequence[Candle]) -> BacktestResult:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        peak_equity = self._starting_equity
        max_drawdown_pct = Decimal("0")
        realized_pnl = Decimal("0")
        total_fees_paid = Decimal("0")
        winning_trades = 0
        losing_trades = 0
        executions: list[BacktestExecution] = []

        position_quantity = Decimal("0")
        average_entry_fill_price: Decimal | None = None
        pending_entry_fee = Decimal("0")
        current_liquidation_price: Decimal | None = None
        current_position_side: str | None = None
        liquidation_events: list[LiquidationEvent] = []
        current_stop_price: Decimal | None = None
        highest_price_since_entry: Decimal | None = None
        stop_loss_count: int = 0

        for index in range(len(ordered_candles)):
            candle = ordered_candles[index]

            # Liquidation check (before strategy signal)
            if (
                self._leverage > 1
                and self._trading_mode == "FUTURES"
                and self._margin_mode == "ISOLATED"
                and position_quantity != Decimal("0")
                and current_liquidation_price is not None
                and current_position_side is not None
                and self._check_liquidation(
                    candle=candle,
                    position_side=current_position_side,
                    liquidation_price=current_liquidation_price,
                    margin_mode=self._margin_mode,
                )
            ):
                liq_price = current_liquidation_price
                if position_quantity > Decimal("0"):  # long
                    exit_fee = liq_price * position_quantity * self._fee_pct
                    trade_pnl = (
                        (liq_price - average_entry_fill_price) * position_quantity
                        - pending_entry_fee
                        - exit_fee
                    )
                    liq_action = "sell"
                else:  # short
                    exit_fee = liq_price * abs(position_quantity) * self._fee_pct
                    trade_pnl = (
                        (average_entry_fill_price - liq_price) * abs(position_quantity)
                        - pending_entry_fee
                        - exit_fee
                    )
                    liq_action = "buy"
                realized_pnl += trade_pnl
                total_fees_paid += exit_fee
                if trade_pnl > Decimal("0"):
                    winning_trades += 1
                elif trade_pnl < Decimal("0"):
                    losing_trades += 1
                breach_price = (
                    candle.low_price if current_position_side == "long" else candle.high_price
                )
                liquidation_events.append(
                    LiquidationEvent(
                        candle_open_time=candle.open_time,
                        position_side=current_position_side,
                        entry_price=average_entry_fill_price,
                        liquidation_price=liq_price,
                        breach_price=breach_price,
                    )
                )
                executions.append(
                    BacktestExecution(
                        action=liq_action,
                        price=liq_price,
                        fill_price=liq_price,
                        quantity=abs(position_quantity),
                        fee=exit_fee,
                        realized_pnl=trade_pnl,
                        reason="liquidated",
                        candle_open_time=candle.open_time,
                        liquidation_price=liq_price,
                        was_liquidated=True,
                    )
                )
                position_quantity = Decimal("0")
                average_entry_fill_price = None
                pending_entry_fee = Decimal("0")
                current_liquidation_price = None
                current_position_side = None
                continue

            # Stop loss check: intrabar breach via candle low (long) or high (short)
            if (
                position_quantity != Decimal("0")
                and current_stop_price is not None
                and self._stop_loss_atr_multiplier > Decimal("0")
            ):
                stop_breached = False
                stop_fill_price = current_stop_price
                stop_action = "sell"
                stop_exit_fee = Decimal("0")
                stop_pnl = Decimal("0")
                if position_quantity > Decimal("0") and candle.low_price <= current_stop_price:
                    stop_breached = True
                    stop_fill_price = (
                        candle.open_price
                        if candle.open_price < current_stop_price
                        else current_stop_price
                    )
                    stop_action = "sell"
                    stop_exit_fee = stop_fill_price * position_quantity * self._fee_pct
                    stop_pnl = (
                        (stop_fill_price - average_entry_fill_price) * position_quantity
                        - pending_entry_fee
                        - stop_exit_fee
                    )
                elif position_quantity < Decimal("0") and candle.high_price >= current_stop_price:
                    stop_breached = True
                    stop_fill_price = (
                        candle.open_price
                        if candle.open_price > current_stop_price
                        else current_stop_price
                    )
                    stop_action = "buy"
                    stop_exit_fee = stop_fill_price * abs(position_quantity) * self._fee_pct
                    stop_pnl = (
                        (average_entry_fill_price - stop_fill_price) * abs(position_quantity)
                        - pending_entry_fee
                        - stop_exit_fee
                    )
                if stop_breached:
                    realized_pnl += stop_pnl
                    total_fees_paid += stop_exit_fee
                    stop_loss_count += 1
                    if stop_pnl > Decimal("0"):
                        winning_trades += 1
                    elif stop_pnl < Decimal("0"):
                        losing_trades += 1
                    executions.append(
                        BacktestExecution(
                            action=stop_action,
                            price=current_stop_price,
                            fill_price=stop_fill_price,
                            quantity=abs(position_quantity),
                            fee=stop_exit_fee,
                            realized_pnl=stop_pnl,
                            reason="stop_loss",
                            candle_open_time=candle.open_time,
                        )
                    )
                    position_quantity = Decimal("0")
                    average_entry_fill_price = None
                    pending_entry_fee = Decimal("0")
                    current_liquidation_price = None
                    current_position_side = None
                    current_stop_price = None
                    highest_price_since_entry = None
                    continue

            marked_equity = self._mark_to_market_equity(
                realized_pnl=realized_pnl,
                position_quantity=position_quantity,
                average_entry_fill_price=average_entry_fill_price,
                mark_price=candle.close_price,
            )
            peak_equity = max(peak_equity, marked_equity)
            max_drawdown_pct = self._update_drawdown(
                current_equity=marked_equity,
                peak_equity=peak_equity,
                current_max_drawdown_pct=max_drawdown_pct,
            )

            # Update trailing stop every candle while in position
            if (
                self._trailing_stop_enabled
                and position_quantity != Decimal("0")
                and current_stop_price is not None
                and self._stop_loss_atr_multiplier > Decimal("0")
            ):
                trail_atr = self._compute_atr_for_candles(ordered_candles[: index + 1])
                if trail_atr is not None:
                    multiplier = self._stop_loss_atr_multiplier
                    if position_quantity > Decimal("0"):
                        new_high = max(
                            highest_price_since_entry or candle.close_price, candle.close_price
                        )
                        new_stop = new_high - trail_atr * multiplier
                        if new_stop > current_stop_price:
                            current_stop_price = new_stop
                            highest_price_since_entry = new_high
                    else:
                        new_low = min(
                            highest_price_since_entry or candle.close_price, candle.close_price
                        )
                        new_stop = new_low + trail_atr * multiplier
                        if new_stop < current_stop_price:
                            current_stop_price = new_stop
                            highest_price_since_entry = new_low

            signal = self._strategy.evaluate(ordered_candles[: index + 1])
            if signal is None:
                continue

            portfolio = self._build_portfolio_state(
                current_equity=marked_equity,
                realized_pnl=realized_pnl,
                position_quantity=position_quantity,
            )
            atr_for_sizing = (
                self._compute_atr_for_sizing(ordered_candles[: index + 1])
                if self._volatility_sizing_enabled
                else None
            )
            decision = self._risk.evaluate(
                portfolio=portfolio,
                trade=TradeContext(
                    signal=signal,
                    entry_price=candle.close_price,
                    atr_value=atr_for_sizing,
                ),
            )
            if not decision.approved:
                continue

            if signal.action == "buy":
                # Already long, ignore same-side signal
                if position_quantity > Decimal("0"):
                    continue

                fill_price = candle.close_price * (Decimal("1") + self._slippage_pct)

                # Closing a short
                if position_quantity < Decimal("0"):
                    exit_fee = fill_price * abs(position_quantity) * self._fee_pct
                    trade_pnl = (
                        (average_entry_fill_price - fill_price) * abs(position_quantity)
                        - pending_entry_fee
                        - exit_fee
                    )
                    realized_pnl += trade_pnl
                    total_fees_paid += exit_fee
                    if trade_pnl > Decimal("0"):
                        winning_trades += 1
                    elif trade_pnl < Decimal("0"):
                        losing_trades += 1
                    executions.append(
                        BacktestExecution(
                            action="buy",
                            price=candle.close_price,
                            fill_price=fill_price,
                            quantity=abs(position_quantity),
                            fee=exit_fee,
                            realized_pnl=trade_pnl,
                            reason=f"close short: {signal.reason}",
                            candle_open_time=candle.open_time,
                        )
                    )
                    position_quantity = Decimal("0")
                    average_entry_fill_price = None
                    pending_entry_fee = Decimal("0")
                    current_liquidation_price = None
                    current_position_side = None
                    current_stop_price = None
                    highest_price_since_entry = None

                # Opening a long
                if position_quantity == Decimal("0"):
                    entry_quantity = decision.quantity * Decimal(self._leverage)
                    entry_fee = fill_price * entry_quantity * self._fee_pct
                    position_quantity = entry_quantity
                    average_entry_fill_price = fill_price
                    pending_entry_fee = entry_fee
                    total_fees_paid += entry_fee
                    # Set ATR-based stop loss on entry
                    if self._stop_loss_atr_multiplier > Decimal("0"):
                        entry_atr = self._compute_atr_for_candles(ordered_candles[: index + 1])
                        if entry_atr is not None:
                            current_stop_price = (
                                fill_price - entry_atr * self._stop_loss_atr_multiplier
                            )
                            highest_price_since_entry = fill_price
                    # Track liquidation
                    current_liq = (
                        self._compute_liquidation_price(
                            side="long",
                            entry_price=fill_price,
                            leverage=self._leverage,
                        )
                        if self._trading_mode == "FUTURES" and self._leverage > 1
                        else None
                    )
                    current_liquidation_price = current_liq
                    current_position_side = "long" if current_liq is not None else None
                    executions.append(
                        BacktestExecution(
                            action="buy",
                            price=candle.close_price,
                            fill_price=fill_price,
                            quantity=position_quantity,
                            fee=entry_fee,
                            realized_pnl=Decimal("0"),
                            reason=signal.reason,
                            candle_open_time=candle.open_time,
                            liquidation_price=current_liq,
                            was_liquidated=False,
                        )
                    )

            elif signal.action == "sell":
                # Already short, ignore same-side signal
                if position_quantity < Decimal("0"):
                    continue

                fill_price = candle.close_price * (Decimal("1") - self._slippage_pct)

                # Closing a long
                if position_quantity > Decimal("0"):
                    exit_fee = fill_price * position_quantity * self._fee_pct
                    trade_pnl = (
                        (fill_price - average_entry_fill_price) * position_quantity
                        - pending_entry_fee
                        - exit_fee
                    )
                    realized_pnl += trade_pnl
                    total_fees_paid += exit_fee
                    if trade_pnl > Decimal("0"):
                        winning_trades += 1
                    elif trade_pnl < Decimal("0"):
                        losing_trades += 1
                    executions.append(
                        BacktestExecution(
                            action="sell",
                            price=candle.close_price,
                            fill_price=fill_price,
                            quantity=position_quantity,
                            fee=exit_fee,
                            realized_pnl=trade_pnl,
                            reason=f"close long: {signal.reason}",
                            candle_open_time=candle.open_time,
                        )
                    )
                    position_quantity = Decimal("0")
                    average_entry_fill_price = None
                    pending_entry_fee = Decimal("0")
                    current_liquidation_price = None
                    current_position_side = None
                    current_stop_price = None
                    highest_price_since_entry = None

                # Opening a short (FUTURES only)
                if self._trading_mode == "FUTURES" and position_quantity == Decimal("0"):
                    entry_quantity = decision.quantity * Decimal(self._leverage)
                    entry_fee = fill_price * entry_quantity * self._fee_pct
                    position_quantity = -entry_quantity  # Negative for shorts
                    average_entry_fill_price = fill_price
                    pending_entry_fee = entry_fee
                    total_fees_paid += entry_fee
                    current_liq = (
                        self._compute_liquidation_price(
                            side="short",
                            entry_price=fill_price,
                            leverage=self._leverage,
                        )
                        if self._leverage > 1
                        else None
                    )
                    current_liquidation_price = current_liq
                    current_position_side = "short" if current_liq is not None else None
                    # Set ATR-based stop loss for short entry
                    if self._stop_loss_atr_multiplier > Decimal("0"):
                        entry_atr = self._compute_atr_for_candles(ordered_candles[: index + 1])
                        if entry_atr is not None:
                            current_stop_price = (
                                fill_price + entry_atr * self._stop_loss_atr_multiplier
                            )
                            highest_price_since_entry = fill_price
                    executions.append(
                        BacktestExecution(
                            action="sell",
                            price=candle.close_price,
                            fill_price=fill_price,
                            quantity=abs(position_quantity),
                            fee=entry_fee,
                            realized_pnl=Decimal("0"),
                            reason=signal.reason,
                            candle_open_time=candle.open_time,
                            liquidation_price=current_liq,
                            was_liquidated=False,
                        )
                    )

        if position_quantity != Decimal("0") and average_entry_fill_price is not None:
            final_candle = ordered_candles[-1]
            final_price = final_candle.close_price

            if position_quantity > Decimal("0"):
                fill_price = final_price * (Decimal("1") - self._slippage_pct)
                exit_fee = fill_price * position_quantity * self._fee_pct
                trade_pnl = (
                    (fill_price - average_entry_fill_price) * position_quantity
                    - pending_entry_fee
                    - exit_fee
                )
                action = "sell"
            else:  # short
                fill_price = final_price * (Decimal("1") + self._slippage_pct)
                exit_fee = fill_price * abs(position_quantity) * self._fee_pct
                trade_pnl = (
                    (average_entry_fill_price - fill_price) * abs(position_quantity)
                    - pending_entry_fee
                    - exit_fee
                )
                action = "buy"

            realized_pnl += trade_pnl
            total_fees_paid += exit_fee
            if trade_pnl > Decimal("0"):
                winning_trades += 1
            elif trade_pnl < Decimal("0"):
                losing_trades += 1
            executions.append(
                BacktestExecution(
                    action=action,
                    price=final_price,
                    fill_price=fill_price,
                    quantity=abs(position_quantity),
                    fee=exit_fee,
                    realized_pnl=trade_pnl,
                    reason="forced close on final candle",
                    candle_open_time=final_candle.open_time,
                )
            )
        ending_equity = self._starting_equity + realized_pnl

        total_return_pct = Decimal("0")
        if self._starting_equity > Decimal("0"):
            total_return_pct = (
                (ending_equity - self._starting_equity) / self._starting_equity
            ) * Decimal("100")

        return BacktestResult(
            starting_equity=self._starting_equity,
            ending_equity=ending_equity,
            total_return_pct=total_return_pct,
            realized_pnl=realized_pnl,
            total_fees_paid=total_fees_paid,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=len(executions),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            slippage_pct=self._slippage_pct,
            fee_pct=self._fee_pct,
            executions=tuple(executions),
            candles=tuple(ordered_candles),
            leverage=self._leverage,
            margin_mode=self._margin_mode,
            liquidation_count=len(liquidation_events),
            liquidation_events=tuple(liquidation_events),
            stop_loss_count=stop_loss_count,
        )

    def run_walk_forward(
        self,
        candles: Sequence[Candle],
        *,
        split_ratio: Decimal = Decimal("0.7"),
        overfitting_threshold_pct: Decimal = Decimal("35"),
    ) -> WalkForwardResult:
        ordered = sorted(candles, key=lambda c: c.open_time)
        split_index = max(1, int(len(ordered) * split_ratio))
        in_sample_candles = ordered[:split_index]
        oos_candles = ordered[split_index:]

        in_sample_result = self.run(in_sample_candles)
        oos_result = self.run(oos_candles)

        if in_sample_result.total_return_pct > Decimal("0"):
            return_degradation_pct = (
                (in_sample_result.total_return_pct - oos_result.total_return_pct)
                / abs(in_sample_result.total_return_pct)
            ) * Decimal("100")
        else:
            return_degradation_pct = Decimal("0")

        return WalkForwardResult(
            in_sample=in_sample_result,
            out_of_sample=oos_result,
            split_ratio=split_ratio,
            in_sample_candles=len(in_sample_candles),
            out_of_sample_candles=len(oos_candles),
            return_degradation_pct=return_degradation_pct,
            overfitting_warning=return_degradation_pct > overfitting_threshold_pct,
            overfitting_threshold_pct=overfitting_threshold_pct,
        )

    def _compute_atr_for_sizing(self, candles: Sequence[Candle]) -> Decimal | None:
        """ATR used for volatility-adjusted position sizing (uses volatility_sizing_atr_period)."""
        from app.domain.strategies.indicators import calculate_atr

        period = self._volatility_sizing_atr_period
        if len(candles) < period + 1:
            return None
        recent = list(candles)[-(period + 1) :]
        try:
            return calculate_atr(
                highs=[c.high_price for c in recent],
                lows=[c.low_price for c in recent],
                closes=[c.close_price for c in recent],
                period=period,
            )
        except ValueError:
            return None

    def _compute_atr_for_candles(self, candles: Sequence[Candle]) -> Decimal | None:
        from app.domain.strategies.indicators import calculate_atr

        period = self._stop_loss_atr_period
        if len(candles) < period + 1:
            return None
        recent = list(candles)[-(period + 1) :]
        try:
            return calculate_atr(
                highs=[c.high_price for c in recent],
                lows=[c.low_price for c in recent],
                closes=[c.close_price for c in recent],
                period=period,
            )
        except ValueError:
            return None

    @staticmethod
    def _compute_liquidation_price(
        *,
        side: str,
        entry_price: Decimal,
        leverage: int,
    ) -> Decimal:
        if side == "long":
            return entry_price * (
                Decimal("1") - Decimal("1") / Decimal(leverage) + MAINTENANCE_MARGIN_RATE
            )
        # short
        return entry_price * (
            Decimal("1") + Decimal("1") / Decimal(leverage) - MAINTENANCE_MARGIN_RATE
        )

    @staticmethod
    def _check_liquidation(
        *,
        candle: "Candle",
        position_side: str,
        liquidation_price: Decimal,
        margin_mode: str,
    ) -> bool:
        if margin_mode == "CROSS":
            return False
        if position_side == "long":
            return candle.low_price <= liquidation_price
        return candle.high_price >= liquidation_price

    def _build_portfolio_state(
        self,
        *,
        current_equity: Decimal,
        realized_pnl: Decimal,
        position_quantity: Decimal,
    ) -> PortfolioState:
        daily_realized_loss_pct = Decimal("0")
        if self._starting_equity > Decimal("0") and realized_pnl < Decimal("0"):
            daily_realized_loss_pct = abs(realized_pnl) / self._starting_equity

        return PortfolioState(
            account_equity=current_equity,
            open_positions=1 if position_quantity > Decimal("0") else 0,
            current_position_quantity=position_quantity,
            daily_realized_loss_pct=daily_realized_loss_pct,
            weekly_realized_loss_pct=Decimal("0"),
            concurrent_exposure_pct=Decimal("0"),
            consecutive_losses=0,
            execution_mode="paper",
            trading_mode=self._trading_mode,
        )

    def _mark_to_market_equity(
        self,
        *,
        realized_pnl: Decimal,
        position_quantity: Decimal,
        average_entry_fill_price: Decimal | None,
        mark_price: Decimal,
    ) -> Decimal:
        if position_quantity == Decimal("0") or average_entry_fill_price is None:
            return self._starting_equity + realized_pnl

        if position_quantity > Decimal("0"):
            unrealized_pnl = (mark_price - average_entry_fill_price) * position_quantity
        else:  # short
            unrealized_pnl = (average_entry_fill_price - mark_price) * abs(position_quantity)

        return self._starting_equity + realized_pnl + unrealized_pnl

    @staticmethod
    def _update_drawdown(
        *,
        current_equity: Decimal,
        peak_equity: Decimal,
        current_max_drawdown_pct: Decimal,
    ) -> Decimal:
        if peak_equity <= Decimal("0"):
            return current_max_drawdown_pct
        drawdown_pct = ((peak_equity - current_equity) / peak_equity) * Decimal("100")
        return max(current_max_drawdown_pct, drawdown_pct)
