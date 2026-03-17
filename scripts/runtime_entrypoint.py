import os
from collections.abc import Callable
from typing import Literal

import uvicorn

from app.backtest import main as run_backtest
from app.config import get_settings
from app.worker import main as run_worker

RuntimeRole = Literal["api", "worker", "backtest"]


def get_runtime_role(value: str | None = None) -> RuntimeRole:
    runtime = (value or os.getenv("APP_RUNTIME", "api")).strip().lower()
    allowed: tuple[RuntimeRole, ...] = ("api", "worker", "backtest")
    if runtime not in allowed:
        allowed_text = ", ".join(allowed)
        raise ValueError(f"APP_RUNTIME must be one of: {allowed_text}")
    return runtime


def build_runtime_runner(runtime: RuntimeRole) -> Callable[[], None]:
    if runtime == "api":
        settings = get_settings()

        def run_api() -> None:
            uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port)

        return run_api
    if runtime == "worker":
        return run_worker
    return run_backtest


def main() -> None:
    runtime = get_runtime_role()
    runner = build_runtime_runner(runtime)
    runner()


if __name__ == "__main__":
    main()
