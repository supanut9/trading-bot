from sqlalchemy import text

from app.config import Settings
from app.infrastructure.database.session import create_engine_from_settings


class StatusService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_status(self) -> dict[str, str | bool]:
        database_status = self._get_database_status()
        return {
            "app": self._settings.app_name,
            "environment": self._settings.app_env,
            "paper_trading": self._settings.paper_trading,
            "live_trading_enabled": self._settings.live_trading_enabled,
            "exchange": self._settings.exchange_name,
            "symbol": self._settings.default_symbol,
            "timeframe": self._settings.default_timeframe,
            "database_url": self._settings.database_url,
            "database_status": database_status,
        }

    def _get_database_status(self) -> str:
        try:
            engine = create_engine_from_settings(self._settings)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "available"
        except Exception:
            return "unavailable"
