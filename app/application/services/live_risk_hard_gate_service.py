from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.position_repository import PositionRepository
from app.infrastructure.database.repositories.trade_repository import TradeRepository


@dataclass(frozen=True, slots=True)
class LiveRiskHardGateReport:
    should_halt: bool
    reason: str | None = None


class LiveRiskHardGateService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._positions = PositionRepository(session)
        self._trades = TradeRepository(session)

    def evaluate(self, exchange: str, symbol: str) -> LiveRiskHardGateReport:
        if not self._settings.live_trading_enabled:
            return LiveRiskHardGateReport(should_halt=False)

        current_time = datetime.now(tz=UTC)

        limit_daily_notional = self._settings.live_max_daily_loss_notional
        if limit_daily_notional is not None:
            daily_loss = self._calculate_realized_loss(
                exchange, symbol, current_time - timedelta(days=1)
            )
            if daily_loss >= limit_daily_notional:
                return LiveRiskHardGateReport(
                    should_halt=True,
                    reason="max_daily_loss_notional_exceeded",
                )

        limit_weekly_notional = self._settings.live_max_weekly_loss_notional
        if limit_weekly_notional is not None:
            weekly_loss = self._calculate_realized_loss(
                exchange, symbol, current_time - timedelta(days=7)
            )
            if weekly_loss >= limit_weekly_notional:
                return LiveRiskHardGateReport(
                    should_halt=True,
                    reason="max_weekly_loss_notional_exceeded",
                )

        limit_exposure = self._settings.live_max_concurrent_exposure_notional
        if limit_exposure is not None:
            position = self._positions.get(exchange=exchange, symbol=symbol, mode="live")
            if (
                position is not None
                and position.quantity > Decimal("0")
                and position.average_entry_price is not None
            ):
                exposure = position.quantity * position.average_entry_price
                if exposure >= limit_exposure:
                    return LiveRiskHardGateReport(
                        should_halt=True,
                        reason="max_concurrent_exposure_notional_exceeded",
                    )

        limit_consec_loss = self._settings.live_consecutive_loss_auto_halt_threshold
        if limit_consec_loss is not None:
            consecutive_losses = self._calculate_consecutive_losses(exchange, symbol)
            if consecutive_losses >= limit_consec_loss:
                return LiveRiskHardGateReport(
                    should_halt=True,
                    reason="consecutive_loss_auto_halt_threshold_exceeded",
                )

        limit_rejects = self._settings.live_repeated_reject_auto_halt_threshold
        if limit_rejects is not None:
            consecutive_rejects = self._calculate_consecutive_rejects(exchange, symbol)
            if consecutive_rejects >= limit_rejects:
                return LiveRiskHardGateReport(
                    should_halt=True,
                    reason="repeated_reject_auto_halt_threshold_exceeded",
                )

        return LiveRiskHardGateReport(should_halt=False)

    def _calculate_realized_loss(self, exchange: str, symbol: str, since: datetime) -> Decimal:
        trade_rows = self._trades.list_analytics_rows()

        @dataclass(slots=True)
        class _PositionState:
            quantity: Decimal = Decimal("0")
            average_entry_price: Decimal | None = None

        state = _PositionState()
        total_loss = Decimal("0")

        for trade in trade_rows:
            if trade.mode != "live" or trade.exchange != exchange or trade.symbol != symbol:
                continue

            fee = trade.fee_amount or Decimal("0")
            quantity = trade.quantity
            price = trade.price
            realized_pnl = Decimal("0")

            if trade.side == "buy":
                existing_average = state.average_entry_price or Decimal("0")
                total_cost = (state.quantity * existing_average) + (quantity * price)
                state.quantity += quantity
                state.average_entry_price = total_cost / state.quantity
            else:
                if state.quantity > Decimal("0") and state.average_entry_price is not None:
                    closed_quantity = quantity if quantity <= state.quantity else state.quantity
                    realized_pnl = (price - state.average_entry_price) * closed_quantity
                    state.quantity -= closed_quantity
                    if state.quantity <= Decimal("0"):
                        state.quantity = Decimal("0")
                        state.average_entry_price = None

            if trade.side == "sell":
                net_trade_pnl = realized_pnl - fee
                # Using >= instead of == allows datetime comparision if date matches exactly.
                # Since since is tz-aware, we MUST assume trade.created_at is UTC.
                # `created_at` in our SQLite setup is usually naive UTC.
                # Let's fix timezone:
                trade_dt = (
                    trade.created_at.replace(tzinfo=UTC)
                    if trade.created_at.tzinfo is None
                    else trade.created_at
                )

                if trade_dt >= since:
                    if net_trade_pnl < Decimal("0"):
                        total_loss += abs(net_trade_pnl)
                    else:
                        total_loss -= net_trade_pnl

        return total_loss

    def _calculate_consecutive_losses(self, exchange: str, symbol: str) -> int:
        trade_rows = self._trades.list_analytics_rows()

        @dataclass(slots=True)
        class _PositionState:
            quantity: Decimal = Decimal("0")
            average_entry_price: Decimal | None = None

        state = _PositionState()
        pnl_sequence: list[Decimal] = []

        for trade in trade_rows:
            if trade.mode != "live" or trade.exchange != exchange or trade.symbol != symbol:
                continue

            fee = trade.fee_amount or Decimal("0")
            quantity = trade.quantity
            price = trade.price
            realized_pnl = Decimal("0")

            if trade.side == "buy":
                existing_average = state.average_entry_price or Decimal("0")
                total_cost = (state.quantity * existing_average) + (quantity * price)
                state.quantity += quantity
                state.average_entry_price = total_cost / state.quantity
            else:
                if state.quantity > Decimal("0") and state.average_entry_price is not None:
                    closed_quantity = quantity if quantity <= state.quantity else state.quantity
                    realized_pnl = (price - state.average_entry_price) * closed_quantity
                    state.quantity -= closed_quantity
                    if state.quantity <= Decimal("0"):
                        state.quantity = Decimal("0")
                        state.average_entry_price = None

            if trade.side == "sell":
                net_trade_pnl = realized_pnl - fee
                pnl_sequence.append(net_trade_pnl)

        consecutive_losses = 0
        for pnl in reversed(pnl_sequence):
            if pnl < Decimal("0"):
                consecutive_losses += 1
            else:
                break
        return consecutive_losses

    def _calculate_consecutive_rejects(self, exchange: str, symbol: str) -> int:
        statement = (
            select(OrderRecord.status)
            .where(
                OrderRecord.mode == "live",
                OrderRecord.exchange == exchange,
                OrderRecord.symbol == symbol,
            )
            .order_by(OrderRecord.created_at.desc(), OrderRecord.id.desc())
            .limit(20)
        )
        statuses = self._session.execute(statement).scalars().all()
        consecutive_rejects = 0
        for status in statuses:
            if status in ("rejected", "review_required"):
                consecutive_rejects += 1
            else:
                break
        return consecutive_rejects
