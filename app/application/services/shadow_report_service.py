from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.backtest_run import BacktestRunRecord
from app.infrastructure.database.repositories.shadow_blocked_signal_repository import (
    ShadowBlockedSignalRepository,
)
from app.infrastructure.database.repositories.shadow_trade_repository import ShadowTradeRepository


@dataclass(frozen=True, slots=True)
class ShadowTradeView:
    id: int
    side: str
    entry_price: Decimal
    simulated_fill_price: Decimal
    simulated_exit_fill_price: Decimal | None
    quantity: Decimal
    entry_fee: Decimal
    exit_fee: Decimal | None
    gross_pnl: Decimal | None
    net_pnl: Decimal | None
    status: str
    client_order_id: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class ShadowBlockedSignalView:
    id: int
    signal_action: str
    signal_reason: str | None
    block_reason: str
    block_source: str
    price: Decimal | None
    client_order_id: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class ShadowQualityReport:
    exchange: str
    symbol: str
    total_shadow_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal
    total_fees_paid: Decimal
    blocked_signal_count: int
    oos_win_rate_pct: Decimal | None
    oos_max_drawdown_pct: Decimal | None
    oos_total_return_pct: Decimal | None
    recent_blocked_signals: list[ShadowBlockedSignalView]
    recent_trades: list[ShadowTradeView]


class ShadowReportService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._shadow_trades = ShadowTradeRepository(session)
        self._blocked_signals = ShadowBlockedSignalRepository(session)

    def get_quality_report(self, *, exchange: str, symbol: str) -> ShadowQualityReport:
        all_trades = self._shadow_trades.list_all(exchange=exchange, symbol=symbol, limit=500)
        closed = [t for t in all_trades if t.status == "closed"]
        open_trades = [t for t in all_trades if t.status == "open"]
        winners = [t for t in closed if (t.net_pnl or Decimal("0")) > Decimal("0")]
        losers = [t for t in closed if (t.net_pnl or Decimal("0")) <= Decimal("0")]

        win_rate_pct = None
        expectancy = None
        max_drawdown_pct = None
        total_net_pnl = sum((t.net_pnl or Decimal("0")) for t in closed)
        total_fees = sum(
            (t.entry_fee or Decimal("0")) + (t.exit_fee or Decimal("0")) for t in all_trades
        )

        if closed:
            win_rate = Decimal(str(len(winners))) / Decimal(str(len(closed)))
            win_rate_pct = win_rate * Decimal("100")

            avg_win = (
                sum(t.net_pnl or Decimal("0") for t in winners) / Decimal(str(len(winners)))
                if winners
                else Decimal("0")
            )
            avg_loss = (
                sum(t.net_pnl or Decimal("0") for t in losers) / Decimal(str(len(losers)))
                if losers
                else Decimal("0")
            )
            expectancy = avg_win * win_rate + avg_loss * (Decimal("1") - win_rate)

            # Max drawdown over cumulative net PnL sequence
            cumulative = Decimal("0")
            peak = Decimal("0")
            max_dd = Decimal("0")
            for t in closed:
                cumulative += t.net_pnl or Decimal("0")
                if cumulative > peak:
                    peak = cumulative
                dd = peak - cumulative
                if dd > max_dd:
                    max_dd = dd
            max_drawdown_pct = (
                (max_dd / peak * Decimal("100")) if peak > Decimal("0") else Decimal("0")
            )

        blocked_records = self._blocked_signals.list_recent(
            exchange=exchange, symbol=symbol, limit=50
        )
        blocked_count = len(
            self._blocked_signals.list_recent(exchange=exchange, symbol=symbol, limit=10000)
        )

        # Walk-forward OOS baseline from most recent qualifying backtest run
        oos_win_rate_pct = None
        oos_max_drawdown_pct = None
        oos_total_return_pct = None
        stmt = (
            select(BacktestRunRecord)
            .where(BacktestRunRecord.exchange == exchange)
            .where(BacktestRunRecord.symbol == symbol)
            .where(BacktestRunRecord.walk_forward_oos_return_pct.isnot(None))
            .order_by(BacktestRunRecord.id.desc())
            .limit(1)
        )
        latest_wf = self._session.execute(stmt).scalar_one_or_none()
        if latest_wf is not None:
            oos_total_return_pct = latest_wf.walk_forward_oos_return_pct
            oos_max_drawdown_pct = latest_wf.walk_forward_oos_drawdown_pct
            # OOS win rate not separately stored in BacktestRunRecord — leave as None

        recent_trades = [
            ShadowTradeView(
                id=t.id,
                side=t.side,
                entry_price=Decimal(str(t.entry_price)),
                simulated_fill_price=Decimal(str(t.simulated_fill_price)),
                simulated_exit_fill_price=(
                    Decimal(str(t.simulated_exit_fill_price))
                    if t.simulated_exit_fill_price is not None
                    else None
                ),
                quantity=Decimal(str(t.quantity)),
                entry_fee=Decimal(str(t.entry_fee)),
                exit_fee=Decimal(str(t.exit_fee)) if t.exit_fee is not None else None,
                gross_pnl=Decimal(str(t.gross_pnl)) if t.gross_pnl is not None else None,
                net_pnl=Decimal(str(t.net_pnl)) if t.net_pnl is not None else None,
                status=t.status,
                client_order_id=t.client_order_id,
                created_at=t.created_at.isoformat(),
            )
            for t in all_trades[-20:]
        ]

        recent_blocked = [
            ShadowBlockedSignalView(
                id=b.id,
                signal_action=b.signal_action,
                signal_reason=b.signal_reason,
                block_reason=b.block_reason,
                block_source=b.block_source,
                price=Decimal(str(b.price)) if b.price is not None else None,
                client_order_id=b.client_order_id,
                created_at=b.created_at.isoformat(),
            )
            for b in blocked_records
        ]

        return ShadowQualityReport(
            exchange=exchange,
            symbol=symbol,
            total_shadow_trades=len(all_trades),
            open_trades=len(open_trades),
            closed_trades=len(closed),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate_pct=win_rate_pct,
            expectancy=expectancy,
            max_drawdown_pct=max_drawdown_pct,
            total_net_pnl=total_net_pnl,
            total_fees_paid=total_fees,
            blocked_signal_count=blocked_count,
            oos_win_rate_pct=oos_win_rate_pct,
            oos_max_drawdown_pct=oos_max_drawdown_pct,
            oos_total_return_pct=oos_total_return_pct,
            recent_blocked_signals=recent_blocked,
            recent_trades=recent_trades,
        )
