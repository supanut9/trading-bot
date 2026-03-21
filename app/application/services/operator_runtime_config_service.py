from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database.repositories.operator_config_repository import (
    OperatorConfigRepository,
)

PAPER_RUNTIME_OPERATOR_CONFIG = "paper_runtime_defaults"
OPERATOR_STRATEGY_EMA_CROSSOVER = "ema_crossover"


@dataclass(frozen=True, slots=True)
class OperatorRuntimeConfig:
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int
    slow_period: int
    trading_mode: str
    source: str
    updated_at: datetime | None = None
    updated_by: str | None = None


@dataclass(frozen=True, slots=True)
class OperatorRuntimeConfigUpdate:
    previous: OperatorRuntimeConfig
    current: OperatorRuntimeConfig
    changed: bool


class OperatorRuntimeConfigService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._configs = OperatorConfigRepository(session)
        self._settings = settings

    def get_effective_config(self) -> OperatorRuntimeConfig:
        if not hasattr(self._session, "execute"):
            return OperatorRuntimeConfig(
                strategy_name=OPERATOR_STRATEGY_EMA_CROSSOVER,
                exchange=self._settings.exchange_name,
                symbol=self._settings.default_symbol,
                timeframe=self._settings.default_timeframe,
                fast_period=self._settings.strategy_fast_period,
                slow_period=self._settings.strategy_slow_period,
                trading_mode=self._settings.trading_mode,
                source="settings",
            )
        record = self._configs.get_by_name(PAPER_RUNTIME_OPERATOR_CONFIG)
        if record is None:
            return OperatorRuntimeConfig(
                strategy_name=OPERATOR_STRATEGY_EMA_CROSSOVER,
                exchange=self._settings.exchange_name,
                symbol=self._settings.default_symbol,
                timeframe=self._settings.default_timeframe,
                fast_period=self._settings.strategy_fast_period,
                slow_period=self._settings.strategy_slow_period,
                trading_mode=self._settings.trading_mode,
                source="settings",
            )
        return OperatorRuntimeConfig(
            strategy_name=record.strategy_name,
            exchange=self._settings.exchange_name,
            symbol=record.symbol,
            timeframe=record.timeframe,
            fast_period=record.fast_period,
            slow_period=record.slow_period,
            trading_mode=record.trading_mode,
            source="runtime_config",
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )

    def set_config(
        self,
        *,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        fast_period: int,
        slow_period: int,
        trading_mode: str,
        updated_by: str,
    ) -> OperatorRuntimeConfigUpdate:
        normalized_strategy = strategy_name.strip().lower()
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip()
        normalized_trading_mode = trading_mode.strip().upper()
        if normalized_strategy != OPERATOR_STRATEGY_EMA_CROSSOVER:
            raise ValueError(f"unsupported runtime strategy: {strategy_name}")
        if normalized_trading_mode not in ("SPOT", "FUTURES"):
            raise ValueError(f"unsupported trading mode: {trading_mode}")
        if not normalized_symbol or not normalized_timeframe:
            raise ValueError("symbol and timeframe are required")
        if fast_period <= 0 or slow_period <= 0:
            raise ValueError("strategy periods must be positive")
        if fast_period >= slow_period:
            raise ValueError("fast period must be smaller than slow period")

        previous = self.get_effective_config()
        record = self._configs.upsert(
            config_name=PAPER_RUNTIME_OPERATOR_CONFIG,
            strategy_name=normalized_strategy,
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            fast_period=fast_period,
            slow_period=slow_period,
            trading_mode=normalized_trading_mode,
            updated_by=updated_by,
        )
        current = OperatorRuntimeConfig(
            strategy_name=record.strategy_name,
            exchange=self._settings.exchange_name,
            symbol=record.symbol,
            timeframe=record.timeframe,
            fast_period=record.fast_period,
            slow_period=record.slow_period,
            trading_mode=record.trading_mode,
            source="runtime_config",
            updated_at=record.updated_at,
            updated_by=record.updated_by,
        )
        return OperatorRuntimeConfigUpdate(
            previous=previous,
            current=current,
            changed=previous != current,
        )
