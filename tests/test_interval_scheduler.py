from app.jobs.interval_scheduler import IntervalScheduler


def test_interval_scheduler_runs_immediate_jobs_and_waits_for_interval() -> None:
    now = [100.0]
    calls: list[str] = []

    def now_provider() -> float:
        return now[0]

    scheduler = IntervalScheduler(now_provider=now_provider)
    scheduler.add_job(
        name="worker_cycle",
        interval_seconds=60,
        runner=lambda: calls.append("worker_cycle"),
    )

    scheduler.run_pending()
    scheduler.run_pending()
    now[0] = 160.0
    scheduler.run_pending()

    assert calls == ["worker_cycle", "worker_cycle"]


def test_interval_scheduler_supports_delayed_first_run() -> None:
    now = [100.0]
    calls: list[str] = []

    def now_provider() -> float:
        return now[0]

    scheduler = IntervalScheduler(now_provider=now_provider)
    scheduler.add_job(
        name="backtest_summary",
        interval_seconds=300,
        runner=lambda: calls.append("backtest_summary"),
        run_immediately=False,
    )

    scheduler.run_pending()
    now[0] = 399.0
    scheduler.run_pending()
    now[0] = 400.0
    scheduler.run_pending()

    assert calls == ["backtest_summary"]


def test_interval_scheduler_reports_seconds_until_next_run() -> None:
    now = [50.0]

    def now_provider() -> float:
        return now[0]

    scheduler = IntervalScheduler(now_provider=now_provider)
    scheduler.add_job(
        name="worker_cycle",
        interval_seconds=10,
        runner=lambda: None,
        run_immediately=False,
    )

    assert scheduler.seconds_until_next_run() == 10.0
    now[0] = 55.0
    assert scheduler.seconds_until_next_run() == 5.0


def test_interval_scheduler_reschedules_from_post_run_time() -> None:
    now = [100.0]
    calls: list[float] = []

    def now_provider() -> float:
        return now[0]

    def slow_runner() -> None:
        calls.append(now[0])
        now[0] = 120.0

    scheduler = IntervalScheduler(now_provider=now_provider)
    scheduler.add_job(
        name="worker_cycle",
        interval_seconds=60,
        runner=slow_runner,
    )

    scheduler.run_pending()

    assert scheduler.seconds_until_next_run() == 60.0
    now[0] = 179.0
    scheduler.run_pending()
    assert calls == [100.0]
    now[0] = 180.0
    scheduler.run_pending()
    assert calls == [100.0, 180.0]
