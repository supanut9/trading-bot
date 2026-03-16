from app.application.services.operational_control_service import OperationalControlService
from app.config import get_settings
from app.core.logger import configure_logging, get_logger
from app.infrastructure.database.init_db import init_database

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    init_database(settings)
    result = OperationalControlService(settings).run_backtest()

    if result.status == "skipped":
        logger.info(
            "backtest_skipped reason=%s exchange=%s symbol=%s "
            "timeframe=%s count=%s required=%s notified=%s",
            result.detail,
            settings.exchange_name,
            settings.default_symbol,
            settings.default_timeframe,
            result.candle_count,
            result.required_candles,
            result.notified,
        )
        return

    logger.info(
        "backtest_completed exchange=%s symbol=%s timeframe=%s "
        "starting_equity=%s ending_equity=%s realized_pnl=%s "
        "total_return_pct=%s executions=%s max_drawdown_pct=%s "
        "risk_per_trade_pct=%s max_open_positions=%s max_daily_loss_pct=%s notified=%s",
        settings.exchange_name,
        settings.default_symbol,
        settings.default_timeframe,
        result.starting_equity,
        result.ending_equity,
        result.realized_pnl,
        result.total_return_pct,
        result.total_trades,
        result.max_drawdown_pct,
        settings.risk_per_trade_pct,
        settings.max_open_positions,
        settings.max_daily_loss_pct,
        result.notified,
    )


if __name__ == "__main__":
    main()
