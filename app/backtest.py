from decimal import Decimal

from app.application.services.backtest_service import BacktestService
from app.application.services.market_data_service import MarketDataService
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.domain.strategies.base import Candle
from app.domain.strategies.ema_crossover import EmaCrossoverStrategy
from app.infrastructure.database.init_db import init_database
from app.infrastructure.database.session import create_session_factory

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_database(settings)
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        market_data = MarketDataService(session)
        records = market_data.list_historical_candles(
            exchange=settings.exchange_name,
            symbol=settings.default_symbol,
            timeframe=settings.default_timeframe,
        )
        if not records:
            logger.info(
                "backtest_skipped reason=no_candles exchange=%s symbol=%s timeframe=%s",
                settings.exchange_name,
                settings.default_symbol,
                settings.default_timeframe,
            )
            return
        minimum_candles = settings.strategy_slow_period + 1
        if len(records) < minimum_candles:
            logger.info(
                "backtest_skipped reason=not_enough_candles exchange=%s symbol=%s "
                "timeframe=%s count=%s required=%s",
                settings.exchange_name,
                settings.default_symbol,
                settings.default_timeframe,
                len(records),
                minimum_candles,
            )
            return

        result = BacktestService(
            strategy=EmaCrossoverStrategy(
                fast_period=settings.strategy_fast_period,
                slow_period=settings.strategy_slow_period,
            ),
            starting_equity=Decimal(str(settings.paper_account_equity)),
        ).run(
            [
                Candle(
                    open_time=record.open_time,
                    close_time=record.close_time,
                    open_price=record.open_price,
                    high_price=record.high_price,
                    low_price=record.low_price,
                    close_price=record.close_price,
                    volume=record.volume,
                )
                for record in records
            ]
        )

    logger.info(
        "backtest_completed exchange=%s symbol=%s timeframe=%s "
        "starting_equity=%s ending_equity=%s realized_pnl=%s "
        "total_return_pct=%s executions=%s max_drawdown_pct=%s",
        settings.exchange_name,
        settings.default_symbol,
        settings.default_timeframe,
        result.starting_equity,
        result.ending_equity,
        result.realized_pnl,
        result.total_return_pct,
        result.total_trades,
        result.max_drawdown_pct,
    )


if __name__ == "__main__":
    main()
