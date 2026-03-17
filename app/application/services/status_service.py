from sqlalchemy import text

from app.application.services.exchange_balance_service import ExchangeBalanceService
from app.config import Settings
from app.infrastructure.database.session import create_engine_from_settings
from app.infrastructure.exchanges.factory import build_live_order_exchange_client


class StatusService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_status(self) -> dict[str, str | bool | list[dict[str, str]]]:
        database_status = self._get_database_status()
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
            "exchange": self._settings.exchange_name,
            "symbol": self._settings.default_symbol,
            "timeframe": self._settings.default_timeframe,
            "database_url": self._settings.database_url,
            "database_status": database_status,
            "account_balance_status": balance_status,
            "account_balances": account_balances,
        }

    def _get_database_status(self) -> str:
        try:
            engine = create_engine_from_settings(self._settings)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "available"
        except Exception:
            return "unavailable"
