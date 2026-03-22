from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.backtest_run import BacktestRunRecord


class BacktestRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_recent(self, *, limit: int = 20) -> list[BacktestRunRecord]:
        statement: Select[tuple[BacktestRunRecord]] = (
            select(BacktestRunRecord)
            .order_by(
                BacktestRunRecord.created_at.desc(),
                BacktestRunRecord.id.desc(),
            )
            .limit(limit)
        )
        return self._session.execute(statement).scalars().all()

    def create(
        self,
        *,
        source: str,
        status: str,
        detail: str,
        strategy_name: str,
        exchange: str,
        symbol: str,
        timeframe: str,
        fast_period: int | None,
        slow_period: int | None,
        starting_equity_input,
        candle_count: int,
        required_candles: int,
        starting_equity,
        ending_equity,
        realized_pnl,
        total_return_pct,
        max_drawdown_pct,
        total_trades: int | None,
        winning_trades: int | None,
        losing_trades: int | None,
        total_fees_paid,
        slippage_pct,
        fee_pct,
        spread_pct,
        signal_latency_bars: int | None,
        walk_forward_split_ratio,
        walk_forward_in_sample_candles: int | None,
        walk_forward_oos_candles: int | None,
        walk_forward_in_sample_return_pct,
        walk_forward_oos_return_pct,
        walk_forward_oos_drawdown_pct,
        walk_forward_oos_total_trades: int | None,
        walk_forward_return_degradation_pct,
        walk_forward_overfitting_warning: bool | None,
        rules_json: str | None,
    ) -> BacktestRunRecord:
        record = BacktestRunRecord(
            source=source,
            status=status,
            detail=detail,
            strategy_name=strategy_name,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            fast_period=fast_period,
            slow_period=slow_period,
            starting_equity_input=starting_equity_input,
            candle_count=candle_count,
            required_candles=required_candles,
            starting_equity=starting_equity,
            ending_equity=ending_equity,
            realized_pnl=realized_pnl,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_fees_paid=total_fees_paid,
            slippage_pct=slippage_pct,
            fee_pct=fee_pct,
            spread_pct=spread_pct,
            signal_latency_bars=signal_latency_bars,
            walk_forward_split_ratio=walk_forward_split_ratio,
            walk_forward_in_sample_candles=walk_forward_in_sample_candles,
            walk_forward_oos_candles=walk_forward_oos_candles,
            walk_forward_in_sample_return_pct=walk_forward_in_sample_return_pct,
            walk_forward_oos_return_pct=walk_forward_oos_return_pct,
            walk_forward_oos_drawdown_pct=walk_forward_oos_drawdown_pct,
            walk_forward_oos_total_trades=walk_forward_oos_total_trades,
            walk_forward_return_degradation_pct=walk_forward_return_degradation_pct,
            walk_forward_overfitting_warning=walk_forward_overfitting_warning,
            rules_json=rules_json,
        )
        self._session.add(record)
        self._session.flush()
        return record
