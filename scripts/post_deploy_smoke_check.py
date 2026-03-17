import argparse
import json
from collections.abc import Callable
from typing import Any, Literal
from urllib.error import URLError
from urllib.request import urlopen

from app.application.services.status_service import StatusService
from app.config import Settings, get_settings

SmokeCheckRole = Literal["api", "worker"]


def fetch_json(url: str, timeout_seconds: int = 5) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def run_api_smoke_check(
    settings: Settings,
    *,
    base_url: str,
    fetcher: Callable[[str], dict[str, Any]] = fetch_json,
) -> list[str]:
    health = fetcher(f"{base_url.rstrip('/')}/health")
    status = fetcher(f"{base_url.rstrip('/')}/status")

    checks = [
        ("health.status", health.get("status"), "ok"),
        ("status.app", status.get("app"), settings.app_name),
        ("status.environment", status.get("environment"), settings.app_env),
        ("status.execution_mode", status.get("execution_mode"), settings.execution_mode),
        ("status.exchange", status.get("exchange"), settings.exchange_name),
        ("status.symbol", status.get("symbol"), settings.default_symbol),
        ("status.timeframe", status.get("timeframe"), settings.default_timeframe),
        ("status.database_status", status.get("database_status"), "available"),
    ]

    errors = [
        f"{field} expected={expected!r} actual={actual!r}"
        for field, actual, expected in checks
        if actual != expected
    ]

    balance_status = status.get("account_balance_status")
    if settings.live_trading_enabled:
        if balance_status != "available":
            errors.append(
                f"status.account_balance_status expected='available' actual={balance_status!r}"
            )
    elif balance_status != "disabled":
        errors.append(
            f"status.account_balance_status expected='disabled' actual={balance_status!r}"
        )

    return errors


def run_worker_smoke_check(
    settings: Settings,
    *,
    status_service_factory: Callable[[Settings], StatusService] = StatusService,
) -> list[str]:
    status = status_service_factory(settings).get_status()
    checks = [
        ("status.app", status.get("app"), settings.app_name),
        ("status.environment", status.get("environment"), settings.app_env),
        ("status.execution_mode", status.get("execution_mode"), settings.execution_mode),
        ("status.database_status", status.get("database_status"), "available"),
    ]
    return [
        f"{field} expected={expected!r} actual={actual!r}"
        for field, actual, expected in checks
        if actual != expected
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run non-destructive deployment smoke checks.")
    parser.add_argument("--role", choices=("api", "worker"), required=True)
    parser.add_argument(
        "--base-url",
        default=None,
        help="API base URL for the api smoke check. Defaults to http://127.0.0.1:<API_PORT>.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()

    try:
        if args.role == "api":
            base_url = args.base_url or f"http://127.0.0.1:{settings.api_port}"
            errors = run_api_smoke_check(settings, base_url=base_url)
        else:
            errors = run_worker_smoke_check(settings)
    except URLError as exc:
        print(f"smoke_check_failed reason=request_error detail={exc}")
        return 1
    except Exception as exc:
        print(f"smoke_check_failed reason=unexpected_error detail={exc}")
        return 1

    if errors:
        print(f"smoke_check_failed role={args.role}")
        for error in errors:
            print(error)
        return 1

    print(
        f"smoke_check_passed role={args.role} env={settings.app_env} mode={settings.execution_mode}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
