from app.infrastructure.executions.base import ExecutionUnavailableError


class UnsupportedLiveExecutionService:
    def execute(self, request: object) -> object:
        del request
        raise ExecutionUnavailableError("live execution is not configured")
