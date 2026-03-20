from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.backtest_run import BacktestRunRecord
from app.infrastructure.database.models.order import OrderRecord
from app.infrastructure.database.repositories.shadow_trade_repository import ShadowTradeRepository
from app.infrastructure.database.repositories.trade_repository import TradeRepository

_DEFAULT_REVIEW_PERIOD_DAYS = 30

# Recommendation thresholds
_HALT_CONSECUTIVE_LOSSES = 5
_HALT_MAX_DRAWDOWN_PCT = Decimal("30")
_PAUSE_WIN_RATE_DRIFT = Decimal("-20")
_PAUSE_SLIPPAGE_OVERSHOOT = Decimal("2.0")
_REDUCE_WIN_RATE_DRIFT = Decimal("-10")
_REDUCE_SLIPPAGE_OVERSHOOT = Decimal("1.0")


@dataclass(frozen=True, slots=True)
class LiveModeMetrics:
    trade_count: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal
    total_fees_paid: Decimal
    avg_slippage_pct: Decimal | None
    slippage_sample_count: int


@dataclass(frozen=True, slots=True)
class ShadowModeMetrics:
    trade_count: int
    win_rate_pct: Decimal | None
    expectancy: Decimal | None
    max_drawdown_pct: Decimal | None
    total_net_pnl: Decimal


@dataclass(frozen=True, slots=True)
class OOSBaseline:
    backtest_run_id: int
    run_date: datetime
    oos_return_pct: Decimal
    oos_drawdown_pct: Decimal
    oos_total_trades: int
    in_sample_return_pct: Decimal
    overfitting_warning: bool


@dataclass(frozen=True, slots=True)
class StrategyHealthIndicators:
    slippage_vs_model_pct: Decimal | None
    shadow_vs_oos_expectancy_drift: Decimal | None
    live_vs_shadow_win_rate_drift: Decimal | None
    consecutive_losses: int
    signal_frequency_per_week: Decimal | None


@dataclass(frozen=True, slots=True)
class LivePerformanceReview:
    live_metrics: LiveModeMetrics | None
    shadow_metrics: ShadowModeMetrics
    oos_baseline: OOSBaseline | None
    health_indicators: StrategyHealthIndicators
    recommendation: str
    recommendation_reasons: list[str]
    review_period_days: int
    generated_at: datetime


class LivePerformanceReviewService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._trade_repo = TradeRepository(session)
        self._shadow_trades = ShadowTradeRepository(session)

    def get_performance_review(
        self,
        *,
        exchange: str,
        symbol: str,
        review_period_days: int = _DEFAULT_REVIEW_PERIOD_DAYS,
    ) -> LivePerformanceReview:
        since = datetime.now(UTC) - timedelta(days=review_period_days)

        live_metrics = self._compute_live_metrics(exchange=exchange, symbol=symbol, since=since)
        shadow_metrics = self._compute_shadow_metrics(exchange=exchange, symbol=symbol)
        oos_baseline = self._fetch_oos_baseline(exchange=exchange, symbol=symbol)

        consecutive_losses = self._trade_repo.get_consecutive_losses(
            exchange=exchange, symbol=symbol, mode="live"
        )

        signal_frequency = self._compute_signal_frequency(
            live_metrics=live_metrics, review_period_days=review_period_days
        )

        slippage_vs_model = self._compute_slippage_vs_model(
            live_metrics=live_metrics, oos_baseline=oos_baseline
        )
        shadow_vs_oos_drift = self._compute_shadow_vs_oos_expectancy_drift(
            shadow_metrics=shadow_metrics, oos_baseline=oos_baseline
        )
        live_vs_shadow_win_rate_drift = self._compute_live_vs_shadow_win_rate_drift(
            live_metrics=live_metrics, shadow_metrics=shadow_metrics
        )

        health_indicators = StrategyHealthIndicators(
            slippage_vs_model_pct=slippage_vs_model,
            shadow_vs_oos_expectancy_drift=shadow_vs_oos_drift,
            live_vs_shadow_win_rate_drift=live_vs_shadow_win_rate_drift,
            consecutive_losses=consecutive_losses,
            signal_frequency_per_week=signal_frequency,
        )

        recommendation, reasons = self._derive_recommendation(
            live_metrics=live_metrics,
            health_indicators=health_indicators,
        )

        return LivePerformanceReview(
            live_metrics=live_metrics,
            shadow_metrics=shadow_metrics,
            oos_baseline=oos_baseline,
            health_indicators=health_indicators,
            recommendation=recommendation,
            recommendation_reasons=reasons,
            review_period_days=review_period_days,
            generated_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_live_metrics(
        self, *, exchange: str, symbol: str, since: datetime
    ) -> LiveModeMetrics | None:
        """Compute live-trade metrics for the review period.

        Returns None when there are no live trades at all.
        """
        from app.infrastructure.database.models.trade import TradeRecord

        # Fetch closed live trades within the review period
        stmt = (
            select(TradeRecord)
            .join(OrderRecord, OrderRecord.id == TradeRecord.order_id)
            .where(
                TradeRecord.exchange == exchange,
                TradeRecord.symbol == symbol,
                OrderRecord.mode == "live",
                TradeRecord.realized_pnl.isnot(None),
                TradeRecord.created_at >= since,
            )
            .order_by(TradeRecord.created_at.asc(), TradeRecord.id.asc())
        )
        live_trades = list(self._session.execute(stmt).scalars())

        if not live_trades:
            return None

        winners = [t for t in live_trades if (t.realized_pnl or Decimal("0")) > Decimal("0")]
        losers = [t for t in live_trades if (t.realized_pnl or Decimal("0")) <= Decimal("0")]

        total = Decimal(str(len(live_trades)))
        win_rate = Decimal(str(len(winners))) / total * Decimal("100")

        avg_win = (
            sum(t.realized_pnl or Decimal("0") for t in winners) / Decimal(str(len(winners)))
            if winners
            else Decimal("0")
        )
        avg_loss = (
            sum(t.realized_pnl or Decimal("0") for t in losers) / Decimal(str(len(losers)))
            if losers
            else Decimal("0")
        )
        wr_fraction = win_rate / Decimal("100")
        expectancy = avg_win * wr_fraction + avg_loss * (Decimal("1") - wr_fraction)

        max_drawdown_pct = self._compute_drawdown_pct_from_pnls(
            [t.realized_pnl or Decimal("0") for t in live_trades]
        )

        total_net_pnl = sum(t.realized_pnl or Decimal("0") for t in live_trades)
        total_fees = sum(t.fee_amount or Decimal("0") for t in live_trades)

        # Slippage: query live orders with both signal_price and average_fill_price
        avg_slippage, slippage_count = self._compute_avg_slippage(
            exchange=exchange, symbol=symbol, since=since
        )

        return LiveModeMetrics(
            trade_count=len(live_trades),
            win_rate_pct=win_rate,
            expectancy=expectancy,
            max_drawdown_pct=max_drawdown_pct,
            total_net_pnl=total_net_pnl,
            total_fees_paid=total_fees,
            avg_slippage_pct=avg_slippage,
            slippage_sample_count=slippage_count,
        )

    def _compute_avg_slippage(
        self, *, exchange: str, symbol: str, since: datetime
    ) -> tuple[Decimal | None, int]:
        stmt = select(OrderRecord.signal_price, OrderRecord.average_fill_price).where(
            OrderRecord.exchange == exchange,
            OrderRecord.symbol == symbol,
            OrderRecord.mode == "live",
            OrderRecord.signal_price.isnot(None),
            OrderRecord.average_fill_price.isnot(None),
            OrderRecord.created_at >= since,
        )
        rows = self._session.execute(stmt).all()
        if not rows:
            return None, 0

        slippages: list[Decimal] = []
        for signal_price, average_fill_price in rows:
            if signal_price and average_fill_price and signal_price != Decimal("0"):
                slippage = (average_fill_price - signal_price) / signal_price * Decimal("100")
                slippages.append(slippage)

        if not slippages:
            return None, 0

        avg = sum(slippages) / Decimal(str(len(slippages)))
        return avg, len(slippages)

    def _compute_shadow_metrics(self, *, exchange: str, symbol: str) -> ShadowModeMetrics:
        closed = self._shadow_trades.list_closed(exchange=exchange, symbol=symbol, limit=1000)

        if not closed:
            return ShadowModeMetrics(
                trade_count=0,
                win_rate_pct=None,
                expectancy=None,
                max_drawdown_pct=None,
                total_net_pnl=Decimal("0"),
            )

        winners = [t for t in closed if (t.net_pnl or Decimal("0")) > Decimal("0")]
        losers = [t for t in closed if (t.net_pnl or Decimal("0")) <= Decimal("0")]
        total = Decimal(str(len(closed)))

        win_rate = Decimal(str(len(winners))) / total * Decimal("100")
        wr_fraction = win_rate / Decimal("100")
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
        expectancy = avg_win * wr_fraction + avg_loss * (Decimal("1") - wr_fraction)

        max_drawdown_pct = self._compute_drawdown_pct_from_pnls(
            [t.net_pnl or Decimal("0") for t in closed]
        )
        total_net_pnl = sum(t.net_pnl or Decimal("0") for t in closed)

        return ShadowModeMetrics(
            trade_count=len(closed),
            win_rate_pct=win_rate,
            expectancy=expectancy,
            max_drawdown_pct=max_drawdown_pct,
            total_net_pnl=total_net_pnl,
        )

    def _fetch_oos_baseline(self, *, exchange: str, symbol: str) -> OOSBaseline | None:
        stmt = (
            select(BacktestRunRecord)
            .where(BacktestRunRecord.exchange == exchange)
            .where(BacktestRunRecord.symbol == symbol)
            .where(BacktestRunRecord.walk_forward_oos_return_pct.isnot(None))
            .order_by(BacktestRunRecord.id.desc())
            .limit(1)
        )
        run = self._session.execute(stmt).scalar_one_or_none()
        if run is None:
            return None

        return OOSBaseline(
            backtest_run_id=run.id,
            run_date=run.created_at,
            oos_return_pct=run.walk_forward_oos_return_pct or Decimal("0"),
            oos_drawdown_pct=run.walk_forward_oos_drawdown_pct or Decimal("0"),
            oos_total_trades=run.walk_forward_oos_total_trades or 0,
            in_sample_return_pct=run.walk_forward_in_sample_return_pct or Decimal("0"),
            overfitting_warning=run.walk_forward_overfitting_warning or False,
        )

    @staticmethod
    def _compute_signal_frequency(
        *, live_metrics: LiveModeMetrics | None, review_period_days: int
    ) -> Decimal | None:
        if live_metrics is None or live_metrics.trade_count == 0:
            return None
        weeks = Decimal(str(review_period_days)) / Decimal("7")
        if weeks == Decimal("0"):
            return None
        return Decimal(str(live_metrics.trade_count)) / weeks

    @staticmethod
    def _compute_slippage_vs_model(
        *, live_metrics: LiveModeMetrics | None, oos_baseline: OOSBaseline | None
    ) -> Decimal | None:
        if live_metrics is None or live_metrics.avg_slippage_pct is None:
            return None
        if oos_baseline is None:
            return live_metrics.avg_slippage_pct
        return live_metrics.avg_slippage_pct

    @staticmethod
    def _compute_shadow_vs_oos_expectancy_drift(
        *, shadow_metrics: ShadowModeMetrics, oos_baseline: OOSBaseline | None
    ) -> Decimal | None:
        if shadow_metrics.expectancy is None or oos_baseline is None:
            return None
        oos_return = oos_baseline.oos_return_pct
        if oos_return == Decimal("0"):
            return None
        drift = (shadow_metrics.expectancy - oos_return) / abs(oos_return) * Decimal("100")
        return drift

    @staticmethod
    def _compute_live_vs_shadow_win_rate_drift(
        *, live_metrics: LiveModeMetrics | None, shadow_metrics: ShadowModeMetrics
    ) -> Decimal | None:
        if live_metrics is None or live_metrics.win_rate_pct is None:
            return None
        if shadow_metrics.win_rate_pct is None:
            return None
        return live_metrics.win_rate_pct - shadow_metrics.win_rate_pct

    @staticmethod
    def _compute_drawdown_pct_from_pnls(pnls: list[Decimal]) -> Decimal:
        cumulative = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        for pnl in pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return (max_dd / peak * Decimal("100")) if peak > Decimal("0") else Decimal("0")

    @staticmethod
    def _derive_recommendation(
        *,
        live_metrics: LiveModeMetrics | None,
        health_indicators: StrategyHealthIndicators,
    ) -> tuple[str, list[str]]:
        if live_metrics is None:
            return "keep_running", ["No live trades yet — system is in paper or shadow mode."]

        reasons: list[str] = []

        # Halt conditions
        if health_indicators.consecutive_losses >= _HALT_CONSECUTIVE_LOSSES:
            reasons.append(
                f"Consecutive losses {health_indicators.consecutive_losses} >= "
                f"{_HALT_CONSECUTIVE_LOSSES} threshold."
            )
        if (
            live_metrics.max_drawdown_pct is not None
            and live_metrics.max_drawdown_pct > _HALT_MAX_DRAWDOWN_PCT
        ):
            reasons.append(
                f"Live max drawdown {live_metrics.max_drawdown_pct:.2f}% exceeds "
                f"{_HALT_MAX_DRAWDOWN_PCT}% halt threshold."
            )
        if reasons:
            return "halt", reasons

        # Pause-and-rework conditions
        if (
            health_indicators.live_vs_shadow_win_rate_drift is not None
            and health_indicators.live_vs_shadow_win_rate_drift < _PAUSE_WIN_RATE_DRIFT
        ):
            drift = health_indicators.live_vs_shadow_win_rate_drift
            reasons.append(
                f"Live vs shadow win rate drift {drift:.2f}%"
                f" is below {_PAUSE_WIN_RATE_DRIFT}% threshold."
            )
        if (
            health_indicators.slippage_vs_model_pct is not None
            and health_indicators.slippage_vs_model_pct > _PAUSE_SLIPPAGE_OVERSHOOT
        ):
            reasons.append(
                f"Average slippage {health_indicators.slippage_vs_model_pct:.4f}% exceeds "
                f"{_PAUSE_SLIPPAGE_OVERSHOOT}% pause threshold."
            )
        if reasons:
            return "pause_and_rework", reasons

        # Reduce-risk conditions
        if (
            health_indicators.live_vs_shadow_win_rate_drift is not None
            and health_indicators.live_vs_shadow_win_rate_drift < _REDUCE_WIN_RATE_DRIFT
        ):
            drift = health_indicators.live_vs_shadow_win_rate_drift
            reasons.append(
                f"Live vs shadow win rate drift {drift:.2f}%"
                f" is below {_REDUCE_WIN_RATE_DRIFT}% threshold."
            )
        if (
            health_indicators.slippage_vs_model_pct is not None
            and health_indicators.slippage_vs_model_pct > _REDUCE_SLIPPAGE_OVERSHOOT
        ):
            reasons.append(
                f"Average slippage {health_indicators.slippage_vs_model_pct:.4f}% exceeds "
                f"{_REDUCE_SLIPPAGE_OVERSHOOT}% reduce-risk threshold."
            )
        if reasons:
            return "reduce_risk", reasons

        return "keep_running", ["All health indicators within acceptable ranges."]
