from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base


def test_expected_tables_are_registered() -> None:
    assert {"audit_events", "backtest_runs", "candles", "orders", "positions", "trades"}.issubset(
        Base.metadata.tables
    )
