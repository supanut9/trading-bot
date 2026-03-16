from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class ScheduledJob:
    name: str
    interval_seconds: int
    runner: Callable[[], object]
    next_run_at: float = field(default=0.0)


class IntervalScheduler:
    def __init__(self, *, now_provider: Callable[[], float] | None = None) -> None:
        self._jobs: list[ScheduledJob] = []
        self._now = now_provider or monotonic

    def add_job(
        self,
        *,
        name: str,
        interval_seconds: int,
        runner: Callable[[], object],
        run_immediately: bool = True,
    ) -> None:
        now = self._now()
        self._jobs.append(
            ScheduledJob(
                name=name,
                interval_seconds=interval_seconds,
                runner=runner,
                next_run_at=now if run_immediately else now + interval_seconds,
            )
        )

    def run_pending(self) -> list[tuple[str, object]]:
        now = self._now()
        results: list[tuple[str, object]] = []
        for job in self._jobs:
            if now < job.next_run_at:
                continue
            results.append((job.name, job.runner()))
            job.next_run_at = now + job.interval_seconds
        return results

    def seconds_until_next_run(self) -> float | None:
        if not self._jobs:
            return None
        now = self._now()
        return max(0.0, min(job.next_run_at for job in self._jobs) - now)
