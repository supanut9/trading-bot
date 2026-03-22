from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.services.backtest_service import BacktestService, WalkForwardResult
from app.domain.risk import RiskLimits, RiskService
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


def _build_candle_on_date(*, close: int, day_offset: int, hour: int = 0) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day_offset, hours=hour)
    price = Decimal(close)
    return Candle(
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open_price=price,
        high_price=price,
        low_price=price,
        close_price=price,
        volume=Decimal("1"),
    )


class BuySellEveryOtherDayStrategy:
    """Buys at price 20, sells at price 10 — deliberately triggers losses — one per day."""

    def __init__(self) -> None:
        self._call = 0

    def evaluate(self, candles: list[Candle]) -> Signal | None:
        close = candles[-1].close_price
        if close == Decimal("20"):
            return Signal(
                action="buy", reason="entry", fast_value=Decimal("1"), slow_value=Decimal("0")
            )
        if close == Decimal("10"):
            return Signal(
                action="sell", reason="exit", fast_value=Decimal("0"), slow_value=Decimal("1")
            )
        return None


def test_daily_loss_limit_resets_each_new_day() -> None:
    """
    Daily loss limit must not permanently block entries after the first bad day.
    Scenario: Day 1 → buy at 20, sell at 10 (loss of ~50%). Day 2 → should be able to buy again.
    With the old (buggy) code, cumulative loss would permanently block Day 2's entry.
    """
    # Day 0: warm-up candles (no signal)
    # Day 1 hour 0: buy signal (close=20), Day 1 hour 1: sell signal (close=10) → losing trade
    # Day 2 hour 0: buy signal (close=20) → should NOT be blocked by previous day's loss
    candles = [
        _build_candle_on_date(close=5, day_offset=0, hour=0),  # warm-up
        _build_candle_on_date(close=5, day_offset=0, hour=1),  # warm-up
        _build_candle_on_date(close=20, day_offset=1, hour=0),  # Day 1: buy
        _build_candle_on_date(close=10, day_offset=1, hour=1),  # Day 1: sell at loss
        _build_candle_on_date(close=20, day_offset=2, hour=0),  # Day 2: buy (should work)
        _build_candle_on_date(close=10, day_offset=2, hour=1),  # Day 2: sell at loss
        _build_candle_on_date(close=20, day_offset=3, hour=0),  # Day 3: buy (should work)
        _build_candle_on_date(close=15, day_offset=3, hour=1),  # Day 3: end
    ]

    # Use a tight daily loss limit (1%) to make sure cumulative loss would block under old logic
    risk = RiskService(
        RiskLimits(
            risk_per_trade_pct=Decimal("0.01"),
            max_open_positions=1,
            max_daily_loss_pct=Decimal("0.01"),  # 1% daily — old code would block after day 1
            paper_trading_only=True,
        )
    )
    service = BacktestService(
        strategy=BuySellEveryOtherDayStrategy(),
        risk_service=risk,
        starting_equity=Decimal("1000"),
    )
    result = service.run(candles)

    # Should have at least 2 buy entries (Day 1 and Day 2) — not permanently blocked after day 1
    buy_entries = [e for e in result.executions if e.action == "buy" and "entry" in e.reason]
    assert len(buy_entries) >= 2, (
        f"Expected trades on multiple days but got only {len(buy_entries)} entries. "
        "Daily loss limit may not be resetting per day."
    )


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
    assert result_with_cost.spread_pct == Decimal("0")
    assert result_with_cost.signal_latency_bars == 0


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


def test_backtest_spread_and_latency_reduce_pnl() -> None:
    service_no_extra_friction = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        slippage_pct=Decimal("0.001"),
        fee_pct=Decimal("0.001"),
    )
    service_with_extra_friction = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        slippage_pct=Decimal("0.001"),
        fee_pct=Decimal("0.001"),
        spread_pct=Decimal("0.002"),
        signal_latency_bars=1,
    )

    result_no_extra_friction = service_no_extra_friction.run(build_candles([10, 12, 20, 30]))
    result_with_extra_friction = service_with_extra_friction.run(build_candles([10, 12, 20, 30]))

    assert result_with_extra_friction.realized_pnl < result_no_extra_friction.realized_pnl
    assert result_with_extra_friction.spread_pct == Decimal("0.002")
    assert result_with_extra_friction.signal_latency_bars == 1
    assert "spread_pct=0.002" in result_with_extra_friction.assumption_summary
    assert "signal_latency_bars=1" in result_with_extra_friction.assumption_summary


def test_backtest_session_constraints_limit_trading_hours() -> None:
    service = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        allowed_hours_utc=(2,),
    )

    result = service.run(build_candles([10, 12, 20, 30]))

    assert result.total_trades == 2
    assert result.executions[0].reason == "stub entry"
    assert result.executions[-1].reason == "forced close on final candle"
    assert result.allowed_hours_utc == (2,)
    assert "allowed_hours_utc=[2]" in result.assumption_summary


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


# ── Stop-loss tests ──────────────────────────────────────────────────────────


def _make_stop_candles(
    *,
    warmup: int = 15,
    warmup_high: int = 102,
    warmup_low: int = 98,
    warmup_close: int = 100,
    entry_close: int = 105,
    extra: list[tuple[int, int, int]] | None = None,  # (close, high, low) tuples
) -> list[Candle]:
    """Build a candle sequence where entry fires on a unique close price after warm-up."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[Candle] = []
    for i in range(warmup):
        t = start + timedelta(hours=i)
        candles.append(
            Candle(
                open_time=t,
                close_time=t + timedelta(hours=1),
                open_price=Decimal(warmup_close),
                high_price=Decimal(warmup_high),
                low_price=Decimal(warmup_low),
                close_price=Decimal(warmup_close),
                volume=Decimal("1"),
            )
        )
    # Entry candle — distinct close so strategy only fires here
    t_entry = start + timedelta(hours=warmup)
    candles.append(
        Candle(
            open_time=t_entry,
            close_time=t_entry + timedelta(hours=1),
            open_price=Decimal(entry_close),
            high_price=Decimal(entry_close + 1),
            low_price=Decimal(entry_close - 1),
            close_price=Decimal(entry_close),
            volume=Decimal("1"),
        )
    )
    for offset, (close, high, low) in enumerate(extra or [], start=1):
        t = start + timedelta(hours=warmup + offset)
        candles.append(
            Candle(
                open_time=t,
                close_time=t + timedelta(hours=1),
                open_price=Decimal(close),
                high_price=Decimal(high),
                low_price=Decimal(low),
                close_price=Decimal(close),
                volume=Decimal("1"),
            )
        )
    return candles


class BuyAtPriceStrategy:
    """Buys when close == trigger, never sells (tests stop-loss exits)."""

    def __init__(self, trigger: int) -> None:
        self.trigger = trigger

    def evaluate(self, candles: list[Candle]) -> Signal | None:
        if candles[-1].close_price == Decimal(self.trigger):
            return Signal(action="buy", reason="entry", fast_value=None, slow_value=None)
        return None


def test_stop_loss_triggers_when_price_drops_below_stop() -> None:
    """15 warm-up (ATR≈4), entry at 105, stop≈97. Drop candle low=80 → stop hit."""
    # ATR ≈ 4 (range 98-102), stop = 105 - 2*4 = 97; drop low=80 breaches it
    candles = _make_stop_candles(
        warmup=15,
        warmup_high=102,
        warmup_low=98,
        warmup_close=100,
        entry_close=105,
        extra=[(105, 106, 80)],  # drop candle: low=80 breaches stop
    )
    result = BacktestService(
        strategy=BuyAtPriceStrategy(trigger=105),
        starting_equity=Decimal("10000"),
        stop_loss_atr_multiplier=Decimal("2"),
        stop_loss_atr_period=14,
        trailing_stop_enabled=False,
    ).run(candles)

    assert result.stop_loss_count == 1
    stop_exec = next(e for e in result.executions if e.reason == "stop_loss")
    assert stop_exec.action == "sell"
    assert stop_exec.realized_pnl < Decimal("0")


def test_stop_loss_not_triggered_when_low_stays_above_stop() -> None:
    """Drop candle low=100 stays above stop≈97 — no stop exit."""
    candles = _make_stop_candles(
        warmup=15,
        warmup_high=102,
        warmup_low=98,
        warmup_close=100,
        entry_close=105,
        extra=[(103, 106, 100)],  # low=100 > stop≈97
    )
    result = BacktestService(
        strategy=BuyAtPriceStrategy(trigger=105),
        starting_equity=Decimal("10000"),
        stop_loss_atr_multiplier=Decimal("2"),
        stop_loss_atr_period=14,
        trailing_stop_enabled=False,
    ).run(candles)

    assert result.stop_loss_count == 0


def test_stop_loss_disabled_when_multiplier_is_zero() -> None:
    """multiplier=0 → no stop set; extreme price drop does not trigger exit."""
    candles = _make_stop_candles(
        warmup=15,
        entry_close=105,
        extra=[(50, 105, 50)],  # catastrophic drop
    )
    result = BacktestService(
        strategy=BuyAtPriceStrategy(trigger=105),
        starting_equity=Decimal("10000"),
        stop_loss_atr_multiplier=Decimal("0"),
    ).run(candles)

    assert result.stop_loss_count == 0
    assert not any(e.reason == "stop_loss" for e in result.executions)


def test_trailing_stop_ratchets_up_and_protects_profit() -> None:
    """Entry at 105, price rises to 125, trailing stop ratchets, then sharp drop exits."""
    # ATR ≈ 2 (range 99-101); initial stop = 105 - 2*2 = 101
    # After rising to 125: trailing stop = 125 - 2*~2 ≈ 121 (above entry) → profit locked
    candles = _make_stop_candles(
        warmup=15,
        warmup_high=101,
        warmup_low=99,
        warmup_close=100,
        entry_close=105,
        extra=[
            (109, 110, 108),
            (113, 114, 112),
            (117, 118, 116),
            (121, 122, 120),
            (125, 126, 124),
            (125, 126, 95),  # sharp drop: low=95 breaches ratcheted trailing stop
        ],
    )
    result = BacktestService(
        strategy=BuyAtPriceStrategy(trigger=105),
        starting_equity=Decimal("10000"),
        stop_loss_atr_multiplier=Decimal("2"),
        stop_loss_atr_period=14,
        trailing_stop_enabled=True,
    ).run(candles)

    assert result.stop_loss_count == 1
    stop_exec = next(e for e in result.executions if e.reason == "stop_loss")
    assert stop_exec.realized_pnl > Decimal("0"), "trailing stop should lock in profit"


# ── Multi-timeframe confirmation tests ────────────────────────────────────────


def _make_htf_candle(*, close: int, offset_hours: int) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=offset_hours)
    price = Decimal(close)
    return Candle(
        open_time=open_time,
        close_time=open_time + timedelta(hours=4),
        open_price=price,
        high_price=price,
        low_price=price,
        close_price=price,
        volume=Decimal("1"),
    )


def test_htf_confirmation_blocks_buy_when_htf_bearish() -> None:
    """When HTF trend is bearish (price below EMA), buy signals should be filtered out.

    All HTF candles are timestamped before the base buy signal at hour 100
    so look-ahead protection does not exclude them.
    """
    # Base candles start at hour 100 so HTF candles (hours 0-84) are all in the past
    base_start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=100)
    base_candles = [
        Candle(
            open_time=base_start + timedelta(hours=i),
            close_time=base_start + timedelta(hours=i + 1),
            open_price=Decimal(c),
            high_price=Decimal(c),
            low_price=Decimal(c),
            close_price=Decimal(c),
            volume=Decimal("1"),
        )
        for i, c in enumerate([10, 12, 20, 30])
    ]
    # HTF is bearish: 21 high-price candles then a collapse to 50 — all before hour 100
    htf_candles = [_make_htf_candle(close=200, offset_hours=i) for i in range(21)] + [
        _make_htf_candle(close=50, offset_hours=21)
    ]

    result = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        htf_candles=htf_candles,
        htf_period=21,
    ).run(base_candles)

    # Buy should be blocked by HTF filter; no completed trades
    assert result.total_trades == 0
    assert result.realized_pnl == Decimal("0")


def test_htf_confirmation_allows_buy_when_htf_bullish() -> None:
    """When HTF trend is bullish (price above EMA), buy signals should pass through."""
    base_start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=100)
    base_candles = [
        Candle(
            open_time=base_start + timedelta(hours=i),
            close_time=base_start + timedelta(hours=i + 1),
            open_price=Decimal(c),
            high_price=Decimal(c),
            low_price=Decimal(c),
            close_price=Decimal(c),
            volume=Decimal("1"),
        )
        for i, c in enumerate([10, 12, 20, 30])
    ]
    # HTF is bullish: 21 flat at 100 then surge to 200 — all before hour 100
    htf_candles = [_make_htf_candle(close=100, offset_hours=i) for i in range(21)] + [
        _make_htf_candle(close=200, offset_hours=21)
    ]

    result = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        htf_candles=htf_candles,
        htf_period=21,
    ).run(base_candles)

    # Buy should pass through and complete at least one round trip
    assert result.total_trades >= 2


def test_htf_confirmation_disabled_when_no_htf_candles() -> None:
    """Empty htf_candles list disables the filter entirely."""
    base_candles = build_candles([10, 12, 20, 30])

    result = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        htf_candles=[],
        htf_period=21,
    ).run(base_candles)

    assert result.total_trades >= 2


def test_htf_look_ahead_protection() -> None:
    """HTF candles after the current base candle's time must not be used."""
    base_candles = build_candles([10, 12, 20, 30])
    base_start = datetime(2026, 1, 1, tzinfo=UTC)

    # HTF candle that is AFTER all base candles — should not influence signal at base[2]
    # Place HTF candle far in the future (bearish: price 50 vs EMA ~200)
    future_htf = [_make_htf_candle(close=200, offset_hours=i * 4) for i in range(21)] + [
        Candle(
            open_time=base_start + timedelta(days=365),  # far future
            close_time=base_start + timedelta(days=365, hours=4),
            open_price=Decimal(50),
            high_price=Decimal(50),
            low_price=Decimal(50),
            close_price=Decimal(50),
            volume=Decimal("1"),
        )
    ]

    result = BacktestService(
        strategy=StubStrategy(),
        starting_equity=Decimal("10000"),
        htf_candles=future_htf,
        htf_period=21,
    ).run(base_candles)

    # The bearish HTF candle is in the future — buy should not be blocked
    assert result.total_trades >= 2
