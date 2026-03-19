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

    assert values["POSTGRES_HOST_PORT"] == "5434"
    assert values["DATABASE_URL"] == (
        "postgresql+psycopg://trading_bot:trading_bot@127.0.0.1:5434/trading_bot"
    )
    assert "APP_ENV" not in values


def test_api_deploy_env_example_uses_api_runtime_defaults() -> None:
    values = _parse_env_file(Path(".env.deploy.api.example"))

    assert values["APP_ENV"] == "production"
    assert values["APP_RUNTIME"] == "api"
    assert values["API_HOST"] == "0.0.0.0"
    assert values["DATABASE_URL"] == (
        "postgresql+psycopg://trading_bot:trading_bot@postgres:5432/trading_bot"
    )
    assert "WORKER_RUN_ONCE" not in values


def test_worker_deploy_env_example_uses_worker_runtime_defaults() -> None:
    values = _parse_env_file(Path(".env.deploy.worker.example"))

    assert values["APP_ENV"] == "production"
    assert values["APP_RUNTIME"] == "worker"
    assert values["WORKER_RUN_ONCE"] == "false"
    assert values["DATABASE_URL"] == (
        "postgresql+psycopg://trading_bot:trading_bot@postgres:5432/trading_bot"
    )
    assert "API_HOST" not in values
