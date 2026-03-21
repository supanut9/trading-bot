"""MarketDataRepository — thin facade over CandleRepository for ML workflows."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.infrastructure.database.models.candle import CandleRecord
from app.infrastructure.database.repositories.candle_repository import CandleRepository


class MarketDataRepository:
    """Read-only access to candle data for model training and feature engineering."""

    def __init__(self, session: Session) -> None:
        self._candles = CandleRepository(session)

    def list_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        limit: int = 10000,
    ) -> Sequence[CandleRecord]:
        """Return up to *limit* candles ordered oldest-first."""
        records = self._candles.list_recent(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
        # list_recent returns newest-first; reverse so callers get chronological order.
        return list(reversed(records))
