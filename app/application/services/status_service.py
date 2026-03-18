from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.services.exchange_balance_service import ExchangeBalanceService
from app.application.services.live_operator_control_service import LiveOperatorControlService
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

    def get_status(self) -> dict[str, str | bool | list[dict[str, str]]]:
        database_status = self._get_database_status()
        effective_live_halt = self._effective_live_trading_halted()
        latest_price_status = "unavailable"
        latest_price: str | None = None
        try:
            latest_ticker = build_market_data_exchange_client(self._settings).fetch_latest_price(
                symbol=self._settings.default_symbol
            )
            latest_price_status = "available"
            latest_price = format(latest_ticker.price, "f")
        except Exception:
            latest_price_status = "unavailable"

        balance_status = "disabled"
        account_balances: list[dict[str, str]] = []
        if self._settings.live_trading_enabled:
            try:
                client = build_live_order_exchange_client(self._settings)
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
        return {
            "app": self._settings.app_name,
            "environment": self._settings.app_env,
            "execution_mode": self._settings.execution_mode,
            "paper_trading": self._settings.paper_trading,
            "live_trading_enabled": self._settings.live_trading_enabled,
            "live_trading_halted": effective_live_halt,
            "live_safety_status": self._live_safety_status(effective_live_halt),
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
            "symbol": self._settings.default_symbol,
            "timeframe": self._settings.default_timeframe,
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
            return self._settings.live_trading_halted

    def _get_database_status(self) -> str:
        try:
            engine = create_engine_from_settings(self._settings)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "available"
        except Exception:
            return "unavailable"
