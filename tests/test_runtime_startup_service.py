import pytest

from app.application.services.runtime_startup_service import (
    build_runtime_startup_context,
    validate_runtime_settings,
    validate_runtime_startup,
)
from app.config import Settings


def test_build_runtime_startup_context_includes_runtime_summary() -> None:
    settings = Settings()

    context = build_runtime_startup_context(settings, "worker")

    assert context.component == "worker"
    assert context.app == "trading-bot"
    assert context.environment == "local"
    assert context.execution_mode == "paper"
    assert context.database_scheme == "sqlite"


def test_validate_runtime_settings_rejects_sqlite_outside_local() -> None:
    settings = Settings(APP_ENV="production")

    errors = validate_runtime_settings(settings, "worker")

    assert errors == ["non-local runtime requires a PostgreSQL-compatible DATABASE_URL"]


def test_validate_runtime_settings_rejects_loopback_api_binding_outside_local() -> None:
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://bot:bot@postgres:5432/trading_bot",
    )

    errors = validate_runtime_settings(settings, "api")

    assert errors == ["non-local api runtime must not bind API_HOST to a loopback address"]


def test_validate_runtime_settings_requires_webhook_url_for_webhook_channel() -> None:
    settings = Settings(NOTIFICATION_CHANNEL="webhook")

    errors = validate_runtime_settings(settings, "worker")

    assert errors == ["NOTIFICATION_WEBHOOK_URL is required when NOTIFICATION_CHANNEL=webhook"]


def test_validate_runtime_settings_requires_startup_sync_for_live_worker() -> None:
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://bot:bot@postgres:5432/trading_bot",
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        STARTUP_STATE_SYNC_ENABLED=False,
    )

    errors = validate_runtime_settings(settings, "worker")

    assert errors == ["live worker runtime requires STARTUP_STATE_SYNC_ENABLED=true"]


def test_validate_runtime_startup_checks_database_connectivity(monkeypatch) -> None:
    settings = Settings(DATABASE_URL="sqlite:///./runtime_startup_test.db")

    monkeypatch.setattr(
        "app.application.services.runtime_startup_service.ensure_database_connectivity",
        lambda _settings: None,
    )

    context = validate_runtime_startup(settings, "backtest")

    assert context.component == "backtest"


def test_validate_runtime_startup_raises_on_invalid_settings(monkeypatch) -> None:
    settings = Settings(APP_ENV="production")
    called = {"db": False}

    def fail_if_called(_settings: Settings) -> None:
        called["db"] = True

    monkeypatch.setattr(
        "app.application.services.runtime_startup_service.ensure_database_connectivity",
        fail_if_called,
    )

    with pytest.raises(ValueError, match="non-local runtime requires a PostgreSQL-compatible"):
        validate_runtime_startup(settings, "worker")

    assert called["db"] is False
