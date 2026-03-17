from app.config import Settings, get_settings
from app.worker import main


def test_worker_run_once_executes_worker_job_without_scheduler(monkeypatch) -> None:
    settings = Settings(WORKER_RUN_ONCE=True)
    events: list[str] = []

    class FakeWorkerCycleJob:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run(self) -> None:
            events.append("worker_run")

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)

    def fail_scheduler() -> None:
        raise AssertionError("scheduler should not be used in run-once mode")

    monkeypatch.setattr("app.worker.IntervalScheduler", fail_scheduler)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert events == ["worker_run"]


def test_worker_scheduled_mode_registers_backtest_job_when_enabled(monkeypatch) -> None:
    settings = Settings(
        WORKER_RUN_ONCE=False,
        WORKER_POLL_INTERVAL_SECONDS=60,
        BACKTEST_SCHEDULE_ENABLED=True,
        BACKTEST_SCHEDULE_INTERVAL_SECONDS=300,
    )
    events: list[str] = []

    class FakeWorkerCycleJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> str:
            events.append("worker_job")
            return "worker"

    class FakeBacktestSummaryJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> str:
            events.append("backtest_job")
            return "backtest"

    class FakeScheduler:
        def __init__(self) -> None:
            self.jobs: list[tuple[str, int]] = []

        def add_job(
            self,
            *,
            name: str,
            interval_seconds: int,
            runner,
            run_immediately: bool = True,
        ) -> None:
            self.jobs.append((name, interval_seconds))
            runner()

        def run_pending(self) -> list[tuple[str, object]]:
            raise KeyboardInterrupt

        def seconds_until_next_run(self) -> float:
            return 1.0

    fake_scheduler = FakeScheduler()

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    monkeypatch.setattr("app.worker.BacktestSummaryJob", FakeBacktestSummaryJob)
    monkeypatch.setattr("app.worker.IntervalScheduler", lambda: fake_scheduler)
    monkeypatch.setattr("app.worker.sleep", lambda _seconds: None)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert fake_scheduler.jobs == [("worker_cycle", 60), ("backtest_summary", 300)]
    assert events == ["worker_job", "backtest_job"]


def test_worker_scheduled_mode_registers_live_reconcile_job_when_enabled(
    monkeypatch,
) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        WORKER_RUN_ONCE=False,
        WORKER_POLL_INTERVAL_SECONDS=60,
        LIVE_RECONCILE_SCHEDULE_ENABLED=True,
        LIVE_RECONCILE_SCHEDULE_INTERVAL_SECONDS=120,
    )
    events: list[str] = []

    class FakeWorkerCycleJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> str:
            events.append("worker_job")
            return "worker"

    class FakeLiveReconcileJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> str:
            events.append("live_reconcile_job")
            return "live_reconcile"

    class FakeScheduler:
        def __init__(self) -> None:
            self.jobs: list[tuple[str, int]] = []

        def add_job(
            self,
            *,
            name: str,
            interval_seconds: int,
            runner,
            run_immediately: bool = True,
        ) -> None:
            self.jobs.append((name, interval_seconds))
            runner()

        def run_pending(self) -> list[tuple[str, object]]:
            raise KeyboardInterrupt

        def seconds_until_next_run(self) -> float:
            return 1.0

    fake_scheduler = FakeScheduler()

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    monkeypatch.setattr("app.worker.LiveReconcileJob", FakeLiveReconcileJob)
    monkeypatch.setattr("app.worker.IntervalScheduler", lambda: fake_scheduler)
    monkeypatch.setattr("app.worker.sleep", lambda _seconds: None)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert fake_scheduler.jobs == [("worker_cycle", 60), ("live_reconcile", 120)]
    assert events == ["worker_job", "live_reconcile_job"]
