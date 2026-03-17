import pytest

from app.config import Settings, get_settings
from scripts.runtime_entrypoint import build_runtime_runner, get_runtime_role, main


def test_get_runtime_role_defaults_to_api(monkeypatch) -> None:
    monkeypatch.delenv("APP_RUNTIME", raising=False)

    assert get_runtime_role() == "api"


def test_get_runtime_role_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="APP_RUNTIME must be one of"):
        get_runtime_role("scheduler")


def test_build_runtime_runner_for_api_uses_settings(monkeypatch) -> None:
    settings = Settings(API_HOST="0.0.0.0", API_PORT=9000)
    events: list[tuple[str, str, int]] = []

    monkeypatch.setattr("scripts.runtime_entrypoint.get_settings", lambda: settings)
    monkeypatch.setattr(
        "scripts.runtime_entrypoint.uvicorn.run",
        lambda app, host, port: events.append((app, host, port)),
    )
    get_settings.cache_clear()

    try:
        runner = build_runtime_runner("api")
        runner()
    finally:
        get_settings.cache_clear()

    assert events == [("app.main:app", "0.0.0.0", 9000)]


def test_main_dispatches_worker_runtime(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setenv("APP_RUNTIME", "worker")
    monkeypatch.setattr(
        "scripts.runtime_entrypoint.run_worker",
        lambda: events.append("worker"),
    )
    monkeypatch.setattr(
        "scripts.runtime_entrypoint.run_backtest", lambda: events.append("backtest")
    )
    monkeypatch.setattr(
        "scripts.runtime_entrypoint.uvicorn.run",
        lambda *_args, **_kwargs: events.append("api"),
    )

    main()

    assert events == ["worker"]
