from sqlalchemy import inspect, text

from app.config import Settings
from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.database.init_db import init_database
from app.infrastructure.database.session import create_engine_from_settings


def test_expected_tables_are_registered() -> None:
    assert {
        "audit_events",
        "backtest_runs",
        "candles",
        "orders",
        "performance_review_decisions",
        "positions",
        "trades",
    }.issubset(Base.metadata.tables)


def test_init_database_reconciles_backtest_run_columns(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'reconcile.db'}")
    engine = create_engine_from_settings(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE backtest_runs (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    fast_period INTEGER,
                    slow_period INTEGER,
                    starting_equity_input NUMERIC(20, 8) NOT NULL,
                    candle_count INTEGER NOT NULL,
                    required_candles INTEGER NOT NULL,
                    starting_equity NUMERIC(20, 8),
                    ending_equity NUMERIC(20, 8),
                    realized_pnl NUMERIC(20, 8),
                    total_return_pct NUMERIC(20, 8),
                    max_drawdown_pct NUMERIC(20, 8),
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    total_fees_paid NUMERIC(20, 8),
                    slippage_pct NUMERIC(10, 8),
                    fee_pct NUMERIC(10, 8),
                    walk_forward_split_ratio NUMERIC(5, 4),
                    walk_forward_in_sample_candles INTEGER,
                    walk_forward_oos_candles INTEGER,
                    walk_forward_in_sample_return_pct NUMERIC(20, 8),
                    walk_forward_oos_return_pct NUMERIC(20, 8),
                    walk_forward_oos_drawdown_pct NUMERIC(20, 8),
                    walk_forward_oos_total_trades INTEGER,
                    walk_forward_return_degradation_pct NUMERIC(20, 8),
                    walk_forward_overfitting_warning BOOLEAN,
                    rules_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )

    init_database(settings)

    columns = {column["name"] for column in inspect(engine).get_columns("backtest_runs")}
    assert {
        "benchmark_realized_pnl",
        "benchmark_return_pct",
        "benchmark_excess_return_pct",
        "spread_pct",
        "signal_latency_bars",
        "allowed_weekdays_utc",
        "allowed_hours_utc",
        "max_volume_fill_pct",
        "allow_partial_fills",
    }.issubset(columns)


def test_init_database_reconciles_strategy_identity_columns(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite:///{tmp_path / 'strategy_identity.db'}")
    engine = create_engine_from_settings(settings)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    trading_mode TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    client_order_id TEXT,
                    exchange_order_id TEXT,
                    quantity NUMERIC(20, 8) NOT NULL,
                    executed_quantity NUMERIC(20, 8) NOT NULL,
                    price NUMERIC(20, 8),
                    signal_price NUMERIC(20, 8),
                    average_fill_price NUMERIC(20, 8),
                    submitted_reason TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    trading_mode TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    quantity NUMERIC(20, 8) NOT NULL,
                    average_entry_price NUMERIC(20, 8),
                    realized_pnl NUMERIC(20, 8) NOT NULL,
                    unrealized_pnl NUMERIC(20, 8) NOT NULL,
                    stop_loss_price NUMERIC(20, 8),
                    highest_price_since_entry NUMERIC(20, 8),
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    order_id INTEGER,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    trading_mode TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity NUMERIC(20, 8) NOT NULL,
                    price NUMERIC(20, 8) NOT NULL,
                    realized_pnl NUMERIC(20, 8),
                    fee_amount NUMERIC(20, 8),
                    fee_asset TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
        )

    init_database(settings)

    orders_columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    positions_columns = {column["name"] for column in inspect(engine).get_columns("positions")}
    trades_columns = {column["name"] for column in inspect(engine).get_columns("trades")}

    assert "strategy_name" in orders_columns
    assert "strategy_name" in positions_columns
    assert "strategy_name" in trades_columns
