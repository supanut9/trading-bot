from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domain.strategies.rule_builder import RuleBuilderStrategyConfig
from app.infrastructure.database.repositories.backtest_run_repository import BacktestRunRepository
from app.interfaces.api.backtest_rule_mapping import to_rule_builder_request


@dataclass(frozen=True, slots=True)
class BacktestRunView:
    id: int
    created_at: datetime
    source: str
    status: str
    detail: str
    strategy_name: str
    exchange: str
    symbol: str
    timeframe: str
    fast_period: int | None
    slow_period: int | None
    starting_equity_input: Decimal
    candle_count: int
    required_candles: int
    starting_equity: Decimal | None
    ending_equity: Decimal | None
    realized_pnl: Decimal | None
    total_return_pct: Decimal | None
    max_drawdown_pct: Decimal | None
    total_trades: int | None
    winning_trades: int | None
    losing_trades: int | None
    rules_payload: dict[str, Any] | None


class BacktestRunHistoryService:
    def __init__(
        self,
        *,
        session: Session | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self._session = session
        self._session_factory = session_factory

    def record_run(
        self,
        *,
        source: str,
        result: Any,
    ) -> None:
        rules_json = self._serialize_rules(result.rules)
        self._with_repository(
            lambda repository: repository.create(
                source=source,
                status=result.status,
                detail=result.detail,
                strategy_name=result.strategy_name,
                exchange=result.exchange,
                symbol=result.symbol,
                timeframe=result.timeframe,
                fast_period=result.fast_period,
                slow_period=result.slow_period,
                starting_equity_input=result.starting_equity_input,
                candle_count=result.candle_count,
                required_candles=result.required_candles,
                starting_equity=result.starting_equity,
                ending_equity=result.ending_equity,
                realized_pnl=result.realized_pnl,
                total_return_pct=result.total_return_pct,
                max_drawdown_pct=result.max_drawdown_pct,
                total_trades=result.total_trades,
                winning_trades=result.winning_trades,
                losing_trades=result.losing_trades,
                rules_json=rules_json,
            )
        )

    def list_recent(self, *, limit: int = 20) -> list[BacktestRunView]:
        return [
            self._to_view(record)
            for record in self._with_repository(
                lambda repository: repository.list_recent(limit=limit)
            )
        ]

    def _with_repository(self, fn: Any) -> Any:
        if self._session is not None:
            return fn(BacktestRunRepository(self._session))
        if self._session_factory is None:
            return []
        with self._session_factory() as session:
            result = fn(BacktestRunRepository(session))
            session.commit()
            return result

    @staticmethod
    def _serialize_rules(rules: RuleBuilderStrategyConfig | None) -> str | None:
        if rules is None:
            return None
        return json.dumps(
            to_rule_builder_request(rules).model_dump(mode="python"),
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def _to_view(record: Any) -> BacktestRunView:
        rules_payload = None
        if record.rules_json:
            rules_payload = json.loads(record.rules_json)
        return BacktestRunView(
            id=record.id,
            created_at=record.created_at,
            source=record.source,
            status=record.status,
            detail=record.detail,
            strategy_name=record.strategy_name,
            exchange=record.exchange,
            symbol=record.symbol,
            timeframe=record.timeframe,
            fast_period=record.fast_period,
            slow_period=record.slow_period,
            starting_equity_input=record.starting_equity_input,
            candle_count=record.candle_count,
            required_candles=record.required_candles,
            starting_equity=record.starting_equity,
            ending_equity=record.ending_equity,
            realized_pnl=record.realized_pnl,
            total_return_pct=record.total_return_pct,
            max_drawdown_pct=record.max_drawdown_pct,
            total_trades=record.total_trades,
            winning_trades=record.winning_trades,
            losing_trades=record.losing_trades,
            rules_payload=rules_payload,
        )
