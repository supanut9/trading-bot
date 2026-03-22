from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.services.exchange_balance_service import ExchangeBalanceService
from app.application.services.live_operator_control_service import LiveOperatorControlService
from app.application.services.live_readiness_service import LiveReadinessService
from app.application.services.operator_runtime_config_service import OperatorRuntimeConfigService
from app.config import Settings
from app.infrastructure.database.session import create_engine_from_settings
from app.infrastructure.exchanges.factory import (
    build_live_order_exchange_client,
    build_market_data_exchange_client,
)


class StatusService:
    def __init__(self, settings: Settings, *, session: Session | None = None) -> None:
        self._settings = settings
        self._session = session

    def get_status(self) -> dict[str, str | bool | int | list[dict[str, str]] | None]:
        database_status = self._get_database_status()
        effective_live_halt = self._effective_live_trading_halted()
        effective_operator_config = self._effective_operator_config()
        live_readiness = self._live_readiness_report()
        latest_price_status = "unavailable"
        latest_price: str | None = None
        try:
            latest_ticker = build_market_data_exchange_client(self._settings).fetch_latest_price(
                symbol=effective_operator_config["symbol"]
            )
            latest_price_status = "available"
            latest_price = format(latest_ticker.price, "f")
        except Exception:
            latest_price_status = "unavailable"

        balance_status = "disabled"
        account_balances: list[dict[str, str]] = []
        if self._settings.live_trading_enabled:
            try:
                trading_mode = effective_operator_config.get("trading_mode")
                client = build_live_order_exchange_client(self._settings, trading_mode=trading_mode)
                balances = ExchangeBalanceService(
                    self._settings,
                    client=client,
                ).list_symbol_balances()
                balance_status = "available"
                account_balances = [
                    {
                        "asset": balance.asset,
                        "free": format(balance.free, "f"),
                        "locked": format(balance.locked, "f"),
                    }
                    for balance in balances
                ]
            except Exception:
                balance_status = "unavailable"
        elif self._settings.paper_trading:
            from sqlalchemy import func, select

            from app.infrastructure.database.models.position import PositionRecord

            paper_pnl = 0.0
            if self._session is not None:
                try:
                    stmt = select(func.sum(PositionRecord.realized_pnl)).where(
                        PositionRecord.mode == "paper"
                    )
                    paper_pnl = float(self._session.execute(stmt).scalar() or 0.0)
                except Exception:
                    pass

            simulated_equity = self._settings.paper_account_equity + paper_pnl
            balance_status = "simulated"
            account_balances = [
                {
                    "asset": "USDT",
                    "free": format(simulated_equity, "f"),
                    "locked": "0.000000",
                }
            ]
        return {
            "app": self._settings.app_name,
            "environment": self._settings.app_env,
            "execution_mode": self._settings.execution_mode,
            "paper_trading": self._settings.paper_trading,
            "live_trading_enabled": self._settings.live_trading_enabled,
            "live_trading_halted": effective_live_halt,
            "live_safety_status": self._live_safety_status(effective_live_halt),
            "live_readiness_status": live_readiness["status"],
            "live_readiness_blocking_reasons": live_readiness["blocking_reasons"],
            "live_max_order_notional": (
                format(self._settings.live_max_order_notional, "f")
                if self._settings.live_max_order_notional is not None
                else None
            ),
            "live_max_position_quantity": (
                format(self._settings.live_max_position_quantity, "f")
                if self._settings.live_max_position_quantity is not None
                else None
            ),
            "exchange": self._settings.exchange_name,
            "strategy_name": effective_operator_config["strategy_name"],
            "symbol": effective_operator_config["symbol"],
            "timeframe": effective_operator_config["timeframe"],
            "fast_period": effective_operator_config["fast_period"],
            "slow_period": effective_operator_config["slow_period"],
            "operator_config_source": effective_operator_config["source"],
            "trading_mode": effective_operator_config.get("trading_mode", "SPOT"),
            "database_url": self._settings.database_url,
            "database_status": database_status,
            "latest_price_status": latest_price_status,
            "latest_price": latest_price,
            "account_balance_status": balance_status,
            "account_balances": account_balances,
        }

    def _live_safety_status(self, live_trading_halted: bool) -> str:
        if not self._settings.live_trading_enabled:
            return "disabled"
        if live_trading_halted:
            return "halted"
        return "enabled"

    def _effective_live_trading_halted(self) -> bool:
        if self._session is None:
            return self._settings.live_trading_halted
        try:
            return (
                LiveOperatorControlService(
                    self._session,
                    self._settings,
                )
                .get_live_trading_halt_state()
                .halted
            )
        except SQLAlchemyError:
            self._session.rollback()
            return self._settings.live_trading_halted

    def _effective_operator_config(self) -> dict[str, str | int]:
        if self._session is None:
            return {
                "strategy_name": "ema_crossover",
                "symbol": self._settings.default_symbol,
                "timeframe": self._settings.default_timeframe,
                "fast_period": self._settings.strategy_fast_period,
                "slow_period": self._settings.strategy_slow_period,
                "trading_mode": self._settings.trading_mode,
                "source": "settings",
            }
        try:
            config = OperatorRuntimeConfigService(
                self._session,
                self._settings,
            ).get_effective_config()
            return {
                "strategy_name": config.strategy_name,
                "symbol": config.symbol,
                "timeframe": config.timeframe,
                "fast_period": config.fast_period,
                "slow_period": config.slow_period,
                "trading_mode": config.trading_mode,
                "source": config.source,
            }
        except SQLAlchemyError:
            self._session.rollback()
            return {
                "strategy_name": "ema_crossover",
                "symbol": self._settings.default_symbol,
                "timeframe": self._settings.default_timeframe,
                "fast_period": self._settings.strategy_fast_period,
                "slow_period": self._settings.strategy_slow_period,
                "trading_mode": self._settings.trading_mode,
                "source": "settings",
            }

    def _live_readiness_report(self) -> dict[str, str | list[str] | None]:
        if self._session is None:
            return {"status": None, "blocking_reasons": []}
        try:
            report = LiveReadinessService(self._session, self._settings).build_report()
            return {
                "status": report.status,
                "blocking_reasons": list(report.blocking_reasons),
            }
        except SQLAlchemyError:
            self._session.rollback()
            return {"status": None, "blocking_reasons": []}

    def _get_database_status(self) -> str:
        try:
            engine = create_engine_from_settings(self._settings)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "available"
        except Exception:
            return "unavailable"
