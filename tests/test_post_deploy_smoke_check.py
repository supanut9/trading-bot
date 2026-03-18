from app.config import Settings, get_settings
from scripts.post_deploy_smoke_check import (
    main,
    run_api_smoke_check,
    run_worker_smoke_check,
)


def test_run_api_smoke_check_passes_for_matching_status() -> None:
    settings = Settings()

    def fake_fetcher(url: str) -> dict[str, object]:
        if url.endswith("/health"):
            return {"status": "ok"}
        return {
            "app": settings.app_name,
            "environment": settings.app_env,
            "execution_mode": settings.execution_mode,
            "live_trading_halted": settings.live_trading_halted,
            "live_safety_status": "disabled",
            "live_max_order_notional": None,
            "live_max_position_quantity": None,
            "exchange": settings.exchange_name,
            "symbol": settings.default_symbol,
            "timeframe": settings.default_timeframe,
            "database_status": "available",
            "account_balance_status": "disabled",
        }

    errors = run_api_smoke_check(settings, base_url="http://127.0.0.1:8000", fetcher=fake_fetcher)

    assert errors == []


def test_run_api_smoke_check_reports_mismatch() -> None:
    settings = Settings()

    def fake_fetcher(url: str) -> dict[str, object]:
        if url.endswith("/health"):
            return {"status": "ok"}
        return {
            "app": settings.app_name,
            "environment": settings.app_env,
            "execution_mode": settings.execution_mode,
            "live_trading_halted": settings.live_trading_halted,
            "live_safety_status": "disabled",
            "live_max_order_notional": None,
            "live_max_position_quantity": None,
            "exchange": settings.exchange_name,
            "symbol": settings.default_symbol,
            "timeframe": settings.default_timeframe,
            "database_status": "unavailable",
            "account_balance_status": "disabled",
        }

    errors = run_api_smoke_check(settings, base_url="http://127.0.0.1:8000", fetcher=fake_fetcher)

    assert errors == ["status.database_status expected='available' actual='unavailable'"]


def test_run_worker_smoke_check_uses_status_service() -> None:
    settings = Settings()

    class FakeStatusService:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def get_status(self) -> dict[str, object]:
            return {
                "app": settings.app_name,
                "environment": settings.app_env,
                "execution_mode": settings.execution_mode,
                "live_trading_halted": settings.live_trading_halted,
                "live_safety_status": "disabled",
                "live_max_order_notional": None,
                "live_max_position_quantity": None,
                "database_status": "available",
            }

    errors = run_worker_smoke_check(settings, status_service_factory=FakeStatusService)

    assert errors == []


def test_run_api_smoke_check_requires_live_safety_fields_to_match() -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        LIVE_TRADING_HALTED=True,
        LIVE_MAX_ORDER_NOTIONAL="250",
        LIVE_MAX_POSITION_QUANTITY="0.02000000",
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )

    def fake_fetcher(url: str) -> dict[str, object]:
        if url.endswith("/health"):
            return {"status": "ok"}
        return {
            "app": settings.app_name,
            "environment": settings.app_env,
            "execution_mode": settings.execution_mode,
            "live_trading_halted": False,
            "live_safety_status": "enabled",
            "live_max_order_notional": "250",
            "live_max_position_quantity": "0.02000000",
            "exchange": settings.exchange_name,
            "symbol": settings.default_symbol,
            "timeframe": settings.default_timeframe,
            "database_status": "available",
            "account_balance_status": "available",
        }

    errors = run_api_smoke_check(settings, base_url="http://127.0.0.1:8000", fetcher=fake_fetcher)

    assert "status.live_trading_halted expected=True actual=False" in errors
    assert "status.live_safety_status expected='halted' actual='enabled'" in errors


def test_run_worker_smoke_check_requires_startup_sync_for_live_worker() -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        STARTUP_STATE_SYNC_ENABLED=False,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
    )

    class FakeStatusService:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def get_status(self) -> dict[str, object]:
            return {
                "app": settings.app_name,
                "environment": settings.app_env,
                "execution_mode": settings.execution_mode,
                "live_trading_halted": settings.live_trading_halted,
                "live_safety_status": "enabled",
                "live_max_order_notional": None,
                "live_max_position_quantity": None,
                "database_status": "available",
            }

    errors = run_worker_smoke_check(settings, status_service_factory=FakeStatusService)

    assert errors == ["worker live smoke check requires STARTUP_STATE_SYNC_ENABLED=true"]


def test_main_returns_nonzero_when_worker_smoke_check_fails(monkeypatch) -> None:
    settings = Settings()
    get_settings.cache_clear()
    monkeypatch.setattr("scripts.post_deploy_smoke_check.get_settings", lambda: settings)
    monkeypatch.setattr(
        "scripts.post_deploy_smoke_check.run_worker_smoke_check",
        lambda _settings: ["status.database_status expected='available' actual='unavailable'"],
    )
    monkeypatch.setattr("sys.argv", ["post_deploy_smoke_check", "--role", "worker"])

    try:
        exit_code = main()
    finally:
        get_settings.cache_clear()

    assert exit_code == 1
