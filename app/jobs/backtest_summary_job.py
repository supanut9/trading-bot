from app.application.services.operational_control_service import (
    BacktestControlResult,
    OperationalControlService,
)
from app.config import Settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class BacktestSummaryJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)

    def run(self) -> BacktestControlResult:
        result = self._controls.run_backtest(source="job.backtest_summary")
        if result.status == "skipped":
            logger.info(
                "scheduled_backtest_skipped reason=%s exchange=%s symbol=%s timeframe=%s "
                "count=%s required=%s notified=%s",
                result.detail,
                self._settings.exchange_name,
                self._settings.default_symbol,
                self._settings.default_timeframe,
                result.candle_count,
                result.required_candles,
                result.notified,
            )
            return result

        logger.info(
            "scheduled_backtest_completed exchange=%s symbol=%s timeframe=%s "
            "starting_equity=%s ending_equity=%s realized_pnl=%s total_return_pct=%s "
            "executions=%s max_drawdown_pct=%s notified=%s",
            self._settings.exchange_name,
            self._settings.default_symbol,
            self._settings.default_timeframe,
            result.starting_equity,
            result.ending_equity,
            result.realized_pnl,
            result.total_return_pct,
            result.total_trades,
            result.max_drawdown_pct,
            result.notified,
        )
        return result
