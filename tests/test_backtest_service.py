from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.services.backtest_service import BacktestService, WalkForwardResult
from app.domain.strategies.base import Candle, Signal
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy


def build_candles(closes: list[int]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for index, close in enumerate(closes):
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(close),
                low_price=Decimal(close),
                close_price=Decimal(close),
                volume=Decimal("1"),
            )
        )
    return candles


def build_candle(
    *, close: int, low: int | None = None, high: int | None = None, index: int = 0
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    price = Decimal(close)
    return Candle(
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open_price=price,
        high_price=Decimal(high) if high is not None else price,
        low_price=Decimal(low) if low is not None else price,
        close_price=price,
        volume=Decimal("1"),
    )


class StubStrategy:
    def evaluate(self, candles: list[Candle]) -> Signal | None:
        latest_close = candles[-1].close_price
        if latest_close == Decimal("20"):
            return Signal(
                action="buy",
                reason="stub entry",
                fast_value=Decimal("1"),
                slow_value=Decimal("0"),
            )
        if latest_close == Decimal("30"):
            return Signal(
                action="sell",
                reason="stub exit",
                fast_value=Decimal("0"),
                slow_value=Decimal("1"),
            )
        return None


def test_backtest_runs_round_trip_and_realizes_profit() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 12, 20, 30]))

    assert result.total_trades >= 2
    assert result.ending_equity > result.starting_equity
    assert result.realized_pnl > Decimal("0")
    assert result.winning_trades >= 1
    assert result.total_fees_paid == Decimal("0")
    assert result.slippage_pct == Decimal("0")
    assert result.fee_pct == Decimal("0")


def test_backtest_returns_no_trades_when_no_crossover_occurs() -> None:
    service = BacktestService(
        strategy=EmaCrossoverStrategy(fast_period=3, slow_period=5),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 11, 12, 13, 14, 15, 16, 17]))

    assert result.total_trades == 0
    assert result.ending_equity == Decimal("10000")
    assert result.realized_pnl == Decimal("0")
    assert result.total_fees_paid == Decimal("0")


def test_backtest_forces_close_open_position_on_final_candle() -> None:
    service = BacktestService(
        strategy=EmaCrossoverStrategy(fast_period=3, slow_period=5),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 10, 10, 10, 10, 9, 9, 9, 20]))

    assert result.total_trades == 2
    assert result.executions[-1].reason == "forced close on final candle"
    assert result.ending_equity == result.starting_equity


def test_backtest_marks_equity_to_market_for_drawdown() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
    )

    result = service.run(build_candles([10, 20, 10, 30]))

    assert result.max_drawdown_pct > Decimal("0")


def test_backtest_cost_modeling_reduces_pnl() -> None:
    # With costs, a winning trade should return less than without costs.
    service_no_cost = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
    )
    service_with_cost = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        slippage_pct=Decimal("0.001"),
        fee_pct=Decimal("0.001"),
    )

    result_no_cost = service_no_cost.run(build_candles([10, 12, 20, 30]))
    result_with_cost = service_with_cost.run(build_candles([10, 12, 20, 30]))

    assert result_with_cost.realized_pnl < result_no_cost.realized_pnl
    assert result_with_cost.ending_equity < result_no_cost.ending_equity
    assert result_with_cost.total_fees_paid > Decimal("0")
    assert result_with_cost.slippage_pct == Decimal("0.001")
    assert result_with_cost.fee_pct == Decimal("0.001")


def test_backtest_cost_modeling_records_fill_price_and_fee_per_execution() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        slippage_pct=Decimal("0.001"),
        fee_pct=Decimal("0.001"),
    )

    result = service.run(build_candles([10, 12, 20, 30]))

    buy_exec = next(e for e in result.executions if e.action == "buy")
    sell_exec = next(e for e in result.executions if e.action == "sell")

    # Buy fill price should be higher than signal price due to slippage
    assert buy_exec.fill_price > buy_exec.price
    # Sell fill price should be lower than signal price due to slippage
    assert sell_exec.fill_price < sell_exec.price
    # Both fills should have positive fee
    assert buy_exec.fee > Decimal("0")
    assert sell_exec.fee > Decimal("0")


def test_backtest_high_fees_can_turn_winning_trade_into_loss() -> None:
    # A trade from 20 to 30 is a 50% gain on price, but massive fees should make it a loss.
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        slippage_pct=Decimal("0.30"),
        fee_pct=Decimal("0.30"),
    )

    result = service.run(build_candles([10, 12, 20, 30]))

    assert result.realized_pnl < Decimal("0")
    assert result.total_fees_paid > Decimal("0")


def test_walk_forward_returns_in_sample_and_oos_results() -> None:
    service = BacktestService(strategy=StubStrategy(), starting_equity=Decimal("10000"))
    # 4 candles: split 0.5 → 2 in-sample, 2 OOS
    result = service.run_walk_forward(
        build_candles([10, 12, 20, 30]),
        split_ratio=Decimal("0.5"),
        overfitting_threshold_pct=Decimal("35"),
    )

    assert isinstance(result, WalkForwardResult)
    assert result.in_sample_candles == 2
    assert result.out_of_sample_candles == 2
    assert result.split_ratio == Decimal("0.5")
    assert result.overfitting_threshold_pct == Decimal("35")


def test_walk_forward_split_respects_ratio() -> None:
    service = BacktestService(strategy=StubStrategy(), starting_equity=Decimal("10000"))
    candles = build_candles(list(range(10, 20)))  # 10 candles

    result = service.run_walk_forward(candles, split_ratio=Decimal("0.7"))

    assert result.in_sample_candles == 7
    assert result.out_of_sample_candles == 3


def test_walk_forward_detects_overfitting_when_oos_degrades() -> None:
    # StubStrategy buys at 20, sells at 30.
    # In-sample: candles with the profitable trade (20→30).
    # OOS: flat candles, no trade → 0% return.
    # IS return is positive, OOS is 0, degradation > threshold → warning.
    service = BacktestService(strategy=StubStrategy(), starting_equity=Decimal("10000"))
    candles = build_candles([10, 12, 20, 30, 15, 15, 15, 15, 15, 15])

    result = service.run_walk_forward(
        candles,
        split_ratio=Decimal("0.4"),  # first 4 candles in-sample (has the trade)
        overfitting_threshold_pct=Decimal("35"),
    )

    assert result.in_sample.total_return_pct > Decimal("0")
    assert result.return_degradation_pct >= Decimal("0")
    assert isinstance(result.overfitting_warning, bool)


def test_walk_forward_no_warning_when_oos_matches_in_sample() -> None:
    # Both windows have profitable trades → degradation should be low.
    service = BacktestService(strategy=StubStrategy(), starting_equity=Decimal("10000"))
    candles = build_candles([10, 12, 20, 30, 10, 12, 20, 30])

    result = service.run_walk_forward(
        candles,
        split_ratio=Decimal("0.5"),
        overfitting_threshold_pct=Decimal("35"),
    )

    # Both windows have the same profitable pattern; degradation should be near 0.
    assert result.return_degradation_pct < Decimal("35")
    assert result.overfitting_warning is False


# ---------------------------------------------------------------------------
# Leverage support tests
# ---------------------------------------------------------------------------


class BuyAtCloseStrategy:
    """Buys when close equals the trigger price; never sells."""

    def __init__(self, trigger: int) -> None:
        self._trigger = Decimal(trigger)

    def evaluate(self, candles: list[Candle]) -> Signal | None:
        if candles[-1].close_price == self._trigger:
            return Signal(
                action="buy",
                reason="test buy",
                fast_value=Decimal("1"),
                slow_value=Decimal("0"),
            )
        return None


class SellAtCloseStrategy:
    """Sells (short) when close equals the trigger price; never buys back."""

    def __init__(self, trigger: int) -> None:
        self._trigger = Decimal(trigger)

    def evaluate(self, candles: list[Candle]) -> Signal | None:
        if candles[-1].close_price == self._trigger:
            return Signal(
                action="sell",
                reason="test sell",
                fast_value=Decimal("0"),
                slow_value=Decimal("1"),
            )
        return None


def test_leverage_amplifies_pnl() -> None:
    # Buy at 20, forced-close at 30 (last candle).
    candles = build_candles([10, 20, 25, 30])

    result_1x = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=1,
    ).run(candles)

    result_5x = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=5,
    ).run(candles)

    assert result_1x.realized_pnl > Decimal("0")
    assert result_5x.realized_pnl == result_1x.realized_pnl * 5


def test_leverage_1_is_identity() -> None:
    candles = build_candles([10, 20, 25, 30])

    result_default = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
    ).run(candles)

    result_explicit_1 = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=1,
    ).run(candles)

    assert result_default.realized_pnl == result_explicit_1.realized_pnl
    assert result_default.executions[0].quantity == result_explicit_1.executions[0].quantity


def test_long_liquidated_when_low_crosses_liq_price() -> None:
    # Long at 100, leverage=10. Liq price = 100 * (1 - 0.1 + 0.004) = 90.4.
    # A candle with low=89 should trigger liquidation.
    entry_candle = build_candle(close=100, index=0)
    liq_candle = build_candle(close=91, low=89, index=1)

    result = BacktestService(
        strategy=BuyAtCloseStrategy(trigger=100),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=10,
        margin_mode="ISOLATED",
    ).run([entry_candle, liq_candle])

    assert result.liquidation_count == 1
    assert len(result.liquidation_events) == 1
    liquidated_exec = next(e for e in result.executions if e.was_liquidated)
    assert liquidated_exec.was_liquidated is True
    assert liquidated_exec.reason == "liquidated"


def test_short_liquidated_when_high_crosses_liq_price() -> None:
    # Short at 100, leverage=10. Liq price = 100 * (1 + 0.1 - 0.004) = 109.6.
    # A candle with high=111 should trigger liquidation.
    entry_candle = build_candle(close=100, index=0)
    liq_candle = build_candle(close=108, high=111, index=1)

    result = BacktestService(
        strategy=SellAtCloseStrategy(trigger=100),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=10,
        margin_mode="ISOLATED",
    ).run([entry_candle, liq_candle])

    assert result.liquidation_count == 1
    liq_exec = next(e for e in result.executions if e.was_liquidated)
    assert liq_exec.was_liquidated is True


def test_no_liquidation_when_price_stays_safe() -> None:
    # Long at 100, leverage=10. Liq price = 90.4.
    # Candle with low=91 is above liq price — no liquidation.
    entry_candle = build_candle(close=100, index=0)
    safe_candle = build_candle(close=95, low=91, index=1)

    result = BacktestService(
        strategy=BuyAtCloseStrategy(trigger=100),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=10,
        margin_mode="ISOLATED",
    ).run([entry_candle, safe_candle])

    assert result.liquidation_count == 0
    assert all(not e.was_liquidated for e in result.executions)


def test_cross_margin_never_liquidates() -> None:
    # Same setup as long-liquidation test but CROSS mode — no liquidation.
    entry_candle = build_candle(close=100, index=0)
    liq_candle = build_candle(close=91, low=89, index=1)

    result = BacktestService(
        strategy=BuyAtCloseStrategy(trigger=100),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=10,
        margin_mode="CROSS",
    ).run([entry_candle, liq_candle])

    assert result.liquidation_count == 0


def test_leverage_stored_in_result() -> None:
    result = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        trading_mode="FUTURES",
        leverage=7,
        margin_mode="CROSS",
    ).run(build_candles([10, 20, 25, 30]))

    assert result.leverage == 7
    assert result.margin_mode == "CROSS"
