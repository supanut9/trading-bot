from app.application.services.operational_control_service import (
    BacktestControlResult,
    OperationalControlService,
)
from app.config import Settings
from app.core.logger import build_correlation_id, correlation_context, get_logger

logger = get_logger(__name__)


class BacktestSummaryJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._controls = OperationalControlService(settings)

    def run(self) -> BacktestControlResult:
        with correlation_context(build_correlation_id("backtest")):
            result = self._controls.run_backtest(source="job.backtest_summary")
            if result.status == "skipped":
                logger.info(
                    "scheduled_backtest_skipped reason=%s exchange=%s symbol=%s timeframe=%s "
                    "count=%s required=%s notified=%s live_safety_status=%s",
                    result.detail,
                    self._settings.exchange_name,
                    self._settings.default_symbol,
                    self._settings.default_timeframe,
                    result.candle_count,
                    result.required_candles,
                    result.notified,
                    "disabled"
                    if not self._settings.live_trading_enabled
                    else ("halted" if self._settings.live_trading_halted else "enabled"),
                )
                return result

            logger.info(
                "scheduled_backtest_completed exchange=%s symbol=%s timeframe=%s "
                "starting_equity=%s ending_equity=%s realized_pnl=%s total_return_pct=%s "
                "executions=%s max_drawdown_pct=%s notified=%s live_safety_status=%s",
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
                "disabled"
                if not self._settings.live_trading_enabled
                else ("halted" if self._settings.live_trading_halted else "enabled"),
            )
            return result
