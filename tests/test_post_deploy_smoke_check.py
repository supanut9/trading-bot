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
                "database_status": "available",
            }

    errors = run_worker_smoke_check(settings, status_service_factory=FakeStatusService)

    assert errors == []


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
