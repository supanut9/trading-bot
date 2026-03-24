from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.operator_config import OperatorConfigRecord


class OperatorConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_name(self, config_name: str) -> OperatorConfigRecord | None:
        statement: Select[tuple[OperatorConfigRecord]] = select(OperatorConfigRecord).where(
            OperatorConfigRecord.config_name == config_name
        )
        return self._session.execute(statement).scalar_one_or_none()

    def upsert(
        self,
        *,
        config_name: str,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        fast_period: int,
        slow_period: int,
        trading_mode: str = "SPOT",
        leverage: int = 1,
        margin_mode: str = "ISOLATED",
        updated_by: str,
    ) -> OperatorConfigRecord:
        record = self.get_by_name(config_name)
        if record is None:
            record = OperatorConfigRecord(
                config_name=config_name,
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                fast_period=fast_period,
                slow_period=slow_period,
                trading_mode=trading_mode,
                leverage=leverage,
                margin_mode=margin_mode,
                updated_by=updated_by,
            )
            self._session.add(record)
            self._session.flush()
            return record

        record.strategy_name = strategy_name
        record.symbol = symbol
        record.timeframe = timeframe
        record.fast_period = fast_period
        record.slow_period = slow_period
        record.trading_mode = trading_mode
        record.leverage = leverage
        record.margin_mode = margin_mode
        record.updated_by = updated_by
        self._session.flush()
        return record
