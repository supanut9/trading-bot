from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.trade_repository import (
    TradeAnalyticsRow,
    TradeRepository,
)


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    mode: str
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None
    average_win: Decimal | None
    average_loss: Decimal | None
    profit_factor: Decimal | None
    expectancy: Decimal | None
    max_drawdown: Decimal
    open_position_count: int


@dataclass(frozen=True, slots=True)
class EquityCurvePoint:
    mode: str
    recorded_at: datetime
    net_pnl: Decimal
    drawdown: Decimal


@dataclass(frozen=True, slots=True)
class DailyPerformanceRow:
    mode: str
    trade_date: date
    trade_count: int
    closed_trade_count: int
    winning_trades: int
    losing_trades: int
    realized_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class PerformanceAnalytics:
    summaries: list[PerformanceSummary]
    equity_curve: list[EquityCurvePoint]
    daily_rows: list[DailyPerformanceRow]


@dataclass(slots=True)
class _ModeAccumulator:
    total_realized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    trade_count: int = 0
    closed_trade_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")
    net_closed_pnl: Decimal = Decimal("0")
    cumulative_net_pnl: Decimal = Decimal("0")
    peak_net_pnl: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")


@dataclass(slots=True)
class _PositionState:
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal | None = None


@dataclass(slots=True)
class _DailyAccumulator:
    mode: str
    trade_date: date
    trade_count: int = 0
    closed_trade_count: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    realized_pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    net_pnl: Decimal = Decimal("0")


class PerformanceAnalyticsService:
    def __init__(self, session: Session) -> None:
        self._positions = PositionRepository(session)
        self._trades = TradeRepository(session)

    def build(self) -> PerformanceAnalytics:
        trade_rows = self._trades.list_analytics_rows()
        positions = self._positions.list_all()

        mode_totals: dict[str, _ModeAccumulator] = defaultdict(_ModeAccumulator)
        open_position_count: dict[str, int] = defaultdict(int)
        total_unrealized_pnl: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        equity_curve: list[EquityCurvePoint] = []
        daily_accumulators: dict[tuple[str, date], _DailyAccumulator] = {}
        symbol_state: dict[tuple[str, str], _PositionState] = defaultdict(_PositionState)

        for position in positions:
            if position.quantity > Decimal("0"):
                open_position_count[position.mode] += 1
            total_unrealized_pnl[position.mode] += position.unrealized_pnl

        for trade in trade_rows:
            accumulator = mode_totals[trade.mode]
            accumulator.trade_count += 1
            fee = trade.fee_amount or Decimal("0")
            accumulator.total_fees += fee

            state = symbol_state[(trade.mode, trade.symbol)]
            realized_pnl = self._apply_trade(state, trade)
            net_trade_pnl = realized_pnl - fee

            accumulator.total_realized_pnl += realized_pnl
            accumulator.cumulative_net_pnl += net_trade_pnl
            if accumulator.cumulative_net_pnl > accumulator.peak_net_pnl:
                accumulator.peak_net_pnl = accumulator.cumulative_net_pnl
            drawdown = accumulator.peak_net_pnl - accumulator.cumulative_net_pnl
            if drawdown > accumulator.max_drawdown:
                accumulator.max_drawdown = drawdown

            equity_curve.append(
                EquityCurvePoint(
                    mode=trade.mode,
                    recorded_at=trade.created_at,
                    net_pnl=accumulator.cumulative_net_pnl,
                    drawdown=drawdown,
                )
            )

            daily_key = (trade.mode, trade.created_at.date())
            daily_row = daily_accumulators.get(daily_key)
            if daily_row is None:
                daily_row = _DailyAccumulator(
                    mode=trade.mode,
                    trade_date=trade.created_at.date(),
                )
            daily_row.trade_count += 1
            daily_row.realized_pnl += realized_pnl
            daily_row.fees += fee
            daily_row.net_pnl += net_trade_pnl

            if trade.side == "sell":
                accumulator.closed_trade_count += 1
                accumulator.net_closed_pnl += net_trade_pnl
                daily_row.closed_trade_count += 1
                if net_trade_pnl > Decimal("0"):
                    accumulator.winning_trades += 1
                    accumulator.gross_profit += net_trade_pnl
                    daily_row.winning_trades += 1
                elif net_trade_pnl < Decimal("0"):
                    accumulator.losing_trades += 1
                    accumulator.gross_loss += abs(net_trade_pnl)
                    daily_row.losing_trades += 1

            daily_accumulators[daily_key] = daily_row

        modes = sorted(
            set(mode_totals) | set(open_position_count) | set(total_unrealized_pnl),
        )
        summaries = [
            self._build_summary(
                mode=mode,
                accumulator=mode_totals.get(mode, _ModeAccumulator()),
                total_unrealized_pnl=total_unrealized_pnl.get(mode, Decimal("0")),
                open_position_count=open_position_count.get(mode, 0),
            )
            for mode in modes
        ]
        daily_rows = sorted(
            (
                DailyPerformanceRow(
                    mode=row.mode,
                    trade_date=row.trade_date,
                    trade_count=row.trade_count,
                    closed_trade_count=row.closed_trade_count,
                    winning_trades=row.winning_trades,
                    losing_trades=row.losing_trades,
                    realized_pnl=row.realized_pnl,
                    fees=row.fees,
                    net_pnl=row.net_pnl,
                )
                for row in daily_accumulators.values()
            ),
            key=lambda row: (row.trade_date, row.mode),
            reverse=True,
        )
        return PerformanceAnalytics(
            summaries=summaries,
            equity_curve=sorted(
                equity_curve,
                key=lambda point: (point.recorded_at, point.mode),
            ),
            daily_rows=daily_rows,
        )

    @staticmethod
    def _apply_trade(state: _PositionState, trade: TradeAnalyticsRow) -> Decimal:
        quantity = trade.quantity
        price = trade.price
        if trade.side == "buy":
            existing_average = state.average_entry_price or Decimal("0")
            total_cost = (state.quantity * existing_average) + (quantity * price)
            state.quantity += quantity
            state.average_entry_price = total_cost / state.quantity
            return Decimal("0")

        if state.quantity <= Decimal("0") or state.average_entry_price is None:
            return Decimal("0")

        closed_quantity = quantity if quantity <= state.quantity else state.quantity
        realized_pnl = (price - state.average_entry_price) * closed_quantity
        state.quantity -= closed_quantity
        if state.quantity <= Decimal("0"):
            state.quantity = Decimal("0")
            state.average_entry_price = None
        return realized_pnl

    @staticmethod
    def _build_summary(
        *,
        mode: str,
        accumulator: _ModeAccumulator,
        total_unrealized_pnl: Decimal,
        open_position_count: int,
    ) -> PerformanceSummary:
        win_rate_pct = None
        average_win = None
        average_loss = None
        profit_factor = None
        expectancy = None
        if accumulator.closed_trade_count > 0:
            win_rate_pct = (
                Decimal(accumulator.winning_trades)
                / Decimal(accumulator.closed_trade_count)
                * Decimal("100")
            )
            expectancy = accumulator.net_closed_pnl / Decimal(accumulator.closed_trade_count)
        if accumulator.winning_trades > 0:
            average_win = accumulator.gross_profit / Decimal(accumulator.winning_trades)
        if accumulator.losing_trades > 0:
            average_loss = accumulator.gross_loss / Decimal(accumulator.losing_trades)
            if accumulator.gross_profit > Decimal("0"):
                profit_factor = accumulator.gross_profit / accumulator.gross_loss
        elif accumulator.gross_profit > Decimal("0"):
            profit_factor = None

        return PerformanceSummary(
            mode=mode,
            total_realized_pnl=accumulator.total_realized_pnl,
            total_unrealized_pnl=total_unrealized_pnl,
            total_fees=accumulator.total_fees,
            net_pnl=(
                accumulator.total_realized_pnl + total_unrealized_pnl - accumulator.total_fees
            ),
            trade_count=accumulator.trade_count,
            closed_trade_count=accumulator.closed_trade_count,
            winning_trades=accumulator.winning_trades,
            losing_trades=accumulator.losing_trades,
            win_rate_pct=win_rate_pct,
            average_win=average_win,
            average_loss=average_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            max_drawdown=accumulator.max_drawdown,
            open_position_count=open_position_count,
        )
