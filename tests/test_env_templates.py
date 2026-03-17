from pathlib import Path


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_local_env_example_includes_current_runtime_defaults() -> None:
    values = _parse_env_file(Path(".env.example"))

    assert values["APP_ENV"] == "local"
    assert values["API_HOST"] == "127.0.0.1"
    assert values["WORKER_RUN_ONCE"] == "true"
    assert values["STARTUP_STATE_SYNC_ENABLED"] == "true"
    assert values["NOTIFICATION_CHANNEL"] == "none"


def test_api_deploy_env_example_uses_api_runtime_defaults() -> None:
    values = _parse_env_file(Path(".env.deploy.api.example"))

    assert values["APP_ENV"] == "production"
    assert values["APP_RUNTIME"] == "api"
    assert values["API_HOST"] == "0.0.0.0"
    assert values["LIVE_TRADING_ENABLED"] == "false"
    assert "WORKER_RUN_ONCE" not in values


def test_worker_deploy_env_example_uses_worker_runtime_defaults() -> None:
    values = _parse_env_file(Path(".env.deploy.worker.example"))

    assert values["APP_ENV"] == "production"
    assert values["APP_RUNTIME"] == "worker"
    assert values["WORKER_RUN_ONCE"] == "false"
    assert values["STARTUP_STATE_SYNC_ENABLED"] == "true"
    assert "API_HOST" not in values
