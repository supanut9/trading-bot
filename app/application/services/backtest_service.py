from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.domain.risk import PortfolioState, RiskLimits, RiskService, TradeContext
from app.domain.strategies.base import Candle, Strategy
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy


@dataclass(frozen=True, slots=True)
class BacktestExecution:
    action: str
    price: Decimal
    quantity: Decimal
    realized_pnl: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class BacktestResult:
    starting_equity: Decimal
    ending_equity: Decimal
    total_return_pct: Decimal
    realized_pnl: Decimal
    max_drawdown_pct: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    executions: tuple[BacktestExecution, ...]


class BacktestService:
    def __init__(
        self,
        *,
        strategy: Strategy | None = None,
        risk_service: RiskService | None = None,
        starting_equity: Decimal = Decimal("10000"),
    ) -> None:
        self._strategy = strategy or EmaCrossoverStrategy()
        self._risk = risk_service or RiskService(
            RiskLimits(
                risk_per_trade_pct=Decimal("0.01"),
                max_open_positions=1,
                max_daily_loss_pct=Decimal("0.03"),
                paper_trading_only=True,
            )
        )
        self._starting_equity = starting_equity

    def run(self, candles: Sequence[Candle]) -> BacktestResult:
        ordered_candles = sorted(candles, key=lambda candle: candle.open_time)
        peak_equity = self._starting_equity
        max_drawdown_pct = Decimal("0")
        realized_pnl = Decimal("0")
        winning_trades = 0
        losing_trades = 0
        executions: list[BacktestExecution] = []

        position_quantity = Decimal("0")
        average_entry_price: Decimal | None = None

        for index in range(len(ordered_candles)):
            candle = ordered_candles[index]
            marked_equity = self._mark_to_market_equity(
                realized_pnl=realized_pnl,
                position_quantity=position_quantity,
                average_entry_price=average_entry_price,
                mark_price=candle.close_price,
            )
            peak_equity = max(peak_equity, marked_equity)
            max_drawdown_pct = self._update_drawdown(
                current_equity=marked_equity,
                peak_equity=peak_equity,
                current_max_drawdown_pct=max_drawdown_pct,
            )

            signal = self._strategy.evaluate(ordered_candles[: index + 1])
            if signal is None:
                continue

            portfolio = self._build_portfolio_state(
                current_equity=marked_equity,
                realized_pnl=realized_pnl,
                position_quantity=position_quantity,
            )
            decision = self._risk.evaluate(
                portfolio=portfolio,
                trade=TradeContext(signal=signal, entry_price=candle.close_price),
            )
            if not decision.approved:
                continue

            if signal.action == "buy":
                if position_quantity > Decimal("0"):
                    continue

                position_quantity = decision.quantity
                average_entry_price = candle.close_price
                executions.append(
                    BacktestExecution(
                        action="buy",
                        price=candle.close_price,
                        quantity=position_quantity,
                        realized_pnl=Decimal("0"),
                        reason=signal.reason,
                    )
                )
            elif position_quantity > Decimal("0") and average_entry_price is not None:
                trade_pnl = (candle.close_price - average_entry_price) * position_quantity
                realized_pnl += trade_pnl
                if trade_pnl > Decimal("0"):
                    winning_trades += 1
                elif trade_pnl < Decimal("0"):
                    losing_trades += 1
                executions.append(
                    BacktestExecution(
                        action="sell",
                        price=candle.close_price,
                        quantity=position_quantity,
                        realized_pnl=trade_pnl,
                        reason=signal.reason,
                    )
                )
                position_quantity = Decimal("0")
                average_entry_price = None

        if position_quantity > Decimal("0") and average_entry_price is not None:
            final_price = ordered_candles[-1].close_price
            trade_pnl = (final_price - average_entry_price) * position_quantity
            realized_pnl += trade_pnl
            if trade_pnl > Decimal("0"):
                winning_trades += 1
            elif trade_pnl < Decimal("0"):
                losing_trades += 1
            executions.append(
                BacktestExecution(
                    action="sell",
                    price=final_price,
                    quantity=position_quantity,
                    realized_pnl=trade_pnl,
                    reason="forced close on final candle",
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
            max_drawdown_pct=max_drawdown_pct,
            total_trades=len(executions),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            executions=tuple(executions),
        )

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
            trading_mode="paper",
        )

    def _mark_to_market_equity(
        self,
        *,
        realized_pnl: Decimal,
        position_quantity: Decimal,
        average_entry_price: Decimal | None,
        mark_price: Decimal,
    ) -> Decimal:
        if position_quantity <= Decimal("0") or average_entry_price is None:
            return self._starting_equity + realized_pnl

        unrealized_pnl = (mark_price - average_entry_price) * position_quantity
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
