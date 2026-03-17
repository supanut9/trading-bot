from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.services.market_data_service import CandleInput, MarketDataService


class UnknownDemoScenarioError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DemoScenarioDefinition:
    name: str
    detail: str
    closes: tuple[int, ...]
    expected_signal_action: str | None


@dataclass(frozen=True, slots=True)
class DemoScenarioLoadResult:
    scenario: str
    detail: str
    exchange: str
    symbol: str
    timeframe: str
    candle_count: int
    stored_count: int
    latest_open_time: datetime
    expected_signal_action: str | None


class DemoScenarioService:
    _scenario_start = datetime(2026, 1, 1, tzinfo=UTC)
    _scenario_definitions: dict[str, DemoScenarioDefinition] = {
        "buy-crossover": DemoScenarioDefinition(
            name="buy-crossover",
            detail="loads candles that produce a buy crossover on the latest closed candle",
            closes=(10, 10, 10, 10, 10, 9, 9, 9, 20),
            expected_signal_action="buy",
        ),
        "sell-crossover": DemoScenarioDefinition(
            name="sell-crossover",
            detail="loads candles that produce a sell crossover on the latest closed candle",
            closes=(20, 20, 20, 20, 20, 21, 21, 21, 5),
            expected_signal_action="sell",
        ),
        "no-action": DemoScenarioDefinition(
            name="no-action",
            detail="loads candles that leave the strategy without a crossover signal",
            closes=(10, 11, 12, 13, 14, 15, 16, 17, 18),
            expected_signal_action=None,
        ),
    }

    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data

    def load(
        self,
        *,
        scenario_name: str,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> DemoScenarioLoadResult:
        definition = self._scenario_definitions.get(scenario_name)
        if definition is None:
            available = ", ".join(sorted(self._scenario_definitions))
            raise UnknownDemoScenarioError(
                f"unknown demo scenario '{scenario_name}', expected one of: {available}"
            )

        candles = self._build_candles(definition.closes)
        stored = self._market_data.store_candles(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )
        return DemoScenarioLoadResult(
            scenario=definition.name,
            detail=definition.detail,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_count=len(candles),
            stored_count=len(stored),
            latest_open_time=max(candle.open_time for candle in candles),
            expected_signal_action=definition.expected_signal_action,
        )

    @classmethod
    def _build_candles(cls, closes: tuple[int, ...]) -> list[CandleInput]:
        candles: list[CandleInput] = []
        for index, close in enumerate(closes):
            open_time = cls._scenario_start + timedelta(hours=index)
            close_price = Decimal(close)
            candles.append(
                CandleInput(
                    open_time=open_time,
                    close_time=open_time + timedelta(hours=1),
                    open_price=close_price,
                    high_price=close_price,
                    low_price=close_price,
                    close_price=close_price,
                    volume=Decimal("1"),
                )
            )
        return candles
