from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.application.services.market_data_service import MarketDataService
from app.application.services.operational_control_service import (
    BacktestRunOptions,
    required_candles_for_backtest_options,
)


@dataclass(frozen=True, slots=True)
class MarketDataCoverageResult:
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    first_open_time: datetime | None
    latest_open_time: datetime | None
    latest_close_time: datetime | None
    required_candles: int
    additional_candles_needed: int
    satisfies_required_candles: bool
    freshness_status: str
    readiness_status: str
    detail: str


class MarketDataCoverageService:
    def __init__(self, session: Session) -> None:
        self._market_data = MarketDataService(session)

    def get_coverage(
        self,
        *,
        options: BacktestRunOptions,
        now: datetime | None = None,
    ) -> MarketDataCoverageResult:
        candles = self._market_data.list_historical_candles(
            exchange=options.exchange or "",
            symbol=options.symbol or "",
            timeframe=options.timeframe or "",
        )
        candle_count = len(candles)
        required_candles = required_candles_for_backtest_options(options)
        additional_candles_needed = max(required_candles - candle_count, 0)
        first_open_time = candles[0].open_time if candles else None
        latest_open_time = candles[-1].open_time if candles else None
        latest_close_time = candles[-1].close_time if candles else None
        freshness_status = self._freshness_status(
            timeframe=options.timeframe or "",
            latest_close_time=latest_close_time,
            now=now,
        )
        satisfies_required_candles = candle_count >= required_candles
        readiness_status, detail = self._readiness(
            candle_count=candle_count,
            required_candles=required_candles,
            additional_candles_needed=additional_candles_needed,
            freshness_status=freshness_status,
        )
        return MarketDataCoverageResult(
            exchange=options.exchange or "",
            symbol=options.symbol or "",
            timeframe=options.timeframe or "",
            candle_count=candle_count,
            first_open_time=first_open_time,
            latest_open_time=latest_open_time,
            latest_close_time=latest_close_time,
            required_candles=required_candles,
            additional_candles_needed=additional_candles_needed,
            satisfies_required_candles=satisfies_required_candles,
            freshness_status=freshness_status,
            readiness_status=readiness_status,
            detail=detail,
        )

    @staticmethod
    def _readiness(
        *,
        candle_count: int,
        required_candles: int,
        additional_candles_needed: int,
        freshness_status: str,
    ) -> tuple[str, str]:
        if candle_count == 0:
            return "not_ready", "no stored candles for this market slice"
        if additional_candles_needed > 0:
            return (
                "not_ready",
                f"need {additional_candles_needed} more candles to satisfy replay minimum",
            )
        if freshness_status == "stale":
            return "warning", "stored history is sufficient but the latest candle looks stale"
        if freshness_status == "unknown":
            return "warning", "stored history is sufficient but freshness could not be evaluated"
        return "ready", "stored history satisfies the selected replay shape"

    @staticmethod
    def _freshness_status(
        *,
        timeframe: str,
        latest_close_time: datetime | None,
        now: datetime | None,
    ) -> str:
        if latest_close_time is None:
            return "empty"
        timeframe_delta = _timeframe_to_timedelta(timeframe)
        if timeframe_delta is None:
            return "unknown"
        reference_now = now or datetime.now(UTC)
        latest_close_utc = (
            latest_close_time.replace(tzinfo=UTC)
            if latest_close_time.tzinfo is None
            else latest_close_time.astimezone(UTC)
        )
        return "fresh" if latest_close_utc >= reference_now - (timeframe_delta * 2) else "stale"


def _timeframe_to_timedelta(timeframe: str) -> timedelta | None:
    if len(timeframe) < 2:
        return None

    unit = timeframe[-1]
    try:
        value = int(timeframe[:-1])
    except ValueError:
        return None

    if value <= 0:
        return None
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return None
