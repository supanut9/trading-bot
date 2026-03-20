from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.backtest_run import BacktestRunRecord
from app.infrastructure.database.repositories.shadow_trade_repository import ShadowTradeRepository

# Configurable thresholds
_MIN_SHADOW_TRADES = 30
_MAX_OOS_DRAWDOWN_PCT = Decimal("25")
_MAX_SHADOW_DRAWDOWN_PCT = Decimal("25")
_MAX_RETURN_DEGRADATION_PCT = Decimal("35")

_NO_WF = "No walk-forward backtest available"


@dataclass(frozen=True, slots=True)
class QualificationGate:
    name: str
    passed: bool
    reason: str
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class QualificationReport:
    exchange: str
    symbol: str
    all_passed: bool
    gates: list[QualificationGate]


class QualificationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._shadow_trades = ShadowTradeRepository(session)

    def evaluate(self, *, exchange: str, symbol: str) -> QualificationReport:
        gates: list[QualificationGate] = []

        wf_run = self._latest_walk_forward_run(exchange=exchange, symbol=symbol)

        # Gate 1: walk-forward backtest run exists
        gates.append(
            QualificationGate(
                name="walk_forward_run_exists",
                passed=wf_run is not None,
                reason=(
                    f"Walk-forward backtest found (run id {wf_run.id})"
                    if wf_run is not None
                    else "No walk-forward backtest run found — run one first"
                ),
                evidence=(f"backtest_run_id={wf_run.id}" if wf_run is not None else None),
            )
        )

        # Gate 2: OOS positive return (cost-adjusted — fees already embedded)
        oos_return = wf_run.walk_forward_oos_return_pct if wf_run else None
        if oos_return is not None:
            passed = oos_return > Decimal("0")
            gates.append(
                QualificationGate(
                    name="oos_positive_return",
                    passed=passed,
                    reason=(
                        f"OOS return {oos_return:+.4f}% is positive after costs"
                        if passed
                        else f"OOS return {oos_return:+.4f}% — no edge on out-of-sample data"
                    ),
                    evidence=f"oos_return_pct={oos_return}",
                )
            )
        else:
            gates.append(QualificationGate(name="oos_positive_return", passed=False, reason=_NO_WF))

        # Gate 3: OOS max drawdown < 25%
        oos_drawdown = wf_run.walk_forward_oos_drawdown_pct if wf_run else None
        if oos_drawdown is not None:
            passed = oos_drawdown < _MAX_OOS_DRAWDOWN_PCT
            gates.append(
                QualificationGate(
                    name="oos_drawdown_acceptable",
                    passed=passed,
                    reason=(
                        f"OOS drawdown {oos_drawdown:.2f}% is below"
                        f" {_MAX_OOS_DRAWDOWN_PCT}% threshold"
                        if passed
                        else f"OOS drawdown {oos_drawdown:.2f}% exceeds"
                        f" {_MAX_OOS_DRAWDOWN_PCT}% — too risky for live capital"
                    ),
                    evidence=f"oos_max_drawdown_pct={oos_drawdown}",
                )
            )
        else:
            gates.append(
                QualificationGate(name="oos_drawdown_acceptable", passed=False, reason=_NO_WF)
            )

        # Gate 4: no overfitting (return degradation <= 35% and no overfitting warning)
        if wf_run is not None:
            degradation = wf_run.walk_forward_return_degradation_pct or Decimal("0")
            overfitting_flag = wf_run.walk_forward_overfitting_warning or False
            passed = not overfitting_flag and degradation <= _MAX_RETURN_DEGRADATION_PCT
            suffix = " and overfitting warning is set" if overfitting_flag else ""
            gates.append(
                QualificationGate(
                    name="no_overfitting",
                    passed=passed,
                    reason=(
                        f"Return degradation {degradation:.2f}% is within"
                        f" {_MAX_RETURN_DEGRADATION_PCT}% tolerance"
                        if passed
                        else (
                            f"Degradation {degradation:.2f}% exceeds"
                            f" {_MAX_RETURN_DEGRADATION_PCT}%{suffix}"
                            " — parameters may not generalise to live conditions"
                        )
                    ),
                    evidence=(
                        f"degradation_pct={degradation}, overfitting_warning={overfitting_flag}"
                    ),
                )
            )
        else:
            gates.append(QualificationGate(name="no_overfitting", passed=False, reason=_NO_WF))

        # Fetch closed shadow trades once for gates 5-7
        closed_trades = self._shadow_trades.list_closed(
            exchange=exchange, symbol=symbol, limit=1000
        )
        closed_count = len(closed_trades)

        # Gate 5: at least 30 completed shadow trades
        gates.append(
            QualificationGate(
                name="shadow_trade_count",
                passed=closed_count >= _MIN_SHADOW_TRADES,
                reason=(
                    f"{closed_count} shadow trades meets the {_MIN_SHADOW_TRADES} minimum"
                    if closed_count >= _MIN_SHADOW_TRADES
                    else (
                        f"Only {closed_count} shadow trades — need"
                        f" {_MIN_SHADOW_TRADES} before live promotion"
                    )
                ),
                evidence=f"closed_shadow_trades={closed_count}",
            )
        )

        # Gate 6: shadow positive expectancy
        if closed_trades:
            expectancy = self._compute_expectancy(closed_trades)
            passed = expectancy > Decimal("0")
            gates.append(
                QualificationGate(
                    name="shadow_positive_expectancy",
                    passed=passed,
                    reason=(
                        f"Shadow expectancy {expectancy:+.4f} is positive"
                        if passed
                        else (
                            f"Shadow expectancy {expectancy:+.4f} is not positive"
                            " — strategy is losing money in live conditions"
                        )
                    ),
                    evidence=f"shadow_expectancy={expectancy:.6f}",
                )
            )
        else:
            gates.append(
                QualificationGate(
                    name="shadow_positive_expectancy",
                    passed=False,
                    reason="No closed shadow trades to compute expectancy",
                )
            )

        # Gate 7: shadow max drawdown < 25%
        if closed_trades:
            shadow_drawdown = self._compute_drawdown_pct(closed_trades)
            passed = shadow_drawdown < _MAX_SHADOW_DRAWDOWN_PCT
            gates.append(
                QualificationGate(
                    name="shadow_drawdown_acceptable",
                    passed=passed,
                    reason=(
                        f"Shadow drawdown {shadow_drawdown:.2f}% is below"
                        f" {_MAX_SHADOW_DRAWDOWN_PCT}% threshold"
                        if passed
                        else (
                            f"Shadow drawdown {shadow_drawdown:.2f}% exceeds"
                            f" {_MAX_SHADOW_DRAWDOWN_PCT}%"
                            " — live conditions worse than backtest expected"
                        )
                    ),
                    evidence=f"shadow_max_drawdown_pct={shadow_drawdown:.4f}",
                )
            )
        else:
            gates.append(
                QualificationGate(
                    name="shadow_drawdown_acceptable",
                    passed=False,
                    reason="No closed shadow trades to compute drawdown",
                )
            )

        return QualificationReport(
            exchange=exchange,
            symbol=symbol,
            all_passed=all(g.passed for g in gates),
            gates=gates,
        )

    def _latest_walk_forward_run(self, *, exchange: str, symbol: str) -> BacktestRunRecord | None:
        stmt = (
            select(BacktestRunRecord)
            .where(BacktestRunRecord.exchange == exchange)
            .where(BacktestRunRecord.symbol == symbol)
            .where(BacktestRunRecord.walk_forward_oos_return_pct.isnot(None))
            .order_by(BacktestRunRecord.id.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _compute_expectancy(closed_trades: list) -> Decimal:
        winners = [t for t in closed_trades if (t.net_pnl or Decimal("0")) > Decimal("0")]
        losers = [t for t in closed_trades if (t.net_pnl or Decimal("0")) <= Decimal("0")]
        total = Decimal(str(len(closed_trades)))
        win_rate = Decimal(str(len(winners))) / total
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
        return avg_win * win_rate + avg_loss * (Decimal("1") - win_rate)

    @staticmethod
    def _compute_drawdown_pct(closed_trades: list) -> Decimal:
        cumulative = Decimal("0")
        peak = Decimal("0")
        max_dd = Decimal("0")
        for t in closed_trades:
            cumulative += t.net_pnl or Decimal("0")
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        return (max_dd / peak * Decimal("100")) if peak > Decimal("0") else Decimal("0")
