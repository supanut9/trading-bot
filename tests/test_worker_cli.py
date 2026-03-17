from app.application.services.operational_control_service import LiveReconcileControlResult
from app.application.services.runtime_startup_service import build_runtime_startup_context
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
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
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


def test_worker_run_once_performs_startup_state_sync_before_live_execution(monkeypatch) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        WORKER_RUN_ONCE=True,
    )
    events: list[str] = []

    class FakeStartupStateSyncJob:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run(self) -> LiveReconcileControlResult:
            events.append("startup_sync")
            return LiveReconcileControlResult(
                status="completed",
                detail="live orders reconciled",
                reconciled_count=1,
                filled_count=1,
                notified=False,
            )

    class FakeWorkerCycleJob:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run(self) -> None:
            events.append("worker_run")

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.StartupStateSyncJob", FakeStartupStateSyncJob)
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert events == ["startup_sync", "worker_run"]


def test_worker_run_once_aborts_when_startup_state_sync_fails(monkeypatch) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        WORKER_RUN_ONCE=True,
    )
    events: list[str] = []

    class FakeStartupStateSyncJob:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run(self) -> LiveReconcileControlResult:
            events.append("startup_sync")
            return LiveReconcileControlResult(
                status="failed",
                detail="live reconciliation failed",
                reconciled_count=0,
                filled_count=0,
                notified=False,
            )

    class FakeWorkerCycleJob:
        def __init__(self, _settings: Settings) -> None:
            raise AssertionError("worker job should not run after failed startup sync")

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.StartupStateSyncJob", FakeStartupStateSyncJob)
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert events == ["startup_sync"]


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
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
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

    class FakeStartupStateSyncJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> LiveReconcileControlResult:
            events.append("startup_sync")
            return LiveReconcileControlResult(
                status="completed",
                detail="no live orders to reconcile",
                reconciled_count=0,
                filled_count=0,
                notified=False,
            )

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
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.StartupStateSyncJob", FakeStartupStateSyncJob)
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
    assert events == ["startup_sync", "worker_job", "live_reconcile_job"]


def test_worker_scheduled_mode_runs_startup_state_sync_before_registering_jobs(
    monkeypatch,
) -> None:
    settings = Settings(
        PAPER_TRADING=False,
        LIVE_TRADING_ENABLED=True,
        EXCHANGE_API_KEY="key",
        EXCHANGE_API_SECRET="secret",
        WORKER_RUN_ONCE=False,
        WORKER_POLL_INTERVAL_SECONDS=60,
    )
    events: list[str] = []

    class FakeStartupStateSyncJob:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run(self) -> LiveReconcileControlResult:
            events.append("startup_sync")
            return LiveReconcileControlResult(
                status="completed",
                detail="no live orders to reconcile",
                reconciled_count=0,
                filled_count=0,
                notified=False,
            )

    class FakeWorkerCycleJob:
        def __init__(self, _settings: Settings) -> None:
            pass

        def run(self) -> str:
            events.append("worker_job")
            return "worker"

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
    monkeypatch.setattr(
        "app.worker.validate_runtime_startup",
        lambda _settings, component: build_runtime_startup_context(settings, component),
    )
    monkeypatch.setattr("app.worker.init_database", lambda _settings: ["candles"])
    monkeypatch.setattr("app.worker.StartupStateSyncJob", FakeStartupStateSyncJob)
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    monkeypatch.setattr("app.worker.IntervalScheduler", lambda: fake_scheduler)
    monkeypatch.setattr("app.worker.sleep", lambda _seconds: None)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert fake_scheduler.jobs == [("worker_cycle", 60)]
    assert events == ["startup_sync", "worker_job"]


def test_worker_returns_early_when_runtime_startup_validation_fails(monkeypatch) -> None:
    settings = Settings(WORKER_RUN_ONCE=True)
    events: list[str] = []

    def fail_validation(_settings: Settings, _component: str) -> None:
        raise RuntimeError("database connectivity check failed")

    class FakeWorkerCycleJob:
        def __init__(self, _settings: Settings) -> None:
            raise AssertionError("worker job should not be created after startup validation fails")

    monkeypatch.setattr("app.worker.get_settings", lambda: settings)
    monkeypatch.setattr("app.worker.configure_logging", lambda _settings: None)
    monkeypatch.setattr("app.worker.validate_runtime_startup", fail_validation)
    monkeypatch.setattr(
        "app.worker.init_database",
        lambda _settings: events.append("init_database") or ["candles"],
    )
    monkeypatch.setattr("app.worker.WorkerCycleJob", FakeWorkerCycleJob)
    get_settings.cache_clear()

    try:
        main()
    finally:
        get_settings.cache_clear()

    assert events == []
