from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import Settings, get_settings
from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings

_BACKTEST_RUNS_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("benchmark_realized_pnl", "NUMERIC(20, 8)"),
    ("benchmark_return_pct", "NUMERIC(20, 8)"),
    ("benchmark_excess_return_pct", "NUMERIC(20, 8)"),
    ("spread_pct", "NUMERIC(10, 8)"),
    ("signal_latency_bars", "INTEGER"),
    ("allowed_weekdays_utc", "TEXT"),
    ("allowed_hours_utc", "TEXT"),
    ("max_volume_fill_pct", "NUMERIC(10, 8)"),
    ("allow_partial_fills", "BOOLEAN"),
)
_ORDERS_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (("strategy_name", "VARCHAR(100)"),)
_POSITIONS_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (("strategy_name", "VARCHAR(100)"),)
_TRADES_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (("strategy_name", "VARCHAR(100)"),)
_OPERATOR_CONFIGS_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("leverage", "INTEGER"),
    ("margin_mode", "VARCHAR(50)"),
)


def _reconcile_table_columns(
    engine: Engine,
    *,
    table_name: str,
    expected_columns: tuple[tuple[str, str], ...],
) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    missing_columns = [
        (name, sql_type) for name, sql_type in expected_columns if name not in existing_columns
    ]
    if not missing_columns:
        return
    with engine.begin() as connection:
        for column_name, sql_type in missing_columns:
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}")
            )


def _reconcile_backtest_runs_schema(engine: Engine) -> None:
    _reconcile_table_columns(
        engine,
        table_name="backtest_runs",
        expected_columns=_BACKTEST_RUNS_RECONCILE_COLUMNS,
    )


def init_database(settings: Settings | None = None) -> list[str]:
    active_settings = settings or get_settings()
    engine = create_engine_from_settings(active_settings)
    Base.metadata.create_all(bind=engine)
    _reconcile_backtest_runs_schema(engine)
    _reconcile_table_columns(
        engine, table_name="orders", expected_columns=_ORDERS_RECONCILE_COLUMNS
    )
    _reconcile_table_columns(
        engine,
        table_name="positions",
        expected_columns=_POSITIONS_RECONCILE_COLUMNS,
    )
    _reconcile_table_columns(
        engine, table_name="trades", expected_columns=_TRADES_RECONCILE_COLUMNS
    )
    _reconcile_table_columns(
        engine,
        table_name="operator_configs",
        expected_columns=_OPERATOR_CONFIGS_RECONCILE_COLUMNS,
    )
    return inspect(engine).get_table_names()
