import pytest

from app.config import Settings


def test_allows_default_paper_execution_mode() -> None:
    settings = Settings()

    assert settings.execution_mode == "paper"


def test_rejects_conflicting_paper_and_live_flags() -> None:
    with pytest.raises(
        ValueError,
        match="PAPER_TRADING and LIVE_TRADING_ENABLED cannot both be true",
    ):
        Settings(PAPER_TRADING=True, LIVE_TRADING_ENABLED=True)


def test_rejects_non_paper_mode_without_live_enablement() -> None:
    with pytest.raises(
        ValueError,
        match="LIVE_TRADING_ENABLED must be true when PAPER_TRADING is false",
    ):
        Settings(PAPER_TRADING=False, LIVE_TRADING_ENABLED=False)


def test_allows_explicit_live_execution_mode() -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )

    assert settings.execution_mode == "live"


def test_rejects_live_mode_without_exchange_credentials() -> None:
    with pytest.raises(
        ValueError,
        match="EXCHANGE_API_KEY and EXCHANGE_API_SECRET are required when live trading is enabled",
    ):
        Settings(PAPER_TRADING=False, LIVE_TRADING_ENABLED=True)


def test_rejects_non_positive_live_max_order_notional() -> None:
    with pytest.raises(
        ValueError,
        match="LIVE_MAX_ORDER_NOTIONAL must be positive when provided",
    ):
        Settings(LIVE_MAX_ORDER_NOTIONAL=0)


def test_rejects_non_positive_live_max_position_quantity() -> None:
    with pytest.raises(
        ValueError,
        match="LIVE_MAX_POSITION_QUANTITY must be positive when provided",
    ):
        Settings(LIVE_MAX_POSITION_QUANTITY=0)
