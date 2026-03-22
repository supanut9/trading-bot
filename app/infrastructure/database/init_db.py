from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import Settings, get_settings
from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings

_BACKTEST_RUNS_RECONCILE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("spread_pct", "NUMERIC(10, 8)"),
    ("signal_latency_bars", "INTEGER"),
    ("allowed_weekdays_utc", "TEXT"),
    ("allowed_hours_utc", "TEXT"),
    ("max_volume_fill_pct", "NUMERIC(10, 8)"),
    ("allow_partial_fills", "BOOLEAN"),
)


def _reconcile_backtest_runs_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    if "backtest_runs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("backtest_runs")}
    missing_columns = [
        (name, sql_type)
        for name, sql_type in _BACKTEST_RUNS_RECONCILE_COLUMNS
        if name not in existing_columns
    ]
    if not missing_columns:
        return
    with engine.begin() as connection:
        for column_name, sql_type in missing_columns:
            connection.execute(
                text(f"ALTER TABLE backtest_runs ADD COLUMN {column_name} {sql_type}")
            )


def init_database(settings: Settings | None = None) -> list[str]:
    active_settings = settings or get_settings()
    engine = create_engine_from_settings(active_settings)
    Base.metadata.create_all(bind=engine)
    _reconcile_backtest_runs_schema(engine)
    return inspect(engine).get_table_names()
