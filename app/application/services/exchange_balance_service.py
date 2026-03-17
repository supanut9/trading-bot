from collections.abc import Sequence

from app.config import Settings
from app.infrastructure.exchanges.base import ExchangeAssetBalance, LiveOrderExchangeClient


class ExchangeBalanceService:
    def __init__(self, settings: Settings, *, client: LiveOrderExchangeClient) -> None:
        self._settings = settings
        self._client = client

    def list_symbol_balances(self) -> Sequence[ExchangeAssetBalance]:
        base_asset, quote_asset = self._split_symbol_assets(self._settings.default_symbol)
        relevant_assets = {base_asset, quote_asset}
        balances = self._client.fetch_account_balances()
        return [balance for balance in balances if balance.asset in relevant_assets]

    def _split_symbol_assets(self, symbol: str) -> tuple[str, str]:
        base_asset, quote_asset = symbol.split("/", maxsplit=1)
        return base_asset.upper(), quote_asset.upper()
