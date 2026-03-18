import logging

from fastapi.testclient import TestClient

from app.application.services.operational_control_service import WorkerControlResult
from app.config import Settings
from app.jobs.worker_cycle_job import WorkerCycleJob
from app.main import app


def test_api_request_logs_share_request_id(caplog) -> None:
    client = TestClient(app)

    with caplog.at_level(logging.INFO):
        response = client.get("/health", headers={"X-Request-ID": "req-test-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test-123"

    request_records = [
        record for record in caplog.records if record.getMessage().startswith("http_request_")
    ]

    assert len(request_records) == 2
    assert request_records[0].getMessage() == "http_request_started method=GET path=/health"
    assert (
        request_records[1]
        .getMessage()
        .startswith("http_request_completed method=GET path=/health status_code=200 duration_ms=")
    )
    assert {record.correlation_id for record in request_records} == {"req-test-123"}


def test_worker_cycle_job_logs_with_generated_correlation_id(monkeypatch, caplog) -> None:
    settings = Settings()

    class FakeControls:
        def __init__(self, active_settings: Settings) -> None:
            assert active_settings is settings

        def run_worker_cycle(self, *, source: str) -> WorkerControlResult:
            assert source == "job.worker_cycle"
            return WorkerControlResult(
                status="executed",
                detail="signal executed in paper mode",
                signal_action="buy",
                client_order_id="paper-btc-usdt-buy-1",
                order_id=1,
                trade_id=2,
                notified=False,
            )

    monkeypatch.setattr("app.jobs.worker_cycle_job.OperationalControlService", FakeControls)

    with caplog.at_level(logging.INFO):
        result = WorkerCycleJob(settings).run()

    assert result.status == "executed"

    completion_records = [
        record
        for record in caplog.records
        if record.getMessage().startswith("worker_cycle_completed")
    ]

    assert len(completion_records) == 1
    assert completion_records[0].correlation_id.startswith("worker-cycle-")
